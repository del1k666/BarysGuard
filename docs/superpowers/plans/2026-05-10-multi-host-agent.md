# Multi-Host Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-host scanning — a Flask HTTPS agent (Windows Service) on each monitored host, plus a Hosts tab in the main app to deploy, ping, and scan remote machines; all existing scan tabs respect the selected host.

**Architecture:** `agent/agent.py` is a standalone Flask HTTPS server with API token auth; `core/hosts_config.py` persists hosts to `hosts.json`; `core/host_state.py` is a global singleton the tabs check when routing scans; `workers/host_worker.py` provides QThread workers for ping, scan, and deploy; `ui/hosts_tab.py` is the new tab; `ui/main_window.py` gains a host-selector QComboBox in the header.

**Tech Stack:** Python 3.12, Flask, psutil, pywin32, cryptography (agent); requests, pywinrm, urllib3 (main app); PyQt6 (UI)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `core/hosts_config.py` | Create | Load/save hosts.json, CRUD for host entries |
| `core/host_state.py` | Create | Global singleton: current selected host |
| `core/agent_client.py` | Create | requests wrapper — all HTTP calls to an agent |
| `agent/__init__.py` | Create | empty |
| `agent/agent.py` | Create | Flask HTTPS server + Windows Service entry point |
| `agent/requirements_agent.txt` | Create | Agent-only pip deps |
| `agent/build.bat` | Create | PyInstaller one-liner |
| `workers/host_worker.py` | Create | PingWorker, RemoteScanWorker, DeployWorker |
| `ui/hosts_tab.py` | Create | Hosts tab UI |
| `ui/main_window.py` | Modify | Add host-selector QComboBox to header |
| `requirements.txt` | Modify | Add requests, pywinrm, urllib3 |
| `tests/test_hosts_config.py` | Create | Unit tests for hosts_config |
| `tests/test_agent_client.py` | Create | Unit tests for agent_client (mocked) |

---

## Task 1: Data layer — hosts_config.py + host_state.py

**Files:**
- Create: `core/hosts_config.py`
- Create: `core/host_state.py`
- Create: `tests/test_hosts_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_hosts_config.py
import os, json, pytest
from pathlib import Path

# Point HOSTS_FILE at a temp location before import
os.environ["HOSTS_FILE_OVERRIDE"] = str(Path(__file__).parent / "hosts_test.json")
import importlib
import core.hosts_config as hc
importlib.reload(hc)

def setup_function():
    if hc.HOSTS_FILE.exists():
        hc.HOSTS_FILE.unlink()

def test_load_empty():
    assert hc.load_hosts() == []

def test_add_and_load():
    h = hc.add_host("TEST", "10.0.0.1", 5555, "abc123")
    hosts = hc.load_hosts()
    assert len(hosts) == 1
    assert hosts[0]["ip"] == "10.0.0.1"
    assert hosts[0]["name"] == "TEST"
    assert "id" in hosts[0]

def test_update_host():
    h = hc.add_host("SRV", "10.0.0.2", 5555, "tok")
    hc.update_host(h["id"], last_seen="2026-01-01")
    updated = [x for x in hc.load_hosts() if x["id"] == h["id"]][0]
    assert updated["last_seen"] == "2026-01-01"

def test_remove_host():
    h = hc.add_host("DEL", "10.0.0.3", 5555, "tok")
    hc.remove_host(h["id"])
    assert all(x["id"] != h["id"] for x in hc.load_hosts())

def teardown_function():
    if hc.HOSTS_FILE.exists():
        hc.HOSTS_FILE.unlink()
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```
cd C:\Users\User\Documents\project\ioc_analyzer_v2
python -m pytest tests/test_hosts_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.hosts_config'`

- [ ] **Step 3: Create core/hosts_config.py**

```python
import json
import os
import uuid
from pathlib import Path

_override = os.environ.get("HOSTS_FILE_OVERRIDE")
HOSTS_FILE = Path(_override) if _override else (
    Path(os.path.dirname(os.path.abspath(__file__))).parent / "hosts.json"
)


def load_hosts() -> list:
    if not HOSTS_FILE.exists():
        return []
    try:
        with open(HOSTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_hosts(hosts: list) -> None:
    with open(HOSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(hosts, f, ensure_ascii=False, indent=2)


def add_host(name: str, ip: str, port: int, token: str) -> dict:
    hosts = load_hosts()
    entry = {
        "id":        str(uuid.uuid4()),
        "name":      name,
        "ip":        ip,
        "port":      port,
        "token":     token,
        "last_seen": None,
        "last_scan": None,
    }
    hosts.append(entry)
    save_hosts(hosts)
    return entry


def update_host(host_id: str, **fields) -> None:
    hosts = load_hosts()
    for h in hosts:
        if h["id"] == host_id:
            h.update(fields)
            break
    save_hosts(hosts)


def remove_host(host_id: str) -> None:
    save_hosts([h for h in load_hosts() if h["id"] != host_id])
```

- [ ] **Step 4: Create core/host_state.py**

