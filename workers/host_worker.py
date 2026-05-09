import os
import base64
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from core.agent_client import AgentClient


class PingWorker(QThread):
    """Pings all hosts concurrently; emits (host_id, is_online, info_dict)."""
    result = pyqtSignal(str, bool, dict)

    def __init__(self, hosts: list):
        super().__init__()
        self._hosts = hosts

    def run(self):
        for h in self._hosts:
            client = AgentClient(h["ip"], h["port"], h["token"], timeout=5)
            try:
                info = client.ping()
                self.result.emit(h["id"], True, info)
            except Exception:
                self.result.emit(h["id"], False, {})


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
        client  = AgentClient(self._host["ip"], self._host["port"], self._host["token"])
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
                        "rule": h["sha256"][:16] + "…",
                        "file": h["file"],
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
            session = winrm.Session(
                f"http://{self._ip}:5985/wsman",
                auth=(self._username, self._password),
                transport="ntlm",
            )

            self.progress.emit("Создание директории C:\\Program Files\\IOCAgent...")
            session.run_ps(
                "New-Item -ItemType Directory -Force "
                "-Path 'C:\\Program Files\\IOCAgent' | Out-Null"
            )

            self.progress.emit(f"Копирование {agent_path.name} ({agent_path.stat().st_size // 1024} КБ)...")
            raw   = agent_path.read_bytes()
            b64   = base64.b64encode(raw).decode()
            chunk = 4000
            session.run_ps(
                "[System.IO.File]::WriteAllBytes("
                "'C:\\Program Files\\IOCAgent\\agent.exe', [byte[]]@())"
            )
            for i in range(0, len(b64), chunk):
                part = b64[i : i + chunk]
                session.run_ps(
                    f"$b=[Convert]::FromBase64String('{part}');"
                    "$f=[IO.File]::Open('C:\\Program Files\\IOCAgent\\agent.exe','Append');"
                    "$f.Write($b,0,$b.Length);$f.Close()"
                )

            self.progress.emit("Установка Windows Service...")
            session.run_ps(
                "cd 'C:\\Program Files\\IOCAgent'; .\\agent.exe --install"
            )
            session.run_ps("Start-Service IOCAgent -ErrorAction SilentlyContinue")

            self.progress.emit("Чтение токена...")
            r     = session.run_ps(
                "Get-Content 'C:\\Program Files\\IOCAgent\\token.txt'"
            )
            token = r.std_out.decode("utf-8").strip()

            self.done.emit(token)
        except Exception as e:
            self.error.emit(str(e))
