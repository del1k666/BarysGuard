import base64
import concurrent.futures
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from core.agent_client import AgentClient


class PingWorker(QThread):
    """Pings all hosts in parallel; emits (host_id, is_online, info_dict)."""
    result = pyqtSignal(str, bool, dict)

    def __init__(self, hosts: list):
        super().__init__()
        self._hosts = hosts

    def _ping_one(self, h: dict):
        client = AgentClient(h["ip"], h["port"], h["token"], timeout=5)
        try:
            info = client.ping()
            return h["id"], True, info
        except Exception:
            return h["id"], False, {}

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(self._ping_one, h): h for h in self._hosts}
            for fut in concurrent.futures.as_completed(futures):
                host_id, online, info = fut.result()
                self.result.emit(host_id, online, info)


class RemoteScanWorker(QThread):
    """Runs selected scan types on a single remote host."""
    progress = pyqtSignal(str)
    done     = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, host: dict, scan_types: list, path: str, rules: dict):
        """
        scan_types: subset of ["yara", "ioc", "hashes"]
        rules: {name: rule_text} for YARA scans
        """
        super().__init__()
        self._host       = host
        self._scan_types = scan_types
        self._path       = path
        self._rules      = rules

    def run(self):
        client  = AgentClient(self._host["ip"], self._host["port"], self._host["token"], timeout=120)
        results = []
        try:
            if "yara" in self._scan_types and self._rules:
                self.progress.emit("YARA скан...")
                r = client.scan_yara(self._rules, self._path)
                for m in r.get("matches", []):
                    results.append({"type": "YARA", "rule": m.get("rule", "?"),
                                    "file": m.get("file", "?")})

            if "ioc" in self._scan_types:
                self.progress.emit("Сбор IOC...")
                r = client.scan_ioc()
                for p in r.get("processes", []):
                    if p.get("suspicious"):
                        results.append({
                            "type": "IOC",
                            "rule": "Подозрит. процесс",
                            "file": f"{p['name']} (PID:{p['pid']}) {p['path']}",
                        })
                for c in r.get("connections", []):
                    results.append({
                        "type": "IOC",
                        "rule": "Соединение",
                        "file": f"{c['process']} → {c['remote']}",
                    })
                for a in r.get("autoruns", []):
                    results.append({
                        "type": "IOC",
                        "rule": "Автозапуск",
                        "file": f"{a['name']} = {a['value']}",
                    })

            if "hashes" in self._scan_types:
                self.progress.emit("Хэши файлов...")
                r = client.scan_hashes(self._path)
                for h in r.get("hashes", []):
                    results.append({
                        "type": "HASH",
                        "rule": (h.get("sha256") or "?")[:16] + "…",
                        "file": h.get("file", "?"),
                    })

            self.done.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class RemoteProcessListWorker(QThread):
    """Fetches running process list from remote agent."""
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, host: dict):
        super().__init__()
        self._host = host

    def run(self):
        client = AgentClient(self._host["ip"], self._host["port"],
                             self._host["token"], timeout=30)
        try:
            r = client.list_processes()
            self.done.emit(r.get("processes", []))
        except Exception as e:
            self.error.emit(str(e))