```python
# Global singleton: which host is currently active in the UI.
# None = local machine. Tabs read this when starting any scan operation.

_current: dict | None = None


def get_current_host() -> dict | None:
    return _current


def set_current_host(host: dict | None) -> None:
    global _current
    _current = host


def is_local() -> bool:
    return _current is None
```

- [ ] **Step 5: Run tests — expect PASS**

```
python -m pytest tests/test_hosts_config.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```
git add core/hosts_config.py core/host_state.py tests/test_hosts_config.py
git commit -m "feat: add hosts data layer (hosts_config, host_state)"
```

---

## Task 2: HTTP client — core/agent_client.py

**Files:**
- Create: `core/agent_client.py`
- Create: `tests/test_agent_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agent_client.py
from unittest.mock import patch, MagicMock
import pytest
from core.agent_client import AgentClient


@pytest.fixture
def client():
    return AgentClient("192.168.1.1", 5555, "testtoken")


def test_ping_success(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "ok", "hostname": "PC01"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as m:
        result = client.ping()
        m.assert_called_once_with(
            "https://192.168.1.1:5555/ping",
            headers={"X-Api-Token": "testtoken", "Content-Type": "application/json"},
            verify=False,
            timeout=10,
        )
    assert result["hostname"] == "PC01"


def test_scan_yara_posts_correct_body(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"matches": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as m:
        result = client.scan_yara({"rule1": "rule rule1 { condition: false }"}, "C:\\Users")
        _, kwargs = m.call_args
        assert kwargs["json"]["path"] == "C:\\Users"
        assert "rule1" in kwargs["json"]["rules"]
    assert result["matches"] == []


def test_unauthorized_raises(client):
    import requests
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("403")

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(requests.HTTPError):
            client.ping()
```

- [ ] **Step 2: Run tests — expect FAIL**

```
python -m pytest tests/test_agent_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.agent_client'`

- [ ] **Step 3: Create core/agent_client.py**

```python
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AgentClient:
    def __init__(self, ip: str, port: int, token: str, timeout: int = 10):
        self._base    = f"https://{ip}:{port}"
        self._headers = {"X-Api-Token": token, "Content-Type": "application/json"}
        self._timeout = timeout

    def _get(self, path: str) -> dict:
        r = requests.get(
            f"{self._base}{path}",
            headers=self._headers,
            verify=False,
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, data: dict) -> dict:
        r = requests.post(
            f"{self._base}{path}",
            json=data,
            headers=self._headers,
            verify=False,
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json()

    def ping(self) -> dict:
        return self._get("/ping")

    def get_info(self) -> dict:
        return self._get("/info")

    def scan_yara(self, rules: dict, path: str) -> dict:
        return self._post("/scan/yara", {"rules": rules, "path": path})

    def scan_ioc(self) -> dict:
        return self._post("/scan/ioc", {})

    def scan_memory(self, pid: int = 0, rules: dict = None) -> dict:
        return self._post("/scan/memory", {"pid": pid, "rules": rules or {}})

    def scan_hashes(self, path: str) -> dict:
        return self._post("/scan/hashes", {"path": path})

    def list_processes(self) -> dict:
        return self._post("/scan/memory", {"pid": 0, "rules": {}})
```

- [ ] **Step 4: Install requests if missing**

```
pip install requests urllib3
```

- [ ] **Step 5: Run tests — expect PASS**

```
python -m pytest tests/test_agent_client.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```
git add core/agent_client.py tests/test_agent_client.py
git commit -m "feat: add AgentClient HTTP wrapper with tests"
```

---

## Task 3: Agent server — agent/agent.py

**Files:**
- Create: `agent/__init__.py`
- Create: `agent/agent.py`
- Create: `agent/requirements_agent.txt`
- Create: `agent/build.bat`

- [ ] **Step 1: Install agent dependencies**

```
pip install flask psutil cryptography pywin32
```

- [ ] **Step 2: Create agent/__init__.py (empty)**

```python
```

- [ ] **Step 3: Create agent/requirements_agent.txt**

```
flask>=3.0
psutil>=5.9
cryptography>=42.0
pywin32>=306
```

- [ ] **Step 4: Create agent/agent.py**

```python
"""
IOC Analyzer Agent — remote scanning daemon.

  python agent.py                  run in foreground (test mode)
  python agent.py --install        install as Windows Service
  python agent.py --uninstall      remove Windows Service
  python agent.py --start          start the installed service
"""
import sys
import os
import ssl
import json
import secrets
import socket
import tempfile
import subprocess
import platform
import hashlib
from pathlib import Path
from datetime import datetime
from functools import wraps

import psutil
from flask import Flask, request, jsonify

# ── Paths ──────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
PORT          = 5555
AGENT_DIR     = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CERT_FILE     = AGENT_DIR / "cert.pem"
KEY_FILE      = AGENT_DIR / "key.pem"
TOKEN_FILE    = AGENT_DIR / "token.txt"

YARA_EXE: str | None = None
for _p in [AGENT_DIR / "yara64.exe", Path(r"C:\Tools\yara\yara64.exe")]:
    if _p.exists():
        YARA_EXE = str(_p)
        break

# ── Auth ───────────────────────────────────────────────────────────────────
_token: str = ""

def _load_token() -> str:
    global _token
    if TOKEN_FILE.exists():
        _token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    else:
        _token = secrets.token_hex(32)
        TOKEN_FILE.write_text(_token, encoding="utf-8")
    return _token


def _auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.headers.get("X-Api-Token") != _token:
            return jsonify({"error": "unauthorized"}), 403
        return f(*args, **kwargs)
    return wrapper


# ── Certificate ───────────────────────────────────────────────────────────
def _generate_cert() -> bool:
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime as dt

        key  = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, socket.gethostname())])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(dt.datetime.utcnow())
            .not_valid_after(dt.datetime.utcnow() + dt.timedelta(days=3650))
            .sign(key, hashes.SHA256())
        )
        CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        KEY_FILE.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
        return True
    except Exception:
        return False


