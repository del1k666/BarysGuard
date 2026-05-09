# IOC Analyzer v2.0 — Threat Intelligence & Incident Response Platform

**Version:** 2.0  
**Platform:** Windows 10/11 (64-bit)  
**Language:** Python 3.10+, PyQt6  
**UI Language:** Russian  
**Target Audience:** SOC analysts, incident responders

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Features](#3-features)
4. [File Structure](#4-file-structure)
5. [Dependencies](#5-dependencies)
6. [Installation & Running](#6-installation--running)
7. [Configuration](#7-configuration)
8. [YARA Engine Setup](#8-yara-engine-setup)
9. [Threading Model](#9-threading-model)
10. [Built-in YARA Rules](#10-built-in-yara-rules)
11. [Platform Requirements](#11-platform-requirements)

---

## 1. Project Overview

**IOC Analyzer v2.0** is a Windows desktop application for cybersecurity analysts that consolidates common threat intelligence and incident response workflows into a single, offline-capable tool. It enables SOC analysts and incident responders to:

- Query file hash reputation via the VirusTotal API
- Collect and export live system IOCs (processes, autoruns, network connections) using PowerShell
- Scan files or running process memory with YARA rules
- Look up IP addresses and domains against AbuseIPDB and geolocation APIs
- Generate threat analysis and YARA rules using AI (Groq or Anthropic Claude)
- Quarantine suspicious files with XOR obfuscation
- Produce structured HTML or plain-text incident reports

The application is built with **Python 3.10+** and **PyQt6**, uses a dark cybersecurity-themed UI, and all blocking I/O operations execute in background **QThread** workers to ensure the interface remains responsive at all times.

---

## 2. Architecture Overview

```
main.py  (entry point, ~30 lines)
  └── ui/main_window.py  (MainWindow — QTabWidget host)
        ├── ui/dashboard_tab.py       (DashboardTab — shared stats, event log)
        ├── ui/hash_tab.py            (HashTab — single & bulk hash lookup)
        ├── ui/ioc_tab.py             (IOCTab — system IOC collection)
        ├── ui/yara_tab.py            (YARATab — file YARA scanning)
        ├── ui/ai_tab.py              (AITab — LLM assistant)
        ├── ui/report_tab.py          (ReportTab — HTML/TXT export)
        ├── ui/net_intel_tab.py       (NetIntelTab — IP/domain intelligence)
        ├── ui/quarantine_tab.py      (QuarantineTab — file isolation)
        ├── ui/memory_scanner_tab.py  (MemoryScannerTab — process memory scan)
        └── ui/settings_tab.py        (SettingsTab — API keys, directories)

Shared modules:
  config.py     → Config class, VT_URL, RESULTS_DIR, QUARANTINE_DIR
  styles.py     → STYLE (dark theme stylesheet)
  constants.py  → BUILTIN_YARA_RULES (20 rules), AI_SYSTEM, QUICK_PROMPTS

Core logic:
  core/yara_engine.py  → run_yara_scan(), YARA_PYTHON_AVAILABLE
  core/hash_utils.py   → compute_sha256()

Workers (QThread subclasses):
  workers/vt_worker.py      → VTWorker, BulkHashWorker
  workers/ioc_worker.py     → IOCWorker, POWERSHELL_SCRIPT
  workers/yara_worker.py    → YARAWorker
  workers/ai_worker.py      → AIWorker
  workers/net_worker.py     → NetIntelWorker
  workers/process_worker.py → ProcessListWorker, MemScanWorker
```

### Design Principles

- **Separation of concerns:** Each UI tab owns its layout and user interaction; all network and CPU-bound work is delegated to dedicated QThread worker classes.
- **Shared state via MainWindow:** Tabs communicate results upward through signals; `MainWindow` aggregates statistics and forwards them to `DashboardTab`.
- **Graceful degradation:** Features that depend on optional binaries (`yara64.exe`) or optional pip packages (`yara-python`) detect availability at startup and disable or fall back automatically.
- **Offline-first configuration:** All API keys and paths are stored in a local `config.json`; the application runs without network access for YARA scanning and quarantine operations.

---

## 3. Features

| Tab | Feature | API / Engine | Description |
|-----|---------|--------------|-------------|
| Dashboard | Real-time stats monitoring | QTimer (3 s refresh) | Aggregates result counts from all tabs; displays a live event log |
| Hash Lookup | Single hash lookup | VirusTotal API v3 | MD5 / SHA1 / SHA256 reputation check with detection ratio and vendor breakdown |
| Hash Lookup | Bulk file scan | VirusTotal API v3 | Recursively hashes a folder (SHA256), submits each hash to VT with configurable rate limiting |
| IOC Collection | System IOC gather | PowerShell 5.1 | Enumerates running processes, autorun entries, and active network connections; exports to CSV/JSON |
| YARA Scanner | File scanning | `yara64.exe` / `yara-python` | Scans individual files or directory trees against 20 built-in rules or custom `.yar` rule files |
| Network Intel | IP / domain reputation | AbuseIPDB + ip-api.com | Returns abuse confidence score, geolocation (country, city), ISP, and ASN |
| AI Assistant | Threat analysis chat | Groq API / Claude API | Answers analyst questions, explains malware behavior, generates YARA rules on demand |
| Report Builder | Session export | Native Python | Compiles findings from all tabs into formatted HTML or plain-text incident reports |
| Memory Scanner | Process memory scanning | YARA engine | Lists running processes and scans a selected process's memory regions with YARA rules |
| Quarantine | File isolation | Local filesystem | Copies files to the quarantine directory with XOR obfuscation; supports restore and permanent delete |
| Settings | Application configuration | `config.json` | API keys, output directories, rate limits, and AI provider selection |

---

## 4. File Structure

```
ioc_analyzer_v2/
│
├── main.py                    # Application entry point; constructs QApplication and MainWindow
├── config.py                  # Config dataclass; loads/saves config.json; exposes VT_URL, RESULTS_DIR, QUARANTINE_DIR
├── styles.py                  # STYLE constant — full PyQt6 dark-theme QSS stylesheet
├── constants.py               # BUILTIN_YARA_RULES (20 rules), AI_SYSTEM prompt, QUICK_PROMPTS list
│
├── requirements.txt           # Python package dependencies
├── build.bat                  # PyInstaller build script → dist/IOC_Analyzer_v2.exe
├── run_debug.bat              # Launches python main.py with console output visible
├── check.py                   # Pre-flight sanity checker (imports, yara availability)
├── yara64.exe                 # YARA command-line binary (Windows 64-bit, included)
│
├── ui/
│   ├── main_window.py         # MainWindow: QTabWidget, tab wiring, cross-tab signal routing
│   ├── dashboard_tab.py       # DashboardTab: stat cards, QTimer refresh, event log widget
│   ├── hash_tab.py            # HashTab: single-hash form, bulk-scan folder picker, results table
│   ├── ioc_tab.py             # IOCTab: IOC collection controls, output viewer, export buttons
│   ├── yara_tab.py            # YARATab: rule selector, file/folder picker, match results table
│   ├── ai_tab.py              # AITab: chat history, prompt input, quick-prompt buttons
│   ├── report_tab.py          # ReportTab: report template chooser, preview pane, save dialog
│   ├── net_intel_tab.py       # NetIntelTab: IP/domain input, result cards, history list
│   ├── quarantine_tab.py      # QuarantineTab: quarantine file list, restore/delete actions
│   ├── memory_scanner_tab.py  # MemoryScannerTab: process list table, scan trigger, match viewer
│   └── settings_tab.py        # SettingsTab: form for all config.json fields, save/reload buttons
│
├── core/
│   ├── yara_engine.py         # run_yara_scan(rules, target) — selects yara64.exe or yara-python; YARA_PYTHON_AVAILABLE flag
│   └── hash_utils.py          # compute_sha256(path) — streaming SHA256 with chunked reads
│
├── workers/
│   ├── vt_worker.py           # VTWorker (single hash); BulkHashWorker (folder scan + VT batch)
│   ├── ioc_worker.py          # IOCWorker: runs embedded POWERSHELL_SCRIPT; emits output lines
│   ├── yara_worker.py         # YARAWorker: iterates files, calls yara_engine.run_yara_scan()
│   ├── ai_worker.py           # AIWorker: calls Groq or Anthropic Claude REST API; streams response
│   ├── net_worker.py          # NetIntelWorker: queries AbuseIPDB + ip-api.com; emits result dict
│   └── process_worker.py      # ProcessListWorker (ps enumeration); MemScanWorker (memory YARA scan)
│
└── docs/
    ├── README.md              # This file
    └── flows/                 # Architecture and data-flow diagrams
```

---

## 5. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `PyQt6` | >= 6.5.0 | GUI framework — widgets, threading (QThread), signals/slots |
| `requests` | >= 2.31.0 | HTTP calls to VirusTotal, AbuseIPDB, ip-api.com, Groq, and Claude APIs |
| `yara-python` | >= 4.3.0 | Optional — YARA scanning fallback when `yara64.exe` is unavailable |
| `pyinstaller` | >= 6.0.0 | Build tool for producing a standalone `IOC_Analyzer_v2.exe` |

Install all runtime dependencies:

```bash
pip install -r requirements.txt
```

> **Note:** `yara-python` requires Microsoft Visual C++ Build Tools on Windows. If installation fails, the application will automatically use the bundled `yara64.exe` instead.

---

## 6. Installation & Running

### Prerequisites

- Python 3.10 or newer (64-bit)
- pip
- Windows 10 or 11 (64-bit)
- Internet connection (required only for API-dependent features)

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run in development mode

```bash
python main.py
```

Alternatively, double-click **`run_debug.bat`** to launch with a visible console window for log output.

### Build a standalone executable

```bat
build.bat
```

PyInstaller bundles Python, all dependencies, `yara64.exe`, and built-in YARA rules into a single file:

```
dist/IOC_Analyzer_v2.exe
```

The resulting executable requires no Python installation on the target machine and runs on any Windows 10/11 64-bit system.

---

## 7. Configuration

### Config file location

```
<project_root>/config.json
```

The file is created automatically with default values on first launch. It can be edited directly or managed through the **Settings** tab inside the application.

### Configuration keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `vt_api_key` | string | `""` | VirusTotal API key. Free tier at [virustotal.com](https://www.virustotal.com) |
| `abuseipdb_key` | string | `""` | AbuseIPDB API key. Free tier at [abuseipdb.com](https://www.abuseipdb.com) |
| `groq_key` | string | `""` | Groq API key. Free tier at [console.groq.com](https://console.groq.com) |
| `claude_key` | string | `""` | Anthropic Claude API key. Available at [console.anthropic.com](https://console.anthropic.com) |
| `ai_provider` | string | `"groq"` | Active AI backend: `"groq"` or `"claude"` |
| `results_dir` | string | `"C:/Tools/results"` | Default output directory for IOC collection exports |
| `quarantine_dir` | string | `"C:/Tools/quarantine"` | Directory used to store quarantined (XOR-obfuscated) files |
| `vt_rate_limit_sec` | integer | `15` | Seconds to wait between VirusTotal API calls. Free tier limit is 4 requests/minute |
| `auto_save_reports` | boolean | `false` | When `true`, reports are saved to `results_dir` automatically after generation |

### Example `config.json`

```json
{
  "vt_api_key": "YOUR_VIRUSTOTAL_KEY",
  "abuseipdb_key": "YOUR_ABUSEIPDB_KEY",
  "groq_key": "YOUR_GROQ_KEY",
  "claude_key": "",
  "ai_provider": "groq",
  "results_dir": "C:/Tools/results",
  "quarantine_dir": "C:/Tools/quarantine",
  "vt_rate_limit_sec": 15,
  "auto_save_reports": false
}
```

---

## 8. YARA Engine Setup

The application supports two YARA execution backends and selects automatically based on availability.

### Preferred: `yara64.exe` (command-line binary)

Place the YARA 64-bit Windows binary in any of the following locations. The engine checks them in order and uses the first match:

| Priority | Path |
|----------|------|
| 1 | `<project_root>/yara64.exe` |
| 2 | `<project_root>/yara/yara64.exe` |
| 3 | `C:\Tools\yara\yara64.exe` |
| 4 | `C:\Tools\yara.exe` |
| 5 | `C:\Program Files\YARA\yara64.exe` |

The project ships with `yara64.exe` in the project root, so no additional setup is required in most cases.

### Fallback: `yara-python` (pip package)

If no `yara64.exe` binary is found, the engine falls back to the `yara-python` Python binding. Install it with:

```bash
pip install yara-python
```

The `YARA_PYTHON_AVAILABLE` flag in `core/yara_engine.py` reflects runtime availability and is displayed in the application status bar on startup.

### Custom YARA rules

In addition to the 20 built-in rules, the YARA Scanner tab allows loading external `.yar` or `.yara` rule files. Rules must be valid YARA 4.x syntax.

---

## 9. Threading Model

All operations that involve I/O, network requests, or CPU-intensive work run in background **QThread** worker objects. This keeps the PyQt6 event loop — and therefore the UI — fully responsive during long-running tasks.

Workers communicate results back to the main thread exclusively via Qt signals (never by direct method calls or shared mutable state).

| Worker class | Module | Responsibility |
|---|---|---|
| `VTWorker` | `workers/vt_worker.py` | Submits a single file hash to the VirusTotal v3 API and emits the JSON result |
| `BulkHashWorker` | `workers/vt_worker.py` | Recursively hashes all files in a directory (SHA256), then submits each to VT with configurable rate limiting between requests |
| `IOCWorker` | `workers/ioc_worker.py` | Executes the embedded `POWERSHELL_SCRIPT` (processes, autoruns, network connections) and streams output lines back to the UI |
| `YARAWorker` | `workers/yara_worker.py` | Iterates over selected files or directory trees and calls `core/yara_engine.run_yara_scan()` for each target; emits match events |
| `AIWorker` | `workers/ai_worker.py` | Sends the analyst's prompt (with conversation history) to the configured LLM API (Groq or Claude) and emits the response text |
| `NetIntelWorker` | `workers/net_worker.py` | Queries AbuseIPDB for abuse confidence score and ip-api.com for geolocation/ISP; emits a combined result dictionary |
| `ProcessListWorker` | `workers/process_worker.py` | Runs a PowerShell command to enumerate all running processes and emits the list to the Memory Scanner tab |
| `MemScanWorker` | `workers/process_worker.py` | Attaches to a target process and scans its memory regions with YARA rules via the YARA engine |

---

## 10. Built-in YARA Rules

The application ships with **20 built-in YARA rules** defined in `constants.py`. These rules are compiled into memory at startup and require no external rule files.

### CRITICAL severity

| Rule name | Detects |
|---|---|
| `Mimikatz` | Mimikatz credential-dumping tool strings and PE characteristics |
| `Meterpreter` | Metasploit Meterpreter stager and reflective-loader signatures |
| `CobaltStrike` | Cobalt Strike Beacon configuration blobs and shellcode patterns |
| `WannaCry` | WannaCry ransomware kill-switch domain and encryption routine markers |
| `Emotet` | Emotet banking trojan loader and C2 communication patterns |
| `Ransomware_Generic` | Generic ransomware behavior: file enumeration + encryption API imports |

### HIGH severity

| Rule name | Detects |
|---|---|
| `AgentTesla` | Agent Tesla keylogger and credential-stealer strings |
| `Njrat` | njRAT (Bladabindi) remote access trojan indicators |
| `Keylogger_Generic` | Generic keylogger API call sequences (SetWindowsHookEx, GetAsyncKeyState) |
| `ProcessInjection` | Process injection technique markers (VirtualAllocEx, WriteProcessMemory, CreateRemoteThread) |
| `WebShell_PHP` | PHP web shell command-execution patterns |
| `Credential_Harvesting` | LSASS dumping and credential extraction API patterns |
| `UAC_Bypass` | Known UAC bypass technique strings and registry key references |
| `Lateral_Movement` | PsExec, WMI, and SMB lateral-movement tool signatures |

### MEDIUM severity

| Rule name | Detects |
|---|---|
| `DLL_Sideloading` | DLL side-loading indicators (known vulnerable binary names, manifest tampering) |
| `Suspicious_Office_Macro` | VBA macro strings executing shell commands or downloading payloads |
| `Network_Recon` | Port scanning and network enumeration tool signatures |
| `Persistence_Registry` | Common registry run-key persistence paths and API calls |
| `Anti_Analysis` | Anti-debugging and anti-VM technique strings |
| `PowerShell_Encoded` | Base64-encoded PowerShell command execution patterns |

### LOW severity

| Rule name | Detects |
|---|---|
| `EICAR_Test` | EICAR antivirus test file string — used to verify scanner functionality |

---

## 11. Platform Requirements

| Requirement | Minimum | Notes |
|---|---|---|
| Operating System | Windows 10 (64-bit) | Windows 11 also supported; 32-bit is not supported |
| Python | 3.10 | Required for development; not needed for the built `.exe` |
| PowerShell | 5.1 | Required for IOC collection and process enumeration features |
| Internet connection | — | Required for VirusTotal, AbuseIPDB, and AI API features; YARA scanning and quarantine work offline |
| Administrator rights | Optional | Required only for process memory scanning (MemScanWorker); all other features run as standard user |
| YARA binary | Bundled | `yara64.exe` is included in the project root; no separate installation needed |

### Free API tier limits

| Service | Free tier rate limit | Config key |
|---|---|---|
| VirusTotal | 4 requests / minute | `vt_rate_limit_sec` (default: 15 s) |
| AbuseIPDB | 1 000 checks / day | — |
| Groq | Varies by model | — |
| Anthropic Claude | Pay-per-token | — |

---

*IOC Analyzer v2.0 — built for Windows incident response workflows.*
