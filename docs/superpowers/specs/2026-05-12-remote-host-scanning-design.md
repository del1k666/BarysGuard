# Remote Host Scanning — Full Feature Design
**Date:** 2026-05-12

## Summary

Extend the Hosts tab with the same YARA + Memory scan stack that exists locally, but executed against a remote agent. Add results routing to Dashboard and Report. Fix YARA scan timeout.

---

## Scope

| # | Feature |
|---|---------|
| 1 | Fix 10s timeout → 120s for remote scans |
| 2 | New `/scan/memory/all` endpoint in agent |
| 3 | HostsTab right panel: two sub-tabs (File Scan / Memory Scan) |
| 4 | YARA rule selector (built-in checkboxes + custom rule editor) — same UX as local tabs |
| 5 | Remote Memory Scan: process list fetched from host → rule selector → scan |
| 6 | Remote scan results logged to DashboardTab with `host` field |
| 7 | New "Удалённые сканы" section at bottom of Dashboard |
| 8 | Report gains "Удалённые сканы" section grouped by host |

---

## Architecture

### Data flow

```
HostsTab (UI)
  ├── FileTab  → RemoteScanWorker(yara/ioc/hashes, rules, path, timeout=120)
  │                └── AgentClient → https://host:5555/scan/yara|ioc|hashes
  └── MemTab   → RemoteMemScanWorker(rules, timeout=180)
                   ├── AgentClient.list_processes() → process table
                   └── AgentClient.scan_memory_all(rules) → matches
                         └── agent /scan/memory/all

Both workers on done → DashboardTab.log_event(..., host="NAME (IP)")
DashboardTab._refresh() → renders "Удалённые сканы" table
ReportTab._collect_data() → filters events by host field → report section
```

---

## File Changes

### `agent/agent.py`

New endpoint `POST /scan/memory/all`:
- Accepts `{ "rules": {name: text, ...} }`
- Iterates `psutil.process_iter(["pid","name","exe"])`
- For each process with a readable exe path, writes each rule to a temp `.yar` file and runs `yara64.exe rule.yar exe_path` (timeout 15s per rule per process)
- Returns `{ "matches": [{ "rule", "file", "pid", "process_name" }] }`
- Skips `AccessDenied` / `NoSuchProcess` silently
- Returns `{"error": "yara64.exe not found"}` if YARA_EXE is None

### `core/agent_client.py`

New method:
```python
def scan_memory_all(self, rules: dict) -> dict:
    return self._post("/scan/memory/all", {"rules": rules})
```
Client constructed with `timeout=120` in `RemoteScanWorker`, `timeout=180` in `RemoteMemScanWorker`.

### `workers/host_worker.py`

- `RemoteScanWorker`: constructor takes `timeout=120`, passes to `AgentClient`
- New `RemoteMemScanWorker(QThread)`:
  - Signals: `processes(list)`, `done(list)`, `error(str)`, `progress(str)`
  - `run()`: calls `client.scan_memory_all(rules)`, emits results
  - Each match → `{"type":"MEMORY","rule":..,"file":..,"pid":..,"process_name":..}`

### `ui/hosts_tab.py`

Right panel replaced with `QTabWidget` containing two tabs:

**Tab 1 — "Файловый скан"** (mirrors existing scan options):
- `QListWidget` with checkbox per built-in rule (same as `MemoryScannerTab.rule_list`)
- "Все" / "Ничего" buttons
- `QTextEdit` custom rule input + "Добавить правило" button — name parsed from `rule <name>` declaration in text, fallback `Custom_N`; stored in `_file_custom_rules: dict`
- IOC / Hashes checkboxes
- Path `QLineEdit` (default `C:\Users`)
- "Scan" button

**Tab 2 — "Memory Scan"** (mirrors `MemoryScannerTab`):
- "Обновить процессы" button → calls `AgentClient.list_processes()` → fills process table
- Process table: PID / Name / Exe (3 cols, Exe stretches)
- Filter `QLineEdit` by name
- "Выбрать все" / "Снять" buttons
- `QListWidget` with checkbox per built-in rule
- "Все" / "Ничего" buttons
- `QTextEdit` custom rule input + "Добавить правило" button — same name-parsing logic; stored in `_mem_custom_rules: dict`
- "Scan Memory" button + "Стоп" button
- `QProgressBar` (5px) + status label

Shared at bottom: existing results `QTableWidget` with cols `[Тип, Severity, Файл/Процесс]`.

Helper `_get_selected_rules(list_widget, custom_dict) -> dict` — shared by both tabs.

`_on_scan_done(results, host)`:
- Fills results table
- Calls `DashboardTab.log_event(type_, msg, level, severity, target, scan=True, host=host_label)`
- Updates `DashboardTab.stats["yara_hits"]` / `stats["suspicious_procs"]`

### `ui/dashboard_tab.py`

`log_event()` signature:
```python
@staticmethod
def log_event(type_, msg, level="info", severity="", target="", scan=False, host=""):
```
`host` stored in event dict.

New `QGroupBox("Удалённые сканы")` added at bottom of `_build()`:
- `QTableWidget` with cols `[Время, Хост, Тип, Правило / Файл]`
- `setMaximumHeight(200)`

`_refresh()` populates it by filtering `stats["recent"]` where `e.get("host")`.

### `ui/report_tab.py`

`_collect_data()` adds:
```python
remote_events = [e for e in events if e.get("host")]
```

TXT preview: new section "УДАЛЁННЫЕ СКАНЫ" grouped by host name.

HTML export: new `<h2>Удалённые сканы</h2>` section with table cols `[Время, Хост, Тип, Правило, Файл]`.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| `yara64.exe` absent on agent | `/scan/memory/all` returns `{"error": "yara64.exe not found"}`, UI shows error in status label |
| Process `AccessDenied` | silently skipped in agent loop |
| Timeout (120 / 180s) | `RemoteScanWorker.error` emitted, status label shows message |
| No rules selected | scan button disabled until ≥1 rule checked |
| No process selected (memory tab) | status label: "Выбери процессы" |

---

## Affected Files (summary)

```
agent/agent.py              + /scan/memory/all endpoint
core/agent_client.py        + scan_memory_all()
workers/host_worker.py      ~ timeout, + RemoteMemScanWorker
ui/hosts_tab.py             ~ right panel → QTabWidget with File/Memory tabs
ui/dashboard_tab.py         ~ log_event host param, + remote scans table
ui/report_tab.py            ~ remote_events in collect_data, + report section
```