# ── Flask app ──────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.route("/ping")
@_auth
def ping():
    return jsonify({
        "status":        "ok",
        "hostname":      socket.gethostname(),
        "os":            platform.platform(),
        "agent_version": AGENT_VERSION,
        "timestamp":     datetime.now().isoformat(),
    })


@app.route("/info")
@_auth
def info():
    mem  = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    return jsonify({
        "cpu_percent":  psutil.cpu_percent(interval=0.5),
        "ram_total":    mem.total,
        "ram_used":     mem.used,
        "ram_percent":  mem.percent,
        "disk_total":   disk.total,
        "disk_used":    disk.used,
        "disk_percent": disk.percent,
        "boot_time":    psutil.boot_time(),
        "users":        [u.name for u in psutil.users()],
    })


@app.route("/scan/yara", methods=["POST"])
@_auth
def scan_yara():
    data       = request.json or {}
    rules_dict = data.get("rules", {})
    path       = data.get("path", r"C:\Users")

    if not rules_dict:
        return jsonify({"error": "no rules"}), 400
    if not os.path.exists(path):
        return jsonify({"error": f"path not found: {path}"}), 400

    matches = []
    if not YARA_EXE:
        matches.append({"rule": "INFO", "file": "yara64.exe not found on agent"})
        return jsonify({"matches": matches})

    for rule_name, rule_text in rules_dict.items():
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".yar")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(rule_text)
            for fpath in _collect_files(path):
                try:
                    r = subprocess.run(
                        [YARA_EXE, tmp_path, fpath],
                        capture_output=True, text=True, timeout=15,
                        encoding="utf-8", errors="replace",
                    )
                    for line in r.stdout.strip().splitlines():
                        line = line.strip()
                        if line and " " in line:
                            parts = line.split(" ", 1)
                            matches.append({"rule": parts[0], "file": parts[1]})
                    if r.stderr.strip():
                        matches.append({"rule": "WARN", "file": f"[{rule_name}] {r.stderr.strip()[:150]}"})
                except subprocess.TimeoutExpired:
                    matches.append({"rule": "TIMEOUT", "file": fpath})
                except Exception as e:
                    matches.append({"rule": "ERROR", "file": str(e)})
        except Exception as e:
            matches.append({"rule": "COMPILE_ERR", "file": f"{rule_name}: {e}"})
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    return jsonify({"matches": matches})


@app.route("/scan/ioc", methods=["POST"])
@_auth
def scan_ioc():
    PS = r"""
$out = @()
$procs = Get-Process | ForEach-Object {
    try { $p = $_.Path } catch { $p = 'N/A' }
    $sus = $p -and $p -ne 'N/A' -and $p -notlike 'C:\Windows\*' -and $p -notlike 'C:\Program Files*'
    [PSCustomObject]@{Name=$_.ProcessName;PID=$_.Id;Path=if($p){$p}else{'N/A'};Suspicious=$sus}
}
$procs | ForEach-Object { $out += "PROC|$($_.Name)|$($_.PID)|$($_.Path)|$($_.Suspicious)" }
$nets = Get-NetTCPConnection -State Established -EA SilentlyContinue
$nets | ForEach-Object {
    $pn = (Get-Process -Id $_.OwningProcess -EA SilentlyContinue).ProcessName
    $out += "NET|$pn|$($_.LocalAddress):$($_.LocalPort)|$($_.RemoteAddress):$($_.RemotePort)"
}
@('HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
  'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run') | ForEach-Object {
    $rk = $_
    try {
        $v = Get-ItemProperty $rk -EA SilentlyContinue
        if ($v) { $v.PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' } |
            ForEach-Object { $out += "REG|$($_.Name)|$($_.Value)" } }
    } catch {}
}
$out -join "`n"
"""
    result = {"processes": [], "connections": [], "autoruns": [], "error": ""}
    try:
        r = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", PS],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
        for line in r.stdout.strip().splitlines():
            parts = line.split("|")
            if not parts:
                continue
            if parts[0] == "PROC" and len(parts) >= 5:
                result["processes"].append({
                    "name": parts[1], "pid": parts[2],
                    "path": parts[3], "suspicious": parts[4].lower() == "true",
                })
            elif parts[0] == "NET" and len(parts) >= 4:
                result["connections"].append(
                    {"process": parts[1], "local": parts[2], "remote": parts[3]}
                )
            elif parts[0] == "REG" and len(parts) >= 3:
                result["autoruns"].append({"name": parts[1], "value": parts[2]})
    except Exception as e:
        result["error"] = str(e)

    return jsonify(result)


