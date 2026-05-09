# IOC Analyzer v2 — Bug Report & Recommendations

**Date:** 2026-05-09
**Project:** IOC Analyzer v2
**Scope:** Full codebase review — security, reliability, correctness, and code quality

---

## Table of Contents

1. [Critical Issues](#critical-issues)
2. [High Issues](#high-issues)
3. [Medium Issues](#medium-issues)
4. [Low Issues](#low-issues)
5. [Summary Table](#summary-table)
6. [Remediation Priority](#remediation-priority)

---

## Critical Issues

---

### Bug 1: Hardcoded API Keys in Source Code

- **Severity**: CRITICAL
- **Location**: `config.py` — `Config.DEFAULTS` dict
- **Description**: Two real API keys are hardcoded as default values in `Config.DEFAULTS`: a VirusTotal API key and an AbuseIPDB API key. Anyone with read access to the source code can extract and use these keys immediately.
- **Risk/Impact**: Key theft, rate limit exhaustion, and potential account suspension. If the repository is ever made public or shared, the keys are immediately and permanently exposed. Even in a private setting, any collaborator or auditor gains unauthorized access to paid API quotas.
- **Recommended Fix**: Remove hardcoded keys from `DEFAULTS`. Set them to an empty string `""`. Add a startup check: if keys are empty, display a setup dialog prompting the user to enter their own keys via the Settings tab before the application proceeds.

---

### Bug 2: Plaintext API Key Storage

- **Severity**: CRITICAL
- **Location**: `config.py` — `Config.save()` method; warning message also surfaced in `ui/settings_tab.py`
- **Description**: All API keys are persisted to `config.json` in plaintext. The Settings tab itself warns users about this limitation, confirming it is a known but unresolved issue. Any local user account, background process, or script with filesystem access can read all keys without any authentication.
- **Risk/Impact**: Credential theft via direct file access, USB drive exfiltration, insider threat exploitation, or opportunistic malware sweeping for `.json` files containing the word `api_key`.
- **Recommended Fix**: Use the Windows Credential Manager via the `keyring` library to store secrets in the OS-managed secure vault. Alternatively, encrypt `config.json` using Windows DPAPI (`cryptography` library) with a user-derived key so that only the logged-in Windows user can decrypt it.

---

### Bug 3: Weak Quarantine Encryption (XOR 0xAA)

- **Severity**: CRITICAL
- **Location**: `ui/quarantine_tab.py` — `_quarantine_file()` and `_restore()` methods
- **Description**: The quarantine mechanism protects files using single-byte XOR with the constant `0xAA`. This is trivially reversible: any attacker, script, or even the malware itself can restore the original file by XOR-ing the quarantined bytes with `0xAA` again. No key, no password, and no real barrier is in place.
- **Risk/Impact**: False sense of security for the user. Malware residing in quarantine could theoretically self-restore. The quarantine directory provides no actual containment — it is effectively just a renamed copy of the original file.
- **Recommended Fix**: Replace XOR with AES-256-GCM using the `cryptography` library (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`). Generate a random 256-bit key per quarantine session, or derive a key from a user-set password using PBKDF2. Store the key (or password hint) securely via the Windows Credential Manager.

---

## High Issues

---

### Bug 4: Race Conditions on Shared Stats Dict

- **Severity**: HIGH
- **Location**: `ui/dashboard_tab.py` — `DashboardTab.stats` class variable; also accessed from `workers/vt_worker.py`, `ui/hash_tab.py`, `ui/ioc_tab.py`, `ui/net_intel_tab.py`, `ui/yara_tab.py`, and `ui/quarantine_tab.py`
- **Description**: `DashboardTab.stats` is a plain Python `dict` that is read and written from multiple `QThread` worker threads simultaneously without any synchronization primitive. Concurrent writes to the same dict key can result in lost updates, torn reads, or corrupted counter values. Python's GIL reduces (but does not eliminate) the risk for simple increments, but compound operations are not protected.
- **Risk/Impact**: Dashboard statistics silently display incorrect totals. In the worst case, a race on a compound operation (read-modify-write) can corrupt the dict state and cause a crash.
- **Recommended Fix**: Protect all reads and writes with a `QMutex`, or — preferably — use Qt signals to marshal stat update events back to the main thread, which then performs the dict update. Replace direct dict writes in worker threads with an `update_stat(key, delta)` method that emits a signal.

---

### Bug 5: No Retry/Timeout Handling in API Workers

- **Severity**: HIGH
- **Location**: `workers/vt_worker.py` (`VTWorker`, `BulkHashWorker`), `workers/ai_worker.py` (`AIWorker`), `workers/net_worker.py` (`NetIntelWorker`)
- **Description**: API calls in worker threads have no configured request timeout. If the remote server becomes unresponsive, workers block the thread indefinitely, making the application appear frozen to the user. `BulkHashWorker` sleeps 60 seconds on an HTTP 429 rate-limit response without any user-visible progress update. Additionally, it uses `continue` after the sleep, which skips the rate-limited file entirely rather than retrying it (see also Bug 10).
- **Risk/Impact**: Application UI appears hung with no feedback. Files are silently skipped during bulk scans when rate-limited, producing incomplete results that the user has no way to detect.
- **Recommended Fix**: Pass `timeout=30` (or a configurable value) to all `requests` calls. Implement exponential backoff with jitter for rate-limit responses. Emit a progress signal during wait periods so the UI can display a countdown. Fix the `BulkHashWorker` rate-limit handler to retry the current file rather than skipping it.

---

### Bug 6: No Path Validation on User Input

- **Severity**: HIGH
- **Location**: `ui/hash_tab.py` — `_scan_folder()`; `ui/ioc_tab.py` — `_run()`; `ui/yara_tab.py` — `_scan()`
- **Description**: User-provided file paths are passed directly to OS-level operations (`os.walk`, `subprocess`, YARA rule compilation) without any validation or sanitization. There is no check for whether the path exists, whether it is a reasonable scan target, or whether it contains characters that are meaningful to a shell or subprocess invocation.
- **Risk/Impact**: Accidental scanning of `C:\Windows\System32` or other critical system directories. UNC paths (`\\server\share`) may cause unexpected network access. Paths containing special characters (backticks, semicolons, redirection operators) can lead to argument injection in subprocess calls, potentially enabling command injection in PowerShell-based workers.
- **Recommended Fix**: Validate all paths before use: confirm they exist (`Path.exists()`), are within a reasonable base directory, and are not known system directories unless the user explicitly confirms. Sanitize paths passed to `subprocess` by using argument lists (not shell strings) and avoiding `shell=True`.

---

## Medium Issues

---

### Bug 7: Outdated Claude API Model Name

- **Severity**: MEDIUM
- **Location**: `workers/ai_worker.py` — `_run_claude()` method
- **Description**: The `_run_claude()` method specifies `"model": "claude-opus-4-5"`, which is not a valid Anthropic model identifier. This will result in an API error at runtime (HTTP 400 or 404), causing the AI analysis feature to fail silently or with a confusing error message.
- **Risk/Impact**: The Claude AI analysis feature is entirely non-functional for all users until this is corrected.
- **Recommended Fix**: Update to a valid, current Anthropic model ID. Consult the Anthropic documentation for currently supported models (e.g., `claude-3-5-sonnet-20241022` or `claude-3-opus-20240229`). Consider making the model name a configurable constant in `config.py` so future updates do not require code changes.

---

### Bug 8: Hardcoded Old Anthropic API Version

- **Severity**: MEDIUM
- **Location**: `workers/ai_worker.py` — `_run_claude()` request headers
- **Description**: The header `"anthropic-version": "2023-06-01"` is hardcoded directly in the request construction. As Anthropic releases new API versions and deprecates older ones, this value will become stale without any mechanism for easy update.
- **Risk/Impact**: If Anthropic deprecates the `2023-06-01` API version, all Claude API calls will fail. The hardcoded location makes the update easy to miss during maintenance.
- **Recommended Fix**: Extract the API version string to a constant in `config.py` (e.g., `ANTHROPIC_API_VERSION = "2023-06-01"`). Update to the current version per Anthropic's documentation. This makes future version bumps a single-line change.

---

### Bug 9: Unencrypted HTTP for Geolocation Requests

- **Severity**: MEDIUM
- **Location**: `workers/net_worker.py` — `NetIntelWorker.run()`
- **Description**: Geolocation lookups are performed over plain HTTP using `http://ip-api.com/json/{target}`. The IP address being investigated is transmitted in cleartext, visible to any network observer on the path between the analyst's machine and the API server (ISPs, VPN providers, corporate network monitors, or on-path attackers).
- **Risk/Impact**: Operational security risk: the IP addresses under investigation are leaked to network observers. This is particularly significant in threat intelligence and incident response contexts where investigation targets must be kept confidential.
- **Recommended Fix**: Switch to HTTPS. Note that `ip-api.com` requires a paid subscription for HTTPS access. A free HTTPS alternative is `https://ipinfo.io/{target}/json`. Update the URL scheme and add the appropriate API key to configuration if a paid plan is used.

---

### Bug 10: BulkHashWorker Rate Limit Bug — File Skipped Instead of Retried

- **Severity**: MEDIUM
- **Location**: `workers/vt_worker.py` — `BulkHashWorker.run()` rate-limit exception handler
- **Description**: When VirusTotal returns HTTP 429 (Too Many Requests), the handler calls `time.sleep(60)` and then `continue`, which advances the loop to the **next** file. The rate-limited file is never processed. A comment in the code reads "повторим этот файл" (Russian: "we will retry this file"), but the `continue` statement contradicts this intent and skips the file entirely.
- **Risk/Impact**: Bulk scan results are silently incomplete. Files that happen to coincide with a rate-limit boundary are dropped from the results with no notification to the user.
- **Recommended Fix**: Replace `continue` with logic that retries the current file: either decrement the loop index (`i -= 1`) before continuing, or use a retry queue pattern. Emit a signal informing the UI of the wait and which file is being retried.

---

### Bug 11: JSON API Response Parsed Without Validation

- **Severity**: MEDIUM
- **Location**: `workers/ai_worker.py` — `_run_groq()` method, response parsing line
- **Description**: The Groq API response is parsed with direct chained key access: `r.json()["choices"][0]["message"]["content"]`. If the API returns an unexpected structure (e.g., an error response, a partial payload due to a network interruption, or a schema change), this raises an unhandled `KeyError` or `IndexError` that propagates as an unhandled exception in the worker thread.
- **Risk/Impact**: Any deviation from the expected API response format causes a silent crash of the AI worker thread, leaving the UI in a loading state with no user feedback.
- **Recommended Fix**: Use `.get()` with safe fallbacks at each level: `r.json().get("choices", [{}])[0].get("message", {}).get("content", "")`. Validate that the extracted content is non-empty before using it, and emit a descriptive error signal if parsing fails.

---

### Bug 12: ProcessListWorker JSON Parse Without Error Handling

- **Severity**: MEDIUM
- **Location**: `workers/process_worker.py` — `ProcessListWorker.run()`
- **Description**: The PowerShell process list output is parsed with `json.loads(r.stdout.strip())` without any surrounding `try-except`. PowerShell output can be malformed due to encoding issues (especially on non-English Windows locales), partial output when the buffer is cut off, or error messages mixed into stdout.
- **Risk/Impact**: Any malformed output from PowerShell causes an unhandled `json.JSONDecodeError` that crashes the worker thread. The process monitor tab will appear to hang or display nothing, with no error message shown to the user.
- **Recommended Fix**: Wrap the `json.loads()` call in a `try-except json.JSONDecodeError` block. On failure, emit an error signal with the raw stdout content included in the message to assist with debugging.

---

### Bug 13: Missing `_last_response` Attribute Initialization

- **Severity**: MEDIUM
- **Location**: `ui/ai_tab.py` — `AITab.__init__()` and `_on_chunk()` method
- **Description**: The instance attribute `self._last_response` is assigned inside `_on_chunk()` (called when the AI streams a response chunk) but is never initialized in `__init__()`. If any code path accesses `self._last_response` before the first chunk arrives — for example, if a copy or export action is triggered immediately after sending a query — it will raise `AttributeError: 'AITab' object has no attribute '_last_response'`.
- **Risk/Impact**: Intermittent `AttributeError` crash in the AI tab under certain timing conditions. The error is not immediately reproducible, making it difficult to diagnose.
- **Recommended Fix**: Add `self._last_response = ""` to `AITab.__init__()` alongside other attribute initializations.

---

### Bug 14: File Handle Leaks in BulkHashWorker and QuarantineTab

- **Severity**: MEDIUM
- **Location**: `workers/vt_worker.py` — `BulkHashWorker.run()`; `ui/quarantine_tab.py` — `_quarantine_file()`
- **Description**: Some file `open()` operations in these methods do not use `with` context managers. If an exception is raised between the `open()` call and the explicit `close()` (or if `close()` is omitted), the file handle is not released. On Windows, unreleased file handles prevent other processes from accessing or deleting the file.
- **Risk/Impact**: File descriptor exhaustion during large bulk scans. Quarantined files may remain locked, preventing management operations. On Windows, locked files cannot be moved, renamed, or deleted by other tools.
- **Recommended Fix**: Convert all `open()` calls in these methods to use `with open(...) as f:` context managers. This guarantees handle release even when exceptions occur.

---

## Low Issues

---

### Bug 15: No Unit Tests

- **Severity**: LOW
- **Location**: Entire project — no `tests/` directory or test files found
- **Description**: The project has zero test coverage. Core logic including API response parsing, file hashing, config serialization/deserialization, YARA rule compilation, and worker thread behavior are all untested. Regression bugs introduced during refactoring or dependency updates go undetected until a user encounters them at runtime.
- **Risk/Impact**: Silent regressions accumulate over time. Confidence in correctness cannot be established programmatically. Onboarding new contributors is harder without tests that document expected behavior.
- **Recommended Fix**: Create a `tests/` directory and add a test runner configuration (e.g., `pytest`). At minimum, add: config save/load round-trip tests, hash calculation tests with known SHA-256 vectors, API response parsing tests using mock `requests` responses (via `responses` or `unittest.mock`), and YARA compilation tests with sample rules.

---

### Bug 16: Hardcoded Windows Drive Paths

- **Severity**: LOW
- **Location**: `config.py` — `DEFAULTS` dict (`results_dir`, `quarantine_dir`); `core/yara_engine.py` — `yara64.exe` search paths
- **Description**: Default output and quarantine directories are set to absolute paths on the `C:` drive (e.g., `C:/Tools/results`, `C:/Tools/quarantine`). Users whose Windows installation is on a different drive letter, or who lack write permissions to `C:\Tools`, will encounter errors on first launch and must manually reconfigure these paths.
- **Risk/Impact**: Poor out-of-box experience for a meaningful subset of users. First-run errors may appear before the user has had a chance to configure anything.
- **Recommended Fix**: Use `pathlib.Path.home()` or the `APPDATA` / `LOCALAPPDATA` environment variable for portable default paths. For example: `str(Path.home() / "IOCAnalyzer" / "results")` works on any Windows account regardless of drive letter or installation path.

---

### Bug 17: Silent `except: pass` Swallows Real Errors

- **Severity**: LOW
- **Location**: `ui/quarantine_tab.py` — `_load()` method; `core/yara_engine.py` — yara-python fallback scan block
- **Description**: Bare `except Exception: pass` clauses silently discard exceptions. In `_load()`, a corrupted quarantine metadata file will be ignored entirely, causing the quarantine list to silently display incomplete data. In `yara_engine.py`, a YARA scan failure is swallowed, producing no matches and no indication that the scan did not run correctly.
- **Risk/Impact**: Users receive no feedback when errors occur. In a security tool context, a silent YARA scan failure is particularly dangerous as it may lead the user to incorrectly conclude a file is clean.
- **Recommended Fix**: At minimum, add `logging.warning(...)` or `print(...)` calls inside exception handlers to surface errors to the console. Better: emit an error signal or append a message to a dedicated debug/log panel in the UI. Never use bare `pass` in security-relevant code paths.

---

### Bug 18: No Proxy Support

- **Severity**: LOW
- **Location**: All `requests.get()` and `requests.post()` calls across `workers/vt_worker.py`, `workers/ai_worker.py`, `workers/net_worker.py`
- **Description**: All outbound API calls are made without proxy configuration. The `requests` library supports proxies via the `proxies` parameter, but this is never used. Enterprise environments commonly require all outbound HTTP(S) traffic to route through a corporate proxy server.
- **Risk/Impact**: The application is unusable in enterprise and government network environments that enforce mandatory proxy routing. API calls will silently fail with connection errors that are difficult to diagnose as a proxy issue.
- **Recommended Fix**: Add a proxy URL field to the Settings tab and expose it in `config.py`. Pass `proxies={"http": proxy_url, "https": proxy_url}` to all `requests` calls, conditionally, when a proxy is configured. Alternatively, respect system proxy settings via `requests`' default behavior when no explicit proxy is set.

---

### Bug 19: No Session-Level API Response Caching

- **Severity**: LOW
- **Location**: `workers/vt_worker.py`, `workers/net_worker.py`
- **Description**: Each time the user queries a hash or IP address, a fresh API request is issued — even if the same indicator was checked minutes earlier in the same session. VirusTotal and AbuseIPDB enforce daily rate limits on free-tier accounts, so repeated lookups of the same indicator consume quota unnecessarily.
- **Risk/Impact**: Premature rate limit exhaustion during investigation sessions. Unnecessary latency on repeated lookups of the same indicator.
- **Recommended Fix**: Implement a simple in-memory cache keyed by the indicator (hash or IP) for the duration of the application session. A `dict` or `functools.lru_cache` wrapper on the lookup function is sufficient. Cache TTL can be set to the session lifetime, or a short fixed window (e.g., 10 minutes) for long-running sessions.

---

### Bug 20: Quarantine Restore Race — Metadata Deleted Before Verifying Write Success

- **Severity**: LOW
- **Location**: `ui/quarantine_tab.py` — `_restore()` method
- **Description**: After decrypting a quarantined file and writing the restored bytes to disk, both the `.quar` (encrypted payload) and `.meta` (metadata) files are deleted. This deletion occurs without first verifying that the write operation completed successfully. If the write fails mid-stream (e.g., disk full, permissions error, I/O error), the quarantine entry metadata is still deleted, leaving the encrypted `.quar` file with no associated metadata — the file is effectively unrecoverable through the application.
- **Risk/Impact**: Permanent, unrecoverable loss of a quarantined file in the event of a disk write failure during restore. The user loses both the quarantined copy and any way to manage it through the UI.
- **Recommended Fix**: Verify restore success before deleting quarantine files. Check that the restored file exists and its size matches the expected size after writing. Wrap the deletion in a `try-finally` block and only delete both files after the write has been confirmed. Consider deleting `.meta` last, so that `.quar` remains recoverable via manual XOR if metadata is still present.

---

## Summary Table

| # | Issue | Severity | Module |
|---|-------|----------|--------|
| 1 | Hardcoded API keys in source code | CRITICAL | `config.py` |
| 2 | Plaintext credential storage | CRITICAL | `config.py` |
| 3 | Weak XOR quarantine encryption | CRITICAL | `ui/quarantine_tab.py` |
| 4 | Race conditions on shared stats dict | HIGH | `ui/dashboard_tab.py` |
| 5 | No retry/timeout in API workers | HIGH | `workers/` |
| 6 | No path validation on user input | HIGH | `ui/` tabs |
| 7 | Outdated Claude API model name | MEDIUM | `workers/ai_worker.py` |
| 8 | Hardcoded old Anthropic API version | MEDIUM | `workers/ai_worker.py` |
| 9 | Unencrypted HTTP for geolocation | MEDIUM | `workers/net_worker.py` |
| 10 | BulkHashWorker skips rate-limited file | MEDIUM | `workers/vt_worker.py` |
| 11 | JSON response parsed without validation | MEDIUM | `workers/ai_worker.py` |
| 12 | ProcessListWorker JSON parse unhandled | MEDIUM | `workers/process_worker.py` |
| 13 | Missing `_last_response` attribute init | MEDIUM | `ui/ai_tab.py` |
| 14 | File handle leaks | MEDIUM | `workers/`, `ui/` |
| 15 | No unit tests | LOW | — (entire project) |
| 16 | Hardcoded Windows drive paths | LOW | `config.py`, `core/yara_engine.py` |
| 17 | Silent `except: pass` swallows errors | LOW | `ui/quarantine_tab.py`, `core/` |
| 18 | No proxy support | LOW | `workers/` |
| 19 | No session-level API response caching | LOW | `workers/` |
| 20 | Quarantine restore race condition | LOW | `ui/quarantine_tab.py` |

---

## Remediation Priority

### Immediate — Before Any Release

Address these before sharing or deploying the application in any form. These issues expose credentials and undermine the core security guarantees of the tool.

- **Bug 1** — Remove hardcoded API keys from source code
- **Bug 2** — Encrypt stored credentials using OS-managed secure storage
- **Bug 3** — Replace XOR quarantine with AES-256-GCM encryption

### Short-Term — Before Wider Use

Address these before the application is used by anyone beyond the original developer. These cause silent data loss, incorrect results, or application hangs.

- **Bug 4** — Add thread synchronization to shared stats dict
- **Bug 5** — Add request timeouts and proper retry logic with user feedback
- **Bug 6** — Validate and sanitize all user-provided file paths

### Medium-Term — Improve Robustness

Address these during the next development sprint. These represent correctness and reliability gaps that surface under realistic usage conditions.

- **Bug 7** — Correct the Claude API model identifier
- **Bug 8** — Update and externalize the Anthropic API version constant
- **Bug 9** — Switch geolocation requests to HTTPS
- **Bug 10** — Fix BulkHashWorker to retry rate-limited files
- **Bug 11** — Add safe JSON parsing with `.get()` fallbacks in Groq worker
- **Bug 12** — Add `json.JSONDecodeError` handling in ProcessListWorker
- **Bug 13** — Initialize `_last_response` in `AITab.__init__()`
- **Bug 14** — Wrap all file opens with `with` context managers

### Long-Term — Code Quality and Portability

Address these as part of ongoing maintenance to improve testability, portability, and defensive programming practices.

- **Bug 15** — Add a `tests/` directory with a baseline test suite
- **Bug 16** — Replace hardcoded drive paths with portable `Path.home()`-based defaults
- **Bug 17** — Replace silent `except: pass` blocks with logging or error signals
- **Bug 18** — Add proxy configuration support to all API workers
- **Bug 19** — Implement session-level LRU caching for repeated indicator lookups
- **Bug 20** — Fix quarantine restore to verify write success before deleting metadata
