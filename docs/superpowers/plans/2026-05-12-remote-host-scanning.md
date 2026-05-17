# Remote Host Scanning — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add remote YARA file-scan rule selector + full remote Memory Scan (process list → rule picker → YARA) to the Hosts tab, route results to Dashboard and Report, fix 10 s timeout.

**Architecture:** New `/scan/memory/all` agent endpoint iterates all processes and runs YARA on each exe in a single HTTP call. HostsTab right panel becomes a QTabWidget with File Scan and Memory Scan sub-tabs that mirror the local YARA and MemoryScanner tabs. Both scan types log events to `DashboardTab.stats` with a `host` field; Dashboard shows a new "Удалённые сканы" table; Report adds a grouped section.

**Tech Stack:** Python 3.13, PyQt6, Flask (agent), psutil, requests, pytest

---

## File Map

| File | Change |
|------|--------|
| `agent/agent.py` | + `/scan/memory/all` endpoint |
| `core/agent_client.py` | + `scan_memory_all()` method |
| `workers/host_worker.py` | timeout 120 s on RemoteScanWorker, + `RemoteProcessListWorker`, + `RemoteMemScanWorker` |
| `ui/hosts_tab.py` | full right-panel rework: QTabWidget with File Scan / Memory Scan tabs |
| `ui/dashboard_tab.py` | `host` param in `log_event`, + "Удалённые сканы" table |
| `ui/report_tab.py` | `remote_events` in `_collect_data`, + TXT/HTML section |
| `tests/test_host_worker.py` | new: tests for `RemoteProcessListWorker` and `RemoteMemScanWorker` |
| `tests/test_agent_client.py` | + test for `scan_memory_all` |

---

### Task 1: Agent — `/scan/memory/all` endpoint

**Files:**
- Modify: `agent/agent.py`

- [ ] **Step 1: Add endpoint** — insert after the closing brace of the `scan_memory` route (after line 285):

```python
@app.route("/scan/memory/all", methods=["POST"])
@_auth
def scan_memory_all():
    data       = request.json or {}
    rules_dict = data.get("rules", {})

    if not rules_dict:
        return jsonify({"error": "no rules"}), 400
    if not YARA_EXE:
        return jsonify({"error": "yara64.exe not found on agent"}), 400

    processes = []
    for p in psutil.process_iter(["pid", "name", "exe"]):
        try:
            exe = p.info.get("exe") or ""
            if exe and os.path.isfile(exe):
                processes.append({
                    "pid":  p.info["pid"],
                    "name": p.info["name"],
                    "exe":  exe,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    matches = []
    for proc in processes:
        for rule_name, rule_text in rules_dict.items():
            tmp_path = None
            try:
                fd, tmp_path = tempfile.mkstemp(suffix=".yar")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(rule_text)
                r = subprocess.run(
                    [YARA_EXE, tmp_path, proc["exe"]],
                    capture_output=True, text=True, timeout=15,
                    encoding="utf-8", errors="replace",
                )
                for line in r.stdout.strip().splitlines():
                    line = line.strip()
                    if line and " " in line:
                        parts = line.split(" ", 1)
                        matches.append({
                            "rule":         parts[0],
                            "file":         parts[1],
                            "pid":          proc["pid"],
                            "process_name": proc["name"],
                        })
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

    return jsonify({"matches": matches})
```

- [ ] **Step 2: Commit**

```bash
git add agent/agent.py
git commit -m "feat(agent): add /scan/memory/all endpoint"
```

---

### Task 2: AgentClient — `scan_memory_all` method + test

**Files:**
- Modify: `core/agent_client.py`
- Modify: `tests/test_agent_client.py`

- [ ] **Step 1: Write failing test** — add to `tests/test_agent_client.py`:

```python
from unittest.mock import MagicMock, patch

def test_scan_memory_all_returns_matches():
    from core.agent_client import AgentClient
    client = AgentClient("127.0.0.1", 5555, "tok")
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "matches": [{"rule": "Mimikatz_Generic", "file": "C:\\lsass.exe",
                     "pid": 800, "process_name": "lsass.exe"}]
    }
    fake_resp.raise_for_status = MagicMock()
    with patch("requests.post", return_value=fake_resp):
        result = client.scan_memory_all({"Mimikatz": "rule Mimikatz_Generic { condition: false }"})
    assert result["matches"][0]["rule"] == "Mimikatz_Generic"
    assert result["matches"][0]["pid"] == 800
```

- [ ] **Step 2: Run — expect FAIL**