class RemoteMemScanWorker(QThread):
    """Runs /scan/memory/all on remote agent with selected YARA rules."""
    progress = pyqtSignal(str)
    done     = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, host: dict, rules: dict):
        super().__init__()
        self._host  = host
        self._rules = rules

    def stop(self):
        self.requestInterruption()

    def run(self):
        client = AgentClient(self._host["ip"], self._host["port"],
                             self._host["token"], timeout=180)
        try:
            self.progress.emit("Сканирование памяти процессов на удалённом хосте...")
            r = client.scan_memory_all(self._rules)
            if "error" in r:
                self.error.emit(r["error"])
                return
            results = []
            for m in r.get("matches", []):
                results.append({
                    "type":         "MEMORY",
                    "rule":         m.get("rule", "?"),
                    "file":         m.get("file", "?"),
                    "pid":          str(m.get("pid", "?")),
                    "process_name": m.get("process_name", "?"),
                })
            self.done.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class DeployWorker(QThread):
    """Copies agent.exe to remote host via WinRM and installs it as a service."""
    progress = pyqtSignal(str)
    done     = pyqtSignal(str)   # emits the token read from the remote host
    error    = pyqtSignal(str)

    def __init__(self, ip: str, username: str, password: str):
        super().__init__()
        self._ip       = ip
        self._username = username
        self._password = password

    def _agent_exe(self) -> Path:
        candidates = [
            Path(__file__).parent.parent / "agent" / "dist" / "agent.exe",
            Path(__file__).parent.parent / "agent" / "agent.exe",
        ]
        for p in candidates:
            if p.exists():
                return p
        raise FileNotFoundError(
            "agent.exe not found. Build it first:\n"
            "  cd agent && build.bat"
        )

    def run(self):
        try:
            import winrm
        except ImportError:
            self.error.emit("pywinrm not installed. Run: pip install pywinrm")
            return

        try:
            agent_path = self._agent_exe()
        except FileNotFoundError as e:
            self.error.emit(str(e))
            return

        try:
            self.progress.emit(f"Подключение к {self._ip} по WinRM...")
            # Use http:// for basic deployments; switch to https://:5986 for production.
            session = winrm.Session(
                f"http://{self._ip}:5985/wsman",
                auth=(self._username, self._password),
                transport="ntlm",
                operation_timeout_sec=30,
                read_timeout_sec=60,
            )
            # Clear password from memory as soon as the session is established
            self._password = None

            self.progress.emit("Создание директории C:\\Program Files\\IOCAgent...")
            res = session.run_ps(
                "New-Item -ItemType Directory -Force "
                "-Path 'C:\\Program Files\\IOCAgent' | Out-Null"
            )
            if res.status_code != 0:
                self.error.emit(f"Не удалось создать директорию: {res.std_err.decode('utf-8', errors='replace')}")
                return

            self.progress.emit(f"Копирование {agent_path.name} ({agent_path.stat().st_size // 1024} КБ)...")
            raw   = agent_path.read_bytes()
            b64   = base64.b64encode(raw).decode()
            chunk = 4000
            session.run_ps(
                "[System.IO.File]::WriteAllBytes("
                "'C:\\Program Files\\IOCAgent\\agent.exe', [byte[]]@())"
            )
            try:
                for i in range(0, len(b64), chunk):
                    part = b64[i: i + chunk]
                    pct = (i + chunk) * 100 // len(b64)
                    self.progress.emit(f"Загрузка агента... {min(pct, 100)}%")
                    res = session.run_ps(
                        f"$b=[Convert]::FromBase64String('{part}');"
                        "$f=[IO.File]::Open('C:\\Program Files\\IOCAgent\\agent.exe','Append');"
                        "$f.Write($b,0,$b.Length);$f.Close()"
                    )
                    if res.status_code != 0:
                        session.run_ps("Remove-Item 'C:\\Program Files\\IOCAgent\\agent.exe' -Force -EA SilentlyContinue")
                        self.error.emit(f"Ошибка при копировании файла: {res.std_err.decode('utf-8', errors='replace')}")
                        return
            except Exception as e:
                self.error.emit(f"Ошибка передачи файла: {e}")
                return

            self.progress.emit("Установка Windows Service...")
            res = session.run_ps(
                "cd 'C:\\Program Files\\IOCAgent'; .\\agent.exe --install"
            )
            if res.status_code != 0:
                self.error.emit(f"Ошибка установки сервиса: {res.std_err.decode('utf-8', errors='replace')}")
                return
            session.run_ps("Start-Service IOCAgent -ErrorAction SilentlyContinue")

            self.progress.emit("Чтение токена...")
            r = session.run_ps("Get-Content 'C:\\Program Files\\IOCAgent\\token.txt'")
            if r.status_code != 0 or not r.std_out:
                self.error.emit("Не удалось прочитать токен. Подождите несколько секунд и попробуйте снова.")
                return
            token = r.std_out.decode("utf-8").strip()
            if not token:
                self.error.emit("Токен пустой — агент мог не запуститься ещё. Повторите попытку.")
                return
            self.done.emit(token)
        except Exception as e:
            self.error.emit(str(e))