@app.route("/scan/memory", methods=["POST"])
@_auth
def scan_memory():
    data       = request.json or {}
    pid        = data.get("pid", 0)
    rules_dict = data.get("rules", {})

    if not pid:
        procs = []
        for p in psutil.process_iter(["pid", "name", "exe"]):
            try:
                procs.append({
                    "pid":  p.info["pid"],
                    "name": p.info["name"],
                    "exe":  p.info.get("exe") or "",
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return jsonify({"processes": procs})

    matches = []
    if YARA_EXE and rules_dict:
        try:
            exe_path = psutil.Process(int(pid)).exe()
        except Exception:
            return jsonify({"error": f"cannot access process {pid}"}), 400

        for rule_name, rule_text in rules_dict.items():
            tmp_path = None
            try:
                fd, tmp_path = tempfile.mkstemp(suffix=".yar")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(rule_text)
                r = subprocess.run(
                    [YARA_EXE, tmp_path, exe_path],
                    capture_output=True, text=True, timeout=15,
                )
                for line in r.stdout.strip().splitlines():
                    if " " in line.strip():
                        parts = line.strip().split(" ", 1)
                        matches.append({"rule": parts[0], "file": parts[1]})
            except Exception as e:
                matches.append({"rule": "ERROR", "file": str(e)})
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

    return jsonify({"matches": matches})


@app.route("/scan/hashes", methods=["POST"])
@_auth
def scan_hashes():
    data  = request.json or {}
    path  = data.get("path", r"C:\Users")
    items = []
    for fpath in _collect_files(path)[:200]:
        try:
            h = hashlib.sha256()
            with open(fpath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            items.append({"file": fpath, "sha256": h.hexdigest()})
        except (PermissionError, OSError):
            pass
    return jsonify({"hashes": items})


def _collect_files(path: str) -> list:
    if os.path.isfile(path):
        return [path]
    files = []
    try:
        for root, _, fnames in os.walk(path):
            for fn in fnames:
                files.append(os.path.join(root, fn))
    except Exception:
        pass
    return files


# ── Server startup ─────────────────────────────────────────────────────────
def run_server():
    _load_token()
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        print("[IOCAgent] Generating self-signed certificate...")
        _generate_cert()
    print(f"[IOCAgent] v{AGENT_VERSION} starting on https://0.0.0.0:{PORT}")
    print(f"[IOCAgent] Token: {_token}")
    print(f"[IOCAgent] YARA:  {YARA_EXE or 'NOT FOUND — scans will fail'}")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(CERT_FILE), str(KEY_FILE))
    app.run(host="0.0.0.0", port=PORT, ssl_context=ctx,
            debug=False, use_reloader=False)


# ── Windows Service ────────────────────────────────────────────────────────
def _run_as_service():
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager

    class IOCAgentService(win32serviceutil.ServiceFramework):
        _svc_name_         = "IOCAgent"
        _svc_display_name_ = "IOC Analyzer Agent"
        _svc_description_  = "Remote scanning agent for IOC Analyzer"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            run_server()

    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(IOCAgentService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(IOCAgentService)


if __name__ == "__main__":
    args = sys.argv[1:]
    if any(a in args for a in ["--install", "--uninstall", "--start", "--stop", "--remove"]):
        _run_as_service()
    else:
        run_server()
```

- [ ] **Step 5: Create agent/build.bat**

```bat
@echo off
cd /d "%~dp0"
echo Building IOC Agent...
pip install pyinstaller flask psutil cryptography pywin32
pyinstaller --onefile --name agent --hidden-import win32timezone agent.py
echo Done. agent.exe is in dist\
pause
```

- [ ] **Step 6: Test agent starts in foreground**

```
cd C:\Users\User\Documents\project\ioc_analyzer_v2\agent
python agent.py
```

Expected output:
```
[IOCAgent] Generating self-signed certificate...
[IOCAgent] v1.0.0 starting on https://0.0.0.0:5555
[IOCAgent] Token: <32-char hex>
```
Press Ctrl+C to stop.

- [ ] **Step 7: Test /ping endpoint (in another terminal)**

```powershell
$tok = Get-Content .\token.txt
Invoke-WebRequest -Uri https://localhost:5555/ping -Headers @{"X-Api-Token"=$tok} -SkipCertificateCheck | Select-Object -ExpandProperty Content
```

Expected: `{"hostname":"...","os":"...","status":"ok",...}`

- [ ] **Step 8: Commit**

```
git add agent/ 
git commit -m "feat: add IOC Agent Flask HTTPS server with Windows Service support"
```

---

## Task 4: QThread workers — workers/host_worker.py

**Files:**
- Create: `workers/host_worker.py`

- [ ] **Step 1: Create workers/host_worker.py**

```python
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
        # Look for built agent.exe, fall back to agent.py location hint
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
            raw    = agent_path.read_bytes()
            b64    = base64.b64encode(raw).decode()
            chunk  = 4000
            # Clear target file first
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
```

- [ ] **Step 2: Commit**

```
git add workers/host_worker.py
git commit -m "feat: add PingWorker, RemoteScanWorker, DeployWorker"
```

---

## Task 5: Hosts tab UI — ui/hosts_tab.py

**Files:**
- Create: `ui/hosts_tab.py`

- [ ] **Step 1: Create ui/hosts_tab.py**

```python
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QListWidget,
    QListWidgetItem, QCheckBox, QSplitter, QLineEdit, QDialog, QFormLayout,
    QDialogButtonBox, QMessageBox, QSpinBox, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from core.hosts_config import load_hosts, add_host, remove_host, update_host
from core.agent_client import AgentClient
from workers.host_worker import PingWorker, RemoteScanWorker, DeployWorker
from constants import BUILTIN_YARA_RULES
from datetime import datetime


# ── Add-host dialog ────────────────────────────────────────────────────────
class _AddHostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить хост")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        self._name  = QLineEdit(); self._name.setPlaceholderText("WS-FINANCE01")
        self._ip    = QLineEdit(); self._ip.setPlaceholderText("192.168.1.10")
        self._port  = QSpinBox();  self._port.setRange(1, 65535); self._port.setValue(5555)
        self._token = QLineEdit(); self._token.setPlaceholderText("из agent/token.txt")
        layout.addRow("Имя:",    self._name)
        layout.addRow("IP:",     self._ip)
        layout.addRow("Порт:",   self._port)
        layout.addRow("Токен:",  self._token)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def data(self):
        return {
            "name":  self._name.text().strip(),
            "ip":    self._ip.text().strip(),
            "port":  self._port.value(),
            "token": self._token.text().strip(),
        }


# ── Deploy dialog ──────────────────────────────────────────────────────────
class _DeployDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deploy агента (WinRM)")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        self._ip   = QLineEdit(); self._ip.setPlaceholderText("192.168.1.10")
        self._user = QLineEdit(); self._user.setPlaceholderText("DOMAIN\\admin или admin")
        self._pwd  = QLineEdit(); self._pwd.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("IP хоста:", self._ip)
        layout.addRow("Пользователь:", self._user)
        layout.addRow("Пароль:", self._pwd)
        self._log = QLabel("Требует WinRM (порт 5985) на целевом хосте.")
        self._log.setStyleSheet("color:#8b949e;font-size:11px;")
        self._log.setWordWrap(True)
        layout.addRow(self._log)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def data(self):
        return {
            "ip":       self._ip.text().strip(),
            "username": self._user.text().strip(),
            "password": self._pwd.text(),
        }


# ── Hosts Tab ──────────────────────────────────────────────────────────────
class HostsTab(QWidget):
    def __init__(self, on_host_changed=None):
        super().__init__()
        self._on_host_changed = on_host_changed  # callback(host_dict | None)
        self._selected_id: str | None = None
        self._ping_worker: PingWorker | None = None
        self._scan_worker: RemoteScanWorker | None = None
        self._deploy_worker: DeployWorker | None = None
        self._build()
        self._reload_hosts()
        self._start_ping_timer()

    # ── Build UI ─────────────────────────────────────────────────────────
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10); lay.setContentsMargins(16, 16, 16, 16)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left — host list ──────────────────────────────────────────────
        left = QWidget()
        ll   = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0); ll.setSpacing(6)

        self._lbl_count = QLabel("Хосты (0)")
        self._lbl_count.setStyleSheet("color:#8b949e;font-size:11px;text-transform:uppercase;")
        ll.addWidget(self._lbl_count)

        self._host_list = QListWidget()
        self._host_list.currentRowChanged.connect(self._on_host_select)
        ll.addWidget(self._host_list)

        row_btns = QHBoxLayout()
        btn_add = QPushButton("+ Добавить")
        btn_add.setObjectName("secondaryBtn"); btn_add.clicked.connect(self._add_host)
        self._btn_remove = QPushButton("Удалить")
        self._btn_remove.setObjectName("secondaryBtn"); self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._remove_host)
        row_btns.addWidget(btn_add); row_btns.addWidget(self._btn_remove)
        ll.addLayout(row_btns)

        splitter.addWidget(left)

        # Right — detail + scan ─────────────────────────────────────────
        right  = QWidget()
        rl     = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(8)

        # Host info strip
        self._info_label = QLabel("Выбери хост слева")
        self._info_label.setStyleSheet("color:#8b949e;font-size:12px;padding:8px;")
        rl.addWidget(self._info_label)

        # Action buttons
        act_row = QHBoxLayout()
        self._btn_deploy = QPushButton("📦 Deploy агента")
        self._btn_deploy.setObjectName("secondaryBtn"); self._btn_deploy.setEnabled(False)
        self._btn_deploy.clicked.connect(self._deploy)
        self._btn_ping = QPushButton("⟳ Ping")
        self._btn_ping.setObjectName("secondaryBtn"); self._btn_ping.setEnabled(False)
        self._btn_ping.clicked.connect(self._ping_selected)
        self._btn_scan = QPushButton("▶ Сканировать")
        self._btn_scan.setFixedHeight(34); self._btn_scan.setEnabled(False)
        self._btn_scan.clicked.connect(self._scan)
        act_row.addWidget(self._btn_deploy)
        act_row.addWidget(self._btn_ping)
        act_row.addStretch()
        act_row.addWidget(self._btn_scan)
        rl.addLayout(act_row)

        # Scan options
        grp_opt = QGroupBox("Что сканировать")
        opt_lay = QHBoxLayout(grp_opt)
        self._chk_yara   = QCheckBox("YARA");    self._chk_yara.setChecked(True)
        self._chk_ioc    = QCheckBox("IOC");     self._chk_ioc.setChecked(True)
        self._chk_hashes = QCheckBox("Хэши файлов")
        self._path_inp   = QLineEdit(); self._path_inp.setPlaceholderText(r"C:\Users")
        self._path_inp.setText(r"C:\Users")
        opt_lay.addWidget(self._chk_yara)
        opt_lay.addWidget(self._chk_ioc)
        opt_lay.addWidget(self._chk_hashes)
        opt_lay.addWidget(QLabel("Путь:"))
        opt_lay.addWidget(self._path_inp)
        rl.addWidget(grp_opt)

        # Progress
        self._prog = QProgressBar(); self._prog.setRange(0, 0)
        self._prog.setFixedHeight(5); self._prog.setVisible(False)
        self._status = QLabel("Готов")
        self._status.setStyleSheet("color:#8b949e;font-size:11px;")
        rl.addWidget(self._prog)
        rl.addWidget(self._status)

        # Results table
        grp_res = QGroupBox("Результаты")
        res_lay = QVBoxLayout(grp_res)
        self._tbl = QTableWidget(0, 3)
        self._tbl.setHorizontalHeaderLabels(["Тип / Правило", "Severity", "Файл / Детали"])
        self._tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tbl.horizontalHeader().resizeSection(0, 180)
        self._tbl.horizontalHeader().resizeSection(1, 70)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        res_lay.addWidget(self._tbl)
        rl.addWidget(grp_res)

        splitter.addWidget(right)
        splitter.setSizes([220, 560])
        lay.addWidget(splitter)

    # ── Host list management ──────────────────────────────────────────────
    def _reload_hosts(self):
        self._host_list.clear()
        hosts = load_hosts()
        self._lbl_count.setText(f"Хосты ({len(hosts)})")
        for h in hosts:
            item = QListWidgetItem(f"🖥 {h['name']}\n{h['ip']}:{h['port']}")
            item.setData(Qt.ItemDataRole.UserRole, h)
            self._host_list.addItem(item)

    def _on_host_select(self, row: int):
        if row < 0:
            self._selected_id = None
            self._btn_remove.setEnabled(False)
            self._btn_deploy.setEnabled(False)
            self._btn_ping.setEnabled(False)
            self._btn_scan.setEnabled(False)
            self._info_label.setText("Выбери хост слева")
            return
        host = self._host_list.item(row).data(Qt.ItemDataRole.UserRole)
        self._selected_id = host["id"]
        self._btn_remove.setEnabled(True)
        self._btn_deploy.setEnabled(True)
        self._btn_ping.setEnabled(True)
        self._btn_scan.setEnabled(True)
        seen = host.get("last_seen") or "никогда"
        scan = host.get("last_scan") or "никогда"
        self._info_label.setText(
            f"<b>{host['name']}</b>  ·  {host['ip']}:{host['port']}"
            f"  ·  последний ping: {seen}  ·  последний скан: {scan}"
        )
        if self._on_host_changed:
            self._on_host_changed(host)

    def _add_host(self):
        dlg = _AddHostDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["name"]:
            QMessageBox.warning(self, "Ошибка", "IP и Имя обязательны"); return
        add_host(d["name"], d["ip"], d["port"], d["token"])
        self._reload_hosts()

    def _remove_host(self):
        if not self._selected_id:
            return
        if QMessageBox.question(self, "Удалить хост?", "Удалить этот хост из списка?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                ) != QMessageBox.StandardButton.Yes:
            return
        remove_host(self._selected_id)
        self._selected_id = None
        if self._on_host_changed:
            self._on_host_changed(None)
        self._reload_hosts()

    # ── Ping ──────────────────────────────────────────────────────────────
    def _start_ping_timer(self):
        self._ping_timer = QTimer(self)
        self._ping_timer.timeout.connect(self._ping_all)
        self._ping_timer.start(30_000)  # ping every 30 s

    def _ping_all(self):
        hosts = load_hosts()
        if not hosts:
            return
        self._ping_worker = PingWorker(hosts)
        self._ping_worker.result.connect(self._on_ping_result)
        self._ping_worker.start()

    def _ping_selected(self):
        if not self._selected_id:
            return
        hosts = [h for h in load_hosts() if h["id"] == self._selected_id]
        if hosts:
            self._ping_worker = PingWorker(hosts)
            self._ping_worker.result.connect(self._on_ping_result)
            self._ping_worker.start()

    def _on_ping_result(self, host_id: str, online: bool, info: dict):
        ts = datetime.now().strftime("%H:%M:%S")
        update_host(host_id, last_seen=ts if online else None)
        for i in range(self._host_list.count()):
            item = self._host_list.item(i)
            h    = item.data(Qt.ItemDataRole.UserRole)
            if h["id"] == host_id:
                h["last_seen"] = ts if online else None
                item.setData(Qt.ItemDataRole.UserRole, h)
                status = "● online" if online else "● offline"
                color  = QColor("#3fb950") if online else QColor("#f85149")
                item.setForeground(color)
                item.setText(f"🖥 {h['name']}\n{h['ip']}:{h['port']}  {status}")
                break

    # ── Scan ──────────────────────────────────────────────────────────────
    def _get_selected_host(self) -> dict | None:
        for i in range(self._host_list.count()):
            h = self._host_list.item(i).data(Qt.ItemDataRole.UserRole)
            if h["id"] == self._selected_id:
                return h
        return None

    def _scan(self):
        host = self._get_selected_host()
        if not host:
            return

        scan_types = []
        if self._chk_yara.isChecked():
            scan_types.append("yara")
        if self._chk_ioc.isChecked():
            scan_types.append("ioc")
        if self._chk_hashes.isChecked():
            scan_types.append("hashes")

        if not scan_types:
            self._status.setText("Выбери хотя бы один тип скана"); return

        self._btn_scan.setEnabled(False)
        self._prog.setVisible(True)
        self._tbl.setRowCount(0)

        self._scan_worker = RemoteScanWorker(
            host, scan_types, self._path_inp.text().strip(), BUILTIN_YARA_RULES
        )
        self._scan_worker.progress.connect(self._status.setText)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.finished.connect(lambda: (
            self._btn_scan.setEnabled(True), self._prog.setVisible(False)
        ))
        self._scan_worker.start()

        update_host(host["id"], last_scan=datetime.now().strftime("%H:%M:%S"))
        self._reload_hosts()

    def _on_scan_done(self, results: list):
        colors = {
            "YARA": "#58a6ff", "IOC": "#d29922", "HASH": "#8b949e",
        }
        sev_map = {
            "critical": "#f85149", "high": "#d29922",
            "medium":   "#58a6ff", "low":  "#3fb950",
        }
        self._tbl.setRowCount(len(results))
        for i, r in enumerate(results):
            typ  = r.get("type", "?")
            rule = r.get("rule", "?")
            fil  = r.get("file", "?")
            col  = colors.get(typ, "#8b949e")

            ri = QTableWidgetItem(f"[{typ}] {rule}")
            si = QTableWidgetItem(typ)
            fi = QTableWidgetItem(fil)
            ri.setForeground(QColor(col))
            si.setForeground(QColor(col))
            for it in (ri, si, fi):
                it.setFont(QFont("Consolas", 11))
            self._tbl.setItem(i, 0, ri)
            self._tbl.setItem(i, 1, si)
            self._tbl.setItem(i, 2, fi)

        hits = len([r for r in results if r.get("type") in ("YARA", "IOC")])
        self._status.setText(f"Найдено: {hits} | Всего записей: {len(results)}")

    def _on_scan_error(self, msg: str):
        self._status.setText(f"✘ Ошибка: {msg}")

    # ── Deploy ────────────────────────────────────────────────────────────
    def _deploy(self):
        dlg = _DeployDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["username"]:
            QMessageBox.warning(self, "Ошибка", "IP и пользователь обязательны"); return

        self._btn_deploy.setEnabled(False)
        self._prog.setVisible(True)
        self._status.setText("Деплой агента...")

        self._deploy_worker = DeployWorker(d["ip"], d["username"], d["password"])
        self._deploy_worker.progress.connect(self._status.setText)
        self._deploy_worker.error.connect(self._on_deploy_error)
        self._deploy_worker.done.connect(lambda tok: self._on_deploy_done(d["ip"], tok))
        self._deploy_worker.finished.connect(lambda: (
            self._btn_deploy.setEnabled(True), self._prog.setVisible(False)
        ))
        self._deploy_worker.start()

    def _on_deploy_done(self, ip: str, token: str):
        self._status.setText(f"✔ Агент задеплоен на {ip}. Токен получен.")
        QMessageBox.information(
            self, "Деплой завершён",
            f"Агент установлен на {ip}\n\nТокен:\n{token}\n\n"
            "Нажми '+ Добавить' и введи этот токен для добавления хоста."
        )

    def _on_deploy_error(self, msg: str):
        self._status.setText(f"✘ Деплой: {msg}")
        QMessageBox.warning(self, "Ошибка деплоя", msg)
```

- [ ] **Step 2: Commit**

```
git add ui/hosts_tab.py
git commit -m "feat: add HostsTab UI with deploy/ping/scan"
```

---

## Task 6: Wire up — main_window.py host selector

**Files:**
- Modify: `ui/main_window.py`

- [ ] **Step 1: Open ui/main_window.py and apply these changes**

Add imports at the top (after existing imports):
```python
from PyQt6.QtWidgets import QComboBox
from ui.hosts_tab import HostsTab
import core.host_state as host_state
from core.hosts_config import load_hosts
```

Replace the `# Tabs` section in `__init__` — add HostsTab and host selector:

```python
        # Tabs
        tabs = QTabWidget()
        tabs.setContentsMargins(12, 12, 12, 12)
        self.dash_tab = DashboardTab()
        self._hosts_tab = HostsTab(on_host_changed=self._on_host_changed)
        tabs.addTab(self.dash_tab,        "  Dashboard  ")
        tabs.addTab(HashTab(),            "  Hash Lookup  ")
        tabs.addTab(IOCTab(),             "  IOC Collection  ")
        tabs.addTab(YARATab(),            "  YARA Scanner  ")
        tabs.addTab(NetIntelTab(),        "  Network Intel  ")
        tabs.addTab(AITab(),              "  AI Assistant  ")
        tabs.addTab(ReportTab(),          "  Report Builder  ")
        self.mem_tab = MemoryScannerTab()
        tabs.addTab(self.mem_tab,         "  Memory Scan  ")
        self.quarantine_tab = QuarantineTab()
        tabs.addTab(self.quarantine_tab,  "  Quarantine  ")
        tabs.addTab(SettingsTab(),        "  Settings  ")
        tabs.addTab(self._hosts_tab,      "  🌐 Hosts  ")
        ml.addWidget(tabs)
```

Add `self._host_combo` to the header section (after the `s` subtitle label):
```python
        self._host_combo = QComboBox()
        self._host_combo.setFixedWidth(200)
        self._host_combo.setStyleSheet(
            "QComboBox{background:#0d1117;color:#58a6ff;border:1px solid #30363d;"
            "border-radius:4px;padding:2px 8px;font-size:12px;}"
        )
        self._host_combo.currentIndexChanged.connect(self._combo_changed)
        hl.addWidget(self._host_combo)
        self._refresh_host_combo()
```

Add these two methods to `MainWindow`:
```python
    def _refresh_host_combo(self):
        self._host_combo.blockSignals(True)
        self._host_combo.clear()
        self._host_combo.addItem("🖥  Local", None)
        for h in load_hosts():
            self._host_combo.addItem(f"🌐  {h['name']}  ({h['ip']})", h)
        self._host_combo.blockSignals(False)

    def _combo_changed(self, idx: int):
        h = self._host_combo.itemData(idx)
        host_state.set_current_host(h)

    def _on_host_changed(self, host):
        # Called when user selects a host inside HostsTab
        host_state.set_current_host(host)
        self._refresh_host_combo()
        # Select matching combo item
        self._host_combo.blockSignals(True)
        for i in range(self._host_combo.count()):
            d = self._host_combo.itemData(i)
            if (host is None and d is None) or (d and host and d.get("id") == host.get("id")):
                self._host_combo.setCurrentIndex(i)
                break
        self._host_combo.blockSignals(False)
```

- [ ] **Step 2: Update requirements.txt**

Add these lines to `requirements.txt`:
```
requests>=2.31
urllib3>=2.0
pywinrm>=0.4.3
```

- [ ] **Step 3: Install new dependencies**

```
pip install requests urllib3 pywinrm
```

- [ ] **Step 4: Start the app and verify the Hosts tab appears**

```
cd C:\Users\User\Documents\project\ioc_analyzer_v2
python main.py
```

Expected: App starts, last tab is "🌐 Hosts", header has a host selector dropdown showing "🖥 Local".

- [ ] **Step 5: Smoke-test add host flow**

1. Click "+ Добавить" in the Hosts tab
2. Enter: Name=TEST, IP=127.0.0.1, Port=5555, Token=(leave blank)
3. Click OK → host appears in the list
4. Click "⟳ Ping" → status changes to offline (no agent running yet)
5. Start the agent in another terminal: `cd agent && python agent.py`
6. Click "⟳ Ping" again → status turns green "● online"
7. Click "▶ Сканировать" → results appear in the table

- [ ] **Step 6: Commit**

```
git add ui/main_window.py requirements.txt
git commit -m "feat: wire HostsTab into main window with host selector in header"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Agent HTTPS port 5555 + self-signed cert | Task 3: `_generate_cert()`, `ssl.SSLContext` |
| API token auth | Task 3: `_auth` decorator, `_load_token()` |
| Windows Service install/uninstall | Task 3: `_run_as_service()` |
| Agent endpoints: ping, info, yara, ioc, memory, hashes | Task 3: all six routes |
| hosts.json persistence | Task 1: `hosts_config.py` |
| AgentClient HTTP wrapper | Task 2: `agent_client.py` |
| PingWorker, RemoteScanWorker, DeployWorker | Task 4: `host_worker.py` |
| HostsTab UI (add/remove/ping/scan/deploy) | Task 5: `hosts_tab.py` |
| Host selector in main window header | Task 6: `_host_combo`, `host_state` |
| Deploy via WinRM | Task 4: `DeployWorker` |
| global host_state singleton | Task 1: `host_state.py` |

**No gaps found.**