```bash
python -m pytest tests/test_agent_client.py::test_scan_memory_all_returns_matches -v
```

Expected: `FAILED` — `AttributeError: 'AgentClient' object has no attribute 'scan_memory_all'`

- [ ] **Step 3: Add method** — append after `list_processes` in `core/agent_client.py`:

```python
    def scan_memory_all(self, rules: dict) -> dict:
        return self._post("/scan/memory/all", {"rules": rules})
```

- [ ] **Step 4: Run — expect PASS**

```bash
python -m pytest tests/test_agent_client.py::test_scan_memory_all_returns_matches -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add core/agent_client.py tests/test_agent_client.py
git commit -m "feat(client): add scan_memory_all method"
```

---

### Task 3: Workers — timeout fix + two new workers

**Files:**
- Modify: `workers/host_worker.py`
- Create: `tests/test_host_worker.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_host_worker.py`:

```python
from unittest.mock import MagicMock, patch

FAKE_HOST = {"id": "1", "ip": "127.0.0.1", "port": 5555, "token": "tok",
             "name": "TestHost", "last_seen": None, "last_scan": None}


def test_remote_process_list_worker_emits_processes():
    from workers.host_worker import RemoteProcessListWorker
    worker = RemoteProcessListWorker(FAKE_HOST)
    received = []
    worker.done.connect(lambda procs: received.extend(procs))

    fake_client = MagicMock()
    fake_client.list_processes.return_value = {
        "processes": [{"pid": 1, "name": "test.exe", "exe": "C:\\test.exe"}]
    }
    with patch("workers.host_worker.AgentClient", return_value=fake_client):
        worker.run()

    assert len(received) == 1
    assert received[0]["name"] == "test.exe"


def test_remote_mem_scan_worker_emits_results():
    from workers.host_worker import RemoteMemScanWorker
    rules = {"Mimikatz": "rule Mimikatz_Generic { condition: false }"}
    worker = RemoteMemScanWorker(FAKE_HOST, rules)
    results = []
    worker.done.connect(lambda r: results.extend(r))

    fake_client = MagicMock()
    fake_client.scan_memory_all.return_value = {
        "matches": [{"rule": "Mimikatz_Generic", "file": "C:\\lsass.exe",
                     "pid": 800, "process_name": "lsass.exe"}]
    }
    with patch("workers.host_worker.AgentClient", return_value=fake_client):
        worker.run()

    assert len(results) == 1
    assert results[0]["type"] == "MEMORY"
    assert results[0]["rule"] == "Mimikatz_Generic"
    assert results[0]["process_name"] == "lsass.exe"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
python -m pytest tests/test_host_worker.py -v
```

Expected: `ImportError: cannot import name 'RemoteProcessListWorker'`

- [ ] **Step 3: Fix timeout in `RemoteScanWorker.run()`** — find:

```python
client = AgentClient(self._host["ip"], self._host["port"], self._host["token"])
```

Replace with:

```python
client = AgentClient(self._host["ip"], self._host["port"], self._host["token"], timeout=120)
```

- [ ] **Step 4: Add `RemoteProcessListWorker`** — append after `RemoteScanWorker` class:

```python
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
```

- [ ] **Step 5: Add `RemoteMemScanWorker`** — append after `RemoteProcessListWorker`:

```python
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
```

- [ ] **Step 6: Run — expect PASS**

```bash
python -m pytest tests/test_host_worker.py -v
```

Expected: both tests `PASSED`

- [ ] **Step 7: Commit**

```bash
git add workers/host_worker.py tests/test_host_worker.py
git commit -m "feat(workers): fix timeout 120s, add RemoteProcessListWorker + RemoteMemScanWorker"
```

---

### Task 4: HostsTab — complete rework

**Files:**
- Modify: `ui/hosts_tab.py`

- [ ] **Step 1: Update imports** — replace the existing import block at the top of `hosts_tab.py` with:

```python
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QListWidget,
    QListWidgetItem, QCheckBox, QSplitter, QLineEdit, QDialog, QFormLayout,
    QDialogButtonBox, QMessageBox, QSpinBox, QTabWidget, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from core.hosts_config import load_hosts, add_host, remove_host, update_host
from workers.host_worker import (
    PingWorker, RemoteScanWorker, DeployWorker,
    RemoteProcessListWorker, RemoteMemScanWorker,
)
from constants import BUILTIN_YARA_RULES
from core.i18n import t
from core.lang_signal import lang_signal
from ui.dashboard_tab import DashboardTab
from datetime import datetime
```

- [ ] **Step 2: Update `__init__`** — add new instance variables after `self._deploy_worker`:

```python
        self._proc_worker: RemoteProcessListWorker | None = None
        self._mem_worker:  RemoteMemScanWorker | None = None
        self._file_custom_rules: dict = {}
        self._mem_custom_rules:  dict = {}
        self._remote_procs: list = []
```

- [ ] **Step 3: Replace right panel in `_build()`**

Remove everything from `splitter.addWidget(left)` to `splitter.setSizes(...)` (inclusive of what's between them), and insert:

```python
        splitter.addWidget(left)

        # ── Right panel ──────────────────────────────────────────────
        right = QWidget()
        rl    = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        self._info_label = QLabel(t("hosts_select_hint"))
        self._info_label.setStyleSheet("color:#8b949e;font-size:12px;padding:8px;")
        rl.addWidget(self._info_label)

        act_row = QHBoxLayout()
        self._btn_deploy = QPushButton(t("hosts_deploy_btn"))
        self._btn_deploy.setObjectName("secondaryBtn")
        self._btn_deploy.setEnabled(False)
        self._btn_deploy.clicked.connect(self._deploy)
        self._btn_ping = QPushButton(t("hosts_ping_btn"))
        self._btn_ping.setObjectName("secondaryBtn")
        self._btn_ping.setEnabled(False)
        self._btn_ping.clicked.connect(self._ping_selected)
        act_row.addWidget(self._btn_deploy)
        act_row.addWidget(self._btn_ping)
        act_row.addStretch()
        rl.addLayout(act_row)

        self._sub_tabs = QTabWidget()
        self._sub_tabs.setEnabled(False)
        self._sub_tabs.addTab(self._build_file_tab(),   "Файловый скан")
        self._sub_tabs.addTab(self._build_memory_tab(), "Memory Scan")
        rl.addWidget(self._sub_tabs)

        self._grp_res = QGroupBox(t("hosts_results"))
        res_lay = QVBoxLayout(self._grp_res)
        self._tbl = QTableWidget(0, 3)
        self._tbl.setHorizontalHeaderLabels([
            t("hosts_tbl_type"), "Severity", t("hosts_tbl_file")
        ])
        self._tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tbl.horizontalHeader().resizeSection(0, 180)
        self._tbl.horizontalHeader().resizeSection(1, 70)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        res_lay.addWidget(self._tbl)
        rl.addWidget(self._grp_res)

        splitter.addWidget(right)
        splitter.setSizes([220, 560])
        lay.addWidget(splitter)
```

- [ ] **Step 4: Add `_build_file_tab()` method** — add as a new method of `HostsTab`:

```python
    def _build_file_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        grp_rules = QGroupBox("YARA правила")
        gr = QVBoxLayout(grp_rules)
        self._file_rule_list = QListWidget()
        self._file_rule_list.setMaximumHeight(130)
        for name in BUILTIN_YARA_RULES:
            item = QListWidgetItem(name)
            item.setCheckState(Qt.CheckState.Checked)
            self._file_rule_list.addItem(item)
        btn_row_f = QHBoxLayout()
        btn_all_f  = QPushButton("Все");    btn_all_f.setObjectName("secondaryBtn")
        btn_none_f = QPushButton("Ничего"); btn_none_f.setObjectName("secondaryBtn")
        btn_all_f.clicked.connect(lambda: self._toggle_rules(self._file_rule_list, True))
        btn_none_f.clicked.connect(lambda: self._toggle_rules(self._file_rule_list, False))
        btn_row_f.addWidget(btn_all_f); btn_row_f.addWidget(btn_none_f); btn_row_f.addStretch()
        gr.addLayout(btn_row_f)
        gr.addWidget(self._file_rule_list)

        grp_custom_f = QGroupBox("Своё правило")
        gc_f = QVBoxLayout(grp_custom_f)
        self._file_rule_edit = QTextEdit()
        self._file_rule_edit.setMaximumHeight(70)
        self._file_rule_edit.setPlaceholderText(
            'rule MyRule {\n  strings: $s = "evil"\n  condition: $s\n}')
        btn_add_f = QPushButton("Добавить правило"); btn_add_f.setObjectName("secondaryBtn")
        btn_add_f.clicked.connect(lambda: self._add_custom_rule(
            self._file_rule_edit, self._file_rule_list, self._file_custom_rules))
        gc_f.addWidget(self._file_rule_edit); gc_f.addWidget(btn_add_f)
        gr.addWidget(grp_custom_f)
        lay.addWidget(grp_rules)

        opt_row = QHBoxLayout()
        self._chk_ioc    = QCheckBox("IOC");   self._chk_ioc.setChecked(True)
        self._chk_hashes = QCheckBox(t("hosts_hashes_chk"))
        self._lbl_path   = QLabel(t("hosts_path_label"))
        self._path_inp   = QLineEdit(); self._path_inp.setText(r"C:\Users")
        opt_row.addWidget(self._chk_ioc)
        opt_row.addWidget(self._chk_hashes)
        opt_row.addWidget(self._lbl_path)
        opt_row.addWidget(self._path_inp)
        lay.addLayout(opt_row)

        self._file_prog = QProgressBar()
        self._file_prog.setRange(0, 0); self._file_prog.setFixedHeight(5)
        self._file_prog.setVisible(False)
        self._file_status = QLabel(t("hosts_ready"))
        self._file_status.setStyleSheet("color:#8b949e;font-size:11px;")
        lay.addWidget(self._file_prog)
        lay.addWidget(self._file_status)

        self._btn_scan = QPushButton(t("hosts_scan_btn"))
        self._btn_scan.setFixedHeight(34)
        self._btn_scan.clicked.connect(self._start_file_scan)
        lay.addWidget(self._btn_scan)
        return w
```

- [ ] **Step 5: Add `_build_memory_tab()` method**:

```python
    def _build_memory_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        top_row = QHBoxLayout()
        self._btn_refresh_procs = QPushButton("Обновить процессы")
        self._btn_refresh_procs.setObjectName("secondaryBtn")
        self._btn_refresh_procs.clicked.connect(self._refresh_remote_procs)
        self._mem_filter = QLineEdit(); self._mem_filter.setPlaceholderText("Фильтр по имени...")
        self._mem_filter.textChanged.connect(self._filter_remote_procs)
        self._mem_proc_count = QLabel("Процессов: 0")
        self._mem_proc_count.setStyleSheet("color:#6e7681;font-size:11px;")
        top_row.addWidget(self._btn_refresh_procs)
        top_row.addWidget(self._mem_filter)
        top_row.addWidget(self._mem_proc_count)
        lay.addLayout(top_row)

        grp_procs = QGroupBox("Процессы удалённого хоста (только для справки)")
        gp = QVBoxLayout(grp_procs)
        self._mem_proc_tbl = QTableWidget(0, 3)
        self._mem_proc_tbl.setHorizontalHeaderLabels(["PID", "Имя", "Exe"])
        self._mem_proc_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._mem_proc_tbl.horizontalHeader().resizeSection(0, 55)
        self._mem_proc_tbl.horizontalHeader().resizeSection(1, 140)
        self._mem_proc_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._mem_proc_tbl.setMaximumHeight(130)
        gp.addWidget(self._mem_proc_tbl)
        lay.addWidget(grp_procs)

        grp_rules_m = QGroupBox("YARA правила")
        gr_m = QVBoxLayout(grp_rules_m)
        self._mem_rule_list = QListWidget()
        self._mem_rule_list.setMaximumHeight(100)
        for name in BUILTIN_YARA_RULES:
            item = QListWidgetItem(name)
            item.setCheckState(Qt.CheckState.Checked)
            self._mem_rule_list.addItem(item)
        btn_row_m = QHBoxLayout()
        btn_all_m  = QPushButton("Все");    btn_all_m.setObjectName("secondaryBtn")
        btn_none_m = QPushButton("Ничего"); btn_none_m.setObjectName("secondaryBtn")
        btn_all_m.clicked.connect(lambda: self._toggle_rules(self._mem_rule_list, True))
        btn_none_m.clicked.connect(lambda: self._toggle_rules(self._mem_rule_list, False))
        btn_row_m.addWidget(btn_all_m); btn_row_m.addWidget(btn_none_m); btn_row_m.addStretch()
        gr_m.addLayout(btn_row_m)
        gr_m.addWidget(self._mem_rule_list)

        grp_custom_m = QGroupBox("Своё правило")
        gc_m = QVBoxLayout(grp_custom_m)
        self._mem_rule_edit = QTextEdit()
        self._mem_rule_edit.setMaximumHeight(65)
        self._mem_rule_edit.setPlaceholderText(
            'rule MyRule {\n  strings: $s = "evil"\n  condition: $s\n}')
        btn_add_m = QPushButton("Добавить правило"); btn_add_m.setObjectName("secondaryBtn")
        btn_add_m.clicked.connect(lambda: self._add_custom_rule(
            self._mem_rule_edit, self._mem_rule_list, self._mem_custom_rules))
        gc_m.addWidget(self._mem_rule_edit); gc_m.addWidget(btn_add_m)
        gr_m.addWidget(grp_custom_m)
        lay.addWidget(grp_rules_m)

        self._mem_prog = QProgressBar()
        self._mem_prog.setRange(0, 0); self._mem_prog.setFixedHeight(5)
        self._mem_prog.setVisible(False)
        self._mem_status = QLabel("Нажми «Обновить процессы», затем «Scan Memory»")
        self._mem_status.setStyleSheet("color:#8b949e;font-size:11px;")
        lay.addWidget(self._mem_prog)
        lay.addWidget(self._mem_status)

        scan_row = QHBoxLayout()
        self._btn_mem_scan = QPushButton("Scan Memory")
        self._btn_mem_scan.setFixedHeight(34)
        self._btn_mem_scan.clicked.connect(self._start_mem_scan)
        self._btn_mem_stop = QPushButton("Стоп")
        self._btn_mem_stop.setObjectName("dangerBtn")
        self._btn_mem_stop.setFixedWidth(70)
        self._btn_mem_stop.setEnabled(False)
        self._btn_mem_stop.clicked.connect(self._stop_mem_scan)
        scan_row.addWidget(self._btn_mem_scan); scan_row.addWidget(self._btn_mem_stop)
        lay.addLayout(scan_row)
        return w
```

- [ ] **Step 6: Add shared helper methods**:

```python
    @staticmethod
    def _toggle_rules(rule_list: QListWidget, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(rule_list.count()):
            rule_list.item(i).setCheckState(state)

    @staticmethod
    def _get_selected_rules(rule_list: QListWidget, custom_rules: dict) -> dict:
        selected = {}
        for i in range(rule_list.count()):
            item = rule_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                name = item.text()
                if name in BUILTIN_YARA_RULES:
                    selected[name] = BUILTIN_YARA_RULES[name]
                elif name in custom_rules:
                    selected[name] = custom_rules[name]
        return selected

    def _add_custom_rule(self, text_edit: QTextEdit,
                         rule_list: QListWidget, custom_store: dict) -> None:
        text = text_edit.toPlainText().strip()
        if not text:
            return
        m = re.search(r'rule\s+(\w+)', text)
        name = m.group(1) if m else f"Custom_{len(custom_store) + 1}"
        custom_store[name] = text
        item = QListWidgetItem(name)
        item.setCheckState(Qt.CheckState.Checked)
        item.setForeground(QColor("#58a6ff"))
        rule_list.addItem(item)
        text_edit.clear()
```

- [ ] **Step 7: Replace `_on_host_select()`** — find the existing method and replace it entirely:

```python
    def _on_host_select(self, row: int):
        if row < 0:
            self._selected_id = None
            self._btn_remove.setEnabled(False)
            self._btn_deploy.setEnabled(False)
            self._btn_ping.setEnabled(False)
            self._sub_tabs.setEnabled(False)
            self._info_label.setText(t("hosts_select_hint"))
            return
        host = self._host_list.item(row).data(Qt.ItemDataRole.UserRole)
        self._selected_id = host["id"]
        self._btn_remove.setEnabled(True)
        self._btn_deploy.setEnabled(True)
        self._btn_ping.setEnabled(True)
        self._sub_tabs.setEnabled(True)
        seen = host.get("last_seen") or t("hosts_never")
        scan = host.get("last_scan") or t("hosts_never")
        self._info_label.setText(
            f"<b>{host['name']}</b>  ·  {host['ip']}:{host['port']}"
            f"  ·  {t('hosts_last_ping')} {seen}  ·  {t('hosts_last_scan')} {scan}"
        )
        if self._on_host_changed:
            self._on_host_changed(host)
```

- [ ] **Step 8: Add file scan method** — replace old `_scan()` method with:

```python
    def _start_file_scan(self):
        host = self._get_selected_host()
        if not host:
            return
        if self._scan_worker is not None and self._scan_worker.isRunning():
            self._file_status.setText(t("hosts_already_running"))
            return

        rules     = self._get_selected_rules(self._file_rule_list, self._file_custom_rules)
        scan_types = []
        if rules:
            scan_types.append("yara")
        if self._chk_ioc.isChecked():
            scan_types.append("ioc")
        if self._chk_hashes.isChecked():
            scan_types.append("hashes")

        if not scan_types:
            self._file_status.setText(t("hosts_no_scan_type"))
            return

        path = self._path_inp.text().strip()
        if not path:
            self._file_status.setText(t("hosts_no_path"))
            return

        self._btn_scan.setEnabled(False)
        self._file_prog.setVisible(True)
        self._tbl.setRowCount(0)

        self._scan_worker = RemoteScanWorker(host, scan_types, path, rules)
        self._scan_worker.progress.connect(self._file_status.setText)
        self._scan_worker.done.connect(lambda r: self._on_results_done(r, host))
        self._scan_worker.error.connect(lambda m: self._file_status.setText(t("hosts_error", msg=m)))
        self._scan_worker.finished.connect(lambda: (
            self._btn_scan.setEnabled(True), self._file_prog.setVisible(False)
        ))
        self._scan_worker.start()
        update_host(host["id"], last_scan=datetime.now().strftime("%H:%M:%S"))
```

- [ ] **Step 9: Add memory scan methods**:

```python
    def _refresh_remote_procs(self):
        host = self._get_selected_host()
        if not host or (self._proc_worker and self._proc_worker.isRunning()):
            return
        self._btn_refresh_procs.setEnabled(False)
        self._mem_status.setText("Загрузка процессов...")
        self._proc_worker = RemoteProcessListWorker(host)
        self._proc_worker.done.connect(self._on_procs_loaded)
        self._proc_worker.error.connect(lambda e: self._mem_status.setText(f"Ошибка: {e}"))
        self._proc_worker.finished.connect(lambda: self._btn_refresh_procs.setEnabled(True))
        self._proc_worker.start()

    def _on_procs_loaded(self, procs: list):
        self._remote_procs = procs
        self._render_remote_procs(procs)
        self._mem_status.setText(f"Загружено процессов: {len(procs)}")

    def _render_remote_procs(self, procs: list):
        self._mem_proc_tbl.setRowCount(0)
        for p in procs:
            row = self._mem_proc_tbl.rowCount()
            self._mem_proc_tbl.insertRow(row)
            for i, txt in enumerate([str(p.get("pid","")),
                                      p.get("name",""), p.get("exe","")]):
                item = QTableWidgetItem(txt)
                item.setFont(QFont("Consolas", 10))
                self._mem_proc_tbl.setItem(row, i, item)
        self._mem_proc_count.setText(f"Процессов: {len(procs)}")

    def _filter_remote_procs(self, text: str):
        text = text.lower()
        filtered = [p for p in self._remote_procs
                    if not text or text in p.get("name", "").lower()]
        self._render_remote_procs(filtered)

    def _start_mem_scan(self):
        host = self._get_selected_host()
        if not host:
            return
        if self._mem_worker is not None and self._mem_worker.isRunning():
            self._mem_status.setText("Сканирование уже запущено")
            return
        rules = self._get_selected_rules(self._mem_rule_list, self._mem_custom_rules)
        if not rules:
            self._mem_status.setText("Выбери хотя бы одно правило")
            return

        self._btn_mem_scan.setEnabled(False)
        self._btn_mem_stop.setEnabled(True)
        self._mem_prog.setVisible(True)
        self._tbl.setRowCount(0)

        self._mem_worker = RemoteMemScanWorker(host, rules)
        self._mem_worker.progress.connect(self._mem_status.setText)
        self._mem_worker.done.connect(lambda r: self._on_results_done(r, host))
        self._mem_worker.error.connect(lambda m: self._mem_status.setText(f"Ошибка: {m}"))
        self._mem_worker.finished.connect(lambda: (
            self._btn_mem_scan.setEnabled(True),
            self._btn_mem_stop.setEnabled(False),
            self._mem_prog.setVisible(False),
        ))
        self._mem_worker.start()

    def _stop_mem_scan(self):
        if self._mem_worker:
            self._mem_worker.stop()
        self._btn_mem_stop.setEnabled(False)
        self._mem_status.setText("Остановлено пользователем")
```

- [ ] **Step 10: Add shared result handler** — replace old `_on_scan_done` and `_on_scan_error` with:

```python
    def _on_results_done(self, results: list, host: dict):
        host_label = f"{host['name']} ({host['ip']})"
        colors = {"YARA": "#58a6ff", "IOC": "#d29922",
                  "HASH": "#8b949e", "MEMORY": "#a371f7"}
        self._tbl.setRowCount(len(results))
        for i, r in enumerate(results):
            typ  = r.get("type", "?")
            rule = r.get("rule", "?")
            proc = r.get("process_name", "")
            fil  = f"[{proc}] {r.get('file','?')}" if proc else r.get("file", "?")
            col  = colors.get(typ, "#8b949e")
            ri   = QTableWidgetItem(f"[{typ}] {rule}")
            si   = QTableWidgetItem(r.get("severity", typ))
            fi   = QTableWidgetItem(fil)
            ri.setForeground(QColor(col)); si.setForeground(QColor(col))
            for it in (ri, si, fi):
                it.setFont(QFont("Consolas", 11))
            self._tbl.setItem(i, 0, ri)
            self._tbl.setItem(i, 1, si)
            self._tbl.setItem(i, 2, fi)
            DashboardTab.log_event(
                typ, f"{rule} — {fil}",
                level="high", severity=r.get("severity", typ),
                scan=True, target=fil[:60], host=host_label,
            )

        yara_hits = sum(1 for r in results if r.get("type") in ("YARA", "MEMORY"))
        sus_procs = sum(1 for r in results if r.get("type") == "IOC")
        DashboardTab.stats["yara_hits"]       += yara_hits
        DashboardTab.stats["suspicious_procs"] += sus_procs

        hits = len([r for r in results if r.get("type") in ("YARA", "IOC", "MEMORY")])
        msg  = t("hosts_found", hits=hits, total=len(results))
        self._file_status.setText(msg)
        self._mem_status.setText(msg)
```

- [ ] **Step 11: Update `retranslate()` method** — find the existing `retranslate` method and replace:

```python
    def retranslate(self, _lang: str = ""):
        self._btn_add.setText(t("hosts_add_btn"))
        self._btn_remove.setText(t("hosts_remove_btn"))
        self._btn_deploy.setText(t("hosts_deploy_btn"))
        self._btn_ping.setText(t("hosts_ping_btn"))
        self._btn_scan.setText(t("hosts_scan_btn"))
        self._chk_hashes.setText(t("hosts_hashes_chk"))
        self._lbl_path.setText(t("hosts_path_label"))
        self._grp_res.setTitle(t("hosts_results"))
        self._tbl.setHorizontalHeaderLabels([
            t("hosts_tbl_type"), "Severity", t("hosts_tbl_file")
        ])
        if self._file_status.text() in ("Готов", "Ready", "Дайын", t("hosts_ready")):
            self._file_status.setText(t("hosts_ready"))
        if self._info_label.text() in (
            "Выбери хост слева", "Select a host on the left", "Сол жақтан хостты таңдаңыз",
            t("hosts_select_hint"),
        ):
            self._info_label.setText(t("hosts_select_hint"))
        self._reload_hosts()
```

- [ ] **Step 12: Verify the app starts**

```bash
python main.py
```

Go to Hosts tab — verify two sub-tabs appear, sub-tabs are disabled until a host is selected, File Scan tab has rule list and custom rule editor, Memory Scan tab has process table + rule list.

- [ ] **Step 13: Commit**

```bash
git add ui/hosts_tab.py
git commit -m "feat(hosts): sub-tabs with file scan rule selector and memory scan panel"
```

---

### Task 5: DashboardTab — `host` field + Remote Scans table

**Files:**
- Modify: `ui/dashboard_tab.py`

- [ ] **Step 1: Update `log_event`** — find the static method and replace:

```python
    @staticmethod
    def log_event(type_, msg, level="info", severity="", target="", scan=False, host=""):
        import datetime
        DashboardTab.stats["recent"].append({
            "time":     datetime.datetime.now().strftime("%H:%M:%S"),
            "type":     type_,
            "msg":      msg,
            "level":    level,
            "severity": severity,
            "target":   target,
            "scan":     scan,
            "host":     host,
        })
        if len(DashboardTab.stats["recent"]) > 200:
            DashboardTab.stats["recent"] = DashboardTab.stats["recent"][-200:]
```

- [ ] **Step 2: Add Remote Scans group in `_build()`** — append after `lay.addWidget(grp_tbl)`:

```python
        grp_remote = QGroupBox("Удалённые сканы")
        gr_rem = QVBoxLayout(grp_remote)
        self.remote_tbl = QTableWidget(0, 4)
        self.remote_tbl.setHorizontalHeaderLabels(
            ["Время", "Хост", "Тип", "Правило / Файл"])
        self.remote_tbl.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        self.remote_tbl.horizontalHeader().resizeSection(0, 70)
        self.remote_tbl.horizontalHeader().resizeSection(1, 160)
        self.remote_tbl.horizontalHeader().resizeSection(2, 80)
        self.remote_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.remote_tbl.setMaximumHeight(180)
        gr_rem.addWidget(self.remote_tbl)
        lay.addWidget(grp_remote)
```

- [ ] **Step 3: Populate in `_refresh()`** — append at the end of `_refresh()`:

```python
        remote_events = [e for e in s["recent"] if e.get("host")]
        self.remote_tbl.setRowCount(0)
        rem_colors = {"YARA": "#58a6ff", "IOC": "#d29922",
                      "MEMORY": "#a371f7", "HASH": "#8b949e"}
        for evt in reversed(remote_events[-20:]):
            row = self.remote_tbl.rowCount()
            self.remote_tbl.insertRow(row)
            typ = evt.get("type", "")
            col = rem_colors.get(typ, "#8b949e")
            for i, txt in enumerate([
                evt.get("time", ""),
                evt.get("host", ""),
                typ,
                evt.get("msg", ""),
            ]):
                item = QTableWidgetItem(txt)
                item.setFont(QFont("Consolas", 11))
                if i in (2, 3):
                    item.setForeground(QColor(col))
                self.remote_tbl.setItem(row, i, item)
```

- [ ] **Step 4: Verify** — run app, do a remote scan, switch to Dashboard — Remote Scans table should populate.

- [ ] **Step 5: Commit**

```bash
git add ui/dashboard_tab.py
git commit -m "feat(dashboard): host param in log_event, add remote scans table"
```

---

### Task 6: ReportTab — remote scans section

**Files:**
- Modify: `ui/report_tab.py`

- [ ] **Step 1: Update `_collect_data()`** — after `quar_events` line add:

```python
        remote_events = [e for e in events if e.get("host")]
```

And add to the return dict:

```python
            "remote_events": remote_events,
```

- [ ] **Step 2: Add TXT section in `_preview()`** — after the `quar_events` block:

```python
        if d.get("remote_events"):
            by_host: dict = {}
            for e in d["remote_events"]:
                by_host.setdefault(e.get("host", "Unknown"), []).append(e)
            lines.append(f"УДАЛЁННЫЕ СКАНЫ ({len(d['remote_events'])})")
            lines.append("-" * 40)
            for host_name, evts in by_host.items():
                lines.append(f"  Хост: {host_name}")
                for e in evts:
                    lines.append(
                        f"    [{e.get('type','?')}] {e.get('time','')}  {e.get('msg','')}"
                    )
            lines.append("")
```

- [ ] **Step 3: Add HTML section in `_export_html()`** — before the YARA rules `if self.chk_yara_rules.isChecked()` block:

```python
        if d.get("remote_events"):
            by_host: dict = {}
            for e in d["remote_events"]:
                by_host.setdefault(e.get("host", "Unknown"), []).append(e)
            rem_colors = {"YARA": "#58a6ff", "IOC": "#d29922",
                          "MEMORY": "#a371f7", "HASH": "#8b949e"}
            remote_rows = ""
            for host_name, evts in by_host.items():
                for e in evts:
                    typ = e.get("type", "?")
                    col = rem_colors.get(typ, "#8b949e")
                    remote_rows += (
                        f'<tr><td>{e.get("time","")}</td>'
                        f'<td style="color:#58a6ff">{host_name}</td>'
                        f'<td style="color:{col}">{typ}</td>'
                        f'<td>{e.get("msg","")}</td></tr>\n'
                    )
            html += (
                f'<h2>Удалённые сканы ({len(d["remote_events"])})</h2>'
                f'<div class="section"><table>'
                f'<tr><th>Время</th><th>Хост</th><th>Тип</th><th>Правило / Файл</th></tr>'
                f'{remote_rows}</table></div>'
            )
```

- [ ] **Step 4: Verify** — run app, do remote scan, go to Report → Preview — "УДАЛЁННЫЕ СКАНЫ" section should appear.

- [ ] **Step 5: Commit**

```bash
git add ui/report_tab.py
git commit -m "feat(report): add remote scans section grouped by host"
```

---

### Task 7: Rebuild agent.exe + deploy to second laptop

- [ ] **Step 1: Build**

```bat
cd agent
build.bat
```

Expected: `agent/dist/agent.exe` rebuilt without errors.

- [ ] **Step 2: Copy to 192.168.1.68** — stop old agent on the second laptop, replace `agent.exe`, restart:

```cmd
agent.exe
```

Verify token still matches what's in the app's hosts.json (token doesn't change on restart since `token.txt` is preserved).

- [ ] **Step 3: Verify end-to-end**

In main app: Hosts tab → select host → Memory Scan tab → "Обновить процессы" → process table fills → select a few rules → "Scan Memory" → results appear in table and in Dashboard "Удалённые сканы".

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: remote YARA+memory scan complete — rule selector, dashboard, report"
```
