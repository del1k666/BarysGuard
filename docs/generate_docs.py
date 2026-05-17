"""
Generate BarysGuard documentation PDFs in three languages.
Run from project root:  python docs/generate_docs.py
Output: docs/BarysGuard_Manual_EN.pdf
        docs/BarysGuard_Manual_RU.pdf
        docs/BarysGuard_Manual_KZ.pdf
"""
from fpdf import FPDF, XPos, YPos
from pathlib import Path

FONT_PATH = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
OUT_DIR   = Path(__file__).parent

# ── Light theme (readable in all PDF viewers and in print) ────────────────────
C_BG      = (255, 255, 255)
C_HEADER  = (30,  80, 162)   # dark blue header bar
C_ACCENT  = (30,  80, 162)   # headings
C_ACCENT2 = (0, 112, 192)    # h2 underline
C_TEXT    = (30,  30,  30)   # body text
C_MUTED   = (100, 100, 110)  # secondary text
C_CODE_BG = (245, 246, 248)  # code block background
C_CODE_TX = (50,  50,  80)   # code text
C_NOTE    = (180,  90,   0)  # warning / note
C_TIP     = (20, 140,  60)   # tip / success
C_RED     = (192,  30,  30)
C_BORDER  = (200, 205, 215)


class DocPDF(FPDF):
    def __init__(self, lang_name: str):
        super().__init__()
        self.lang_name = lang_name
        self.add_font("Arial", style="",  fname=FONT_PATH)
        self.add_font("Arial", style="B", fname=FONT_BOLD)
        self.set_auto_page_break(auto=True, margin=22)

    def _rgb(self, r, g, b):
        self.set_text_color(r, g, b)

    # ── Typography ────────────────────────────────────────────────────────────

    def h1(self, text: str):
        self.ln(5)
        self.set_font("Arial", "B", 17)
        self._rgb(*C_ACCENT)
        self.multi_cell(0, 9, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*C_ACCENT)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_line_width(0.2)
        self.ln(3)

    def h2(self, text: str):
        self.ln(3)
        self.set_font("Arial", "B", 12)
        self._rgb(*C_ACCENT)
        self.multi_cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*C_ACCENT2)
        self.line(10, self.get_y(), 110, self.get_y())
        self.set_draw_color(*C_BORDER)
        self.ln(2)

    def h3(self, text: str):
        self.ln(2)
        self.set_font("Arial", "B", 10)
        self._rgb(*C_TEXT)
        self.multi_cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def body(self, text: str):
        self.set_font("Arial", "", 10)
        self._rgb(*C_TEXT)
        self.multi_cell(0, 5.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def bullet(self, text: str, indent: int = 5):
        self.set_font("Arial", "", 10)
        self._rgb(*C_TEXT)
        x0 = self.get_x()
        self.set_x(x0 + indent)
        self.multi_cell(0, 5.5, f"•  {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(x0)

    def note(self, text: str):
        self.set_font("Arial", "B", 9)
        self._rgb(*C_NOTE)
        self.multi_cell(0, 5, f"[!]  {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self._rgb(*C_TEXT)
        self.ln(1)

    def tip(self, text: str):
        self.set_font("Arial", "B", 9)
        self._rgb(*C_TIP)
        self.multi_cell(0, 5, f"[OK] {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self._rgb(*C_TEXT)
        self.ln(1)

    def danger(self, text: str):
        self.set_font("Arial", "B", 9)
        self._rgb(*C_RED)
        self.multi_cell(0, 5, f"[!!] {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self._rgb(*C_TEXT)
        self.ln(1)

    def code(self, text: str):
        lines = text.strip().splitlines()
        pad = 4
        self.set_fill_color(*C_CODE_BG)
        self.set_draw_color(*C_BORDER)
        block_h = len(lines) * 5 + pad * 2
        self.rect(10, self.get_y(), 190, block_h, "FD")
        self.set_y(self.get_y() + pad)
        self.set_font("Arial", "", 9)
        self._rgb(*C_CODE_TX)
        for line in lines:
            self.set_x(14)
            self.multi_cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(pad)
        self._rgb(*C_TEXT)

    def separator(self):
        self.set_draw_color(*C_BORDER)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(5)

    def header(self):
        self.set_fill_color(*C_HEADER)
        self.rect(0, 0, 210, 12, "F")
        self.set_font("Arial", "B", 8)
        self.set_text_color(255, 255, 255)
        self.set_y(3)
        self.cell(0, 6, f"BarysGuard v2  —  {self.lang_name}", align="C")
        self.ln(10)

    def footer(self):
        self.set_y(-13)
        self.set_font("Arial", "", 8)
        self._rgb(*C_MUTED)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def title_page(self, title: str, subtitle: str, version: str = "v2.0"):
        self.add_page()
        self.set_fill_color(*C_HEADER)
        self.rect(0, 0, 210, 70, "F")
        self.set_y(18)
        self.set_font("Arial", "B", 30)
        self.set_text_color(255, 255, 255)
        self.cell(0, 14, "BARYSGUARD", align="C")
        self.ln(10)
        self.set_font("Arial", "B", 14)
        self.cell(0, 8, title, align="C")
        self.ln(7)
        self.set_font("Arial", "", 10)
        self.set_text_color(200, 215, 240)
        self.cell(0, 6, subtitle, align="C")
        self.ln(5)
        self.cell(0, 6, f"{version}  ·  2025", align="C")

        self.set_y(82)
        self._rgb(*C_TEXT)
        self.set_font("Arial", "", 10)
        self.cell(0, 6, "Threat Intelligence & Incident Response Platform", align="C")
        self.ln(8)
        self.set_draw_color(*C_BORDER)
        self.line(40, self.get_y(), 170, self.get_y())


# =============================================================================
#  ENGLISH
# =============================================================================
def build_en(pdf: DocPDF):
    pdf.title_page(
        "Administrator & Engineer Manual",
        "Complete reference: features, deployment, and operations",
    )

    # ── 1. Introduction ───────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("1. Introduction")
    pdf.body(
        "BarysGuard v2 is a desktop threat intelligence and incident-response platform "
        "for Windows. It enables security analysts, administrators, and engineers to "
        "detect malware artifacts, scan files and process memory with YARA rules, "
        "check file hashes against VirusTotal, collect network intelligence, manage "
        "multiple remote hosts, and perform network isolation — all from a single workstation."
    )

    pdf.h2("1.1 System Requirements")
    for item in [
        "OS: Windows 10 / 11 (64-bit) on both analyst workstation and monitored hosts",
        "Python 3.11+ with PyQt6, requests, psutil, cryptography",
        "Network access for API calls (VirusTotal, AbuseIPDB)",
        "yara64.exe or yara-python for YARA scanning",
        "pywinrm for automated remote agent deployment (optional)",
    ]:
        pdf.bullet(item)

    pdf.h2("1.2 First Launch")
    pdf.body("Run the application from the project root:")
    pdf.code("python main.py")
    pdf.body(
        "On first launch, config.json is created automatically. Open the Settings tab "
        "to enter your API keys (VirusTotal, AbuseIPDB)."
    )

    # ── 2. Features ───────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("2. Feature Reference")

    pdf.h2("2.1 Dashboard")
    pdf.body(
        "The Dashboard provides a real-time overview of scanning activity across four sub-tabs: "
        "Overview (live counters and event feed), Scans (scan statistics), "
        "Network (network lookup results), and Hosts (remote host activity). "
        "Every significant finding from any tab is automatically logged to the event feed."
    )

    pdf.h2("2.2 Hash Lookup")
    pdf.body(
        "Enter one or more SHA-256, MD5, or SHA-1 file hashes to query the VirusTotal API. "
        "Results show the detection ratio, file name, file type, and a direct link "
        "to the VirusTotal report. The free VT API supports 4 requests/minute — "
        "configure the delay in Settings."
    )

    pdf.h2("2.3 IOC Collection")
    pdf.body(
        "Collect Indicators of Compromise from the local host: running processes, "
        "active network connections, and autorun registry entries. "
        "Suspicious processes (outside C:\\Windows and C:\\Program Files) are highlighted automatically."
    )

    pdf.h2("2.4 YARA Scanner (local)")
    pdf.body(
        "Scan a local file or directory using YARA rules. The scanner ships with 40+ built-in "
        "rules covering ransomware (LockBit, BlackCat/ALPHV), RATs (AsyncRAT, QuasarRAT, Remcos), "
        "credential stealers (RedLine, Vidar), C2 frameworks (Sliver, Havoc, Chisel), "
        "and offensive tools (LOLBins, AMSI bypass, Defender tampering). "
        "You can also write custom rules in the built-in editor."
    )
    pdf.bullet("Select rules from the left panel (use the search box to filter 40+ rules).")
    pdf.bullet("Choose a target file or folder using the File / Folder buttons.")
    pdf.bullet("Click Scan YARA. Results appear in the table with severity color coding.")
    pdf.note("YARA scanning requires yara64.exe in the project folder or yara-python installed.")

    pdf.h2("2.5 Network Intel")
    pdf.body(
        "Look up IP addresses and domains against AbuseIPDB and VirusTotal. "
        "Results include abuse confidence score, country, ISP, and threat categories."
    )

    pdf.h2("2.6 Report Builder")
    pdf.body(
        "Generate incident reports in HTML format. Reports aggregate findings "
        "from all tabs, include timestamps, severity levels, and recommendations. "
        "Enable auto-save in Settings to export a report after every scan automatically."
    )

    pdf.h2("2.7 Memory Scanner (local)")
    pdf.body(
        "List all running local processes and scan a selected process executable with YARA rules. "
        "Useful for detecting in-memory malware that has not written files to disk. "
        "Requires elevated privileges for protected processes."
    )

    pdf.h2("2.8 Quarantine")
    pdf.body(
        "Move suspicious files to an isolated quarantine folder. Quarantined files "
        "are renamed to prevent accidental execution. You can restore or permanently "
        "delete them from this tab."
    )

    pdf.h2("2.9 Settings")
    pdf.body("Configure the application:")
    pdf.bullet("API keys for VirusTotal, AbuseIPDB")
    pdf.bullet("Default folders for results and quarantine")
    pdf.bullet("VirusTotal request rate limit")
    pdf.bullet("Auto-save reports toggle")
    pdf.bullet("Interface language: English / Russian / Kazakh")

    # ── 2.11 Hosts ────────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h2("2.10 Hosts — Multi-Host Remote Scanning")
    pdf.body(
        "The Hosts tab lets you manage and scan multiple Windows machines from a single "
        "BarysGuard instance. Each remote host runs a lightweight Flask HTTPS agent "
        "(agent.exe) on port 5555. Select a host from the left panel to access its five sub-tabs."
    )

    pdf.h3("Sub-tab: Status")
    pdf.body(
        "Shows host details (IP, port, last ping, last scan) and provides quick-action buttons: "
        "Ping, Deploy Agent, and navigation shortcuts to other sub-tabs."
    )

    pdf.h3("Sub-tab: File Scan")
    pdf.body(
        "Run YARA, IOC collection, and file hash scanning on a remote path. "
        "Contains two inner tabs:"
    )
    pdf.bullet("Scanning — compact rule selector with search filter, path input, IOC/hash options, Scan button.")
    pdf.bullet("Custom Rules — full YARA rule editor. Write rules on the right, manage saved rules on the left.")

    pdf.h3("Sub-tab: Memory Scan")
    pdf.body(
        "List all processes running on the remote host and scan their memory with YARA rules. "
        "Contains two inner tabs:"
    )
    pdf.bullet("Scanning — process table (with filter), rule selector with search, Scan Memory / Stop buttons.")
    pdf.bullet("Custom Rules — same full YARA rule editor as in File Scan.")

    pdf.h3("Sub-tab: Results")
    pdf.body(
        "Displays all scan findings in a table (Rule, Severity, File/Process) "
        "with a scan log below. Findings are color-coded by severity: "
        "Critical (red), High (orange), Medium (blue), Low (green)."
    )

    pdf.h3("Sub-tab: Isolation")
    pdf.body(
        "Perform network isolation on the remote host via Windows Firewall. See Section 2.11."
    )

    pdf.h2("2.11 Network Isolation (Incident Response)")
    pdf.body(
        "Network isolation blocks all inbound and outbound traffic on a compromised host "
        "while preserving the analyst's access. This is a critical incident-response capability "
        "that can contain an active attack without requiring physical access to the host."
    )
    pdf.danger(
        "Isolation modifies Windows Firewall profile defaults. The agent MUST be running "
        "as Administrator, otherwise isolation will fail with a 500 error."
    )

    pdf.h3("How it works")
    pdf.body(
        "Isolation uses Set-NetFirewallProfile to set the firewall default action to Block "
        "for all profiles (Domain, Private, Public), then adds explicit Allow rules for the "
        "management IP. This approach is correct: Allow rules override the profile default, "
        "but NOT explicit Block rules — so the management connection is always preserved."
    )
    pdf.bullet("Enter your management IP (pre-filled with your current IP) in the field.")
    pdf.bullet("Click 'Isolate Host'. Confirm the dialog.")
    pdf.bullet("The host is isolated. You can still reach the agent from your IP.")
    pdf.bullet("Click 'Restore Network' to remove isolation rules and reset the firewall profile.")
    pdf.note(
        "If isolation was applied but Restore fails (timeout), go to the isolated host "
        "physically and run: netsh advfirewall reset"
    )

    pdf.h3("Firewall rules created during isolation")
    pdf.bullet("IOCIsolate_AllowMgmt_In  — allows inbound from management IP")
    pdf.bullet("IOCIsolate_AllowMgmt_Out — allows outbound to management IP")
    pdf.body("Profile default: DefaultInboundAction = Block, DefaultOutboundAction = Block")
    pdf.body("On restore: both rules are deleted and profile defaults are set to NotConfigured.")

    # ── 3. Deploying the Agent ────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("3. Deploying a Remote Agent")

    pdf.h2("3.1 What the Agent Does")
    pdf.body(
        "agent.exe (compiled from agent.py) is a self-contained Flask HTTPS server that runs "
        "as a Windows Service or standalone process on each monitored host. "
        "All traffic is encrypted with a self-signed TLS certificate generated on first run. "
        "Every endpoint requires an API token in the X-Api-Token header."
    )
    pdf.h3("API Endpoints")
    for ep in [
        "GET  /ping              — returns hostname, OS, agent version",
        "GET  /info              — returns CPU / RAM / disk usage and logged-on users",
        "POST /scan/yara         — runs YARA rules against a remote path",
        "POST /scan/ioc          — collects processes, connections, autoruns",
        "POST /scan/memory       — scans process memory with YARA",
        "POST /scan/hashes       — returns SHA-256 hashes of files in a path",
        "GET  /processes         — returns the running process list",
        "GET  /network/status    — returns isolation status (isolated: true/false)",
        "POST /network/isolate   — applies network isolation (requires admin)",
        "POST /network/restore   — removes isolation rules and resets firewall profile",
    ]:
        pdf.bullet(ep)

    pdf.h2("3.2 Method A — Manual Deployment")
    pdf.body("Use this method when WinRM is not available on the target host.")

    pdf.h3("Step 1 — Copy agent.exe to the target host")
    pdf.body(
        "agent.exe is a self-contained executable — no Python required on the target. "
        "Copy it to C:\\IOCAgent\\ on the remote machine (USB, shared folder, or file copy)."
    )
    pdf.code(
        "# From your workstation (replace TARGET-HOST with actual name or IP):\n"
        "copy agent\\dist\\agent.exe \\\\TARGET-HOST\\c$\\IOCAgent\\"
    )

    pdf.h3("Step 2 — Run agent.exe to generate the token")
    pdf.code(
        "# On the target host, open PowerShell as Administrator:\n"
        "cd C:\\IOCAgent\n"
        ".\\agent.exe\n"
        "# Output:\n"
        "# [IOCAgent] Generating self-signed certificate...\n"
        "# [IOCAgent] v2.0 starting on https://0.0.0.0:5555\n"
        "# [IOCAgent] Token: a3f7c9d2...  (32-char hex)"
    )
    pdf.tip("The token is also saved in C:\\IOCAgent\\token.txt — copy it for Step 5.")

    pdf.h3("Step 3 — Install as Windows Service (recommended)")
    pdf.code(
        "# Run as Administrator:\n"
        ".\\agent.exe --install\n"
        ".\\agent.exe --start\n"
        "# Or: net start IOCAgent"
    )
    pdf.note("Running as a service ensures the agent starts automatically after reboot and has SYSTEM privileges needed for network isolation.")

    pdf.h3("Step 4 — Allow port 5555 in Windows Firewall")
    pdf.code(
        "netsh advfirewall firewall add rule name=\"IOCAgent\" ^\n"
        "  dir=in action=allow protocol=TCP localport=5555"
    )

    pdf.h3("Step 5 — Add the host in BarysGuard")
    pdf.body("Open the Hosts tab, click '+ Add', and fill in:")
    pdf.bullet("Name: any label (e.g. SRV-DC01)")
    pdf.bullet("IP: the target host IP address")
    pdf.bullet("Port: 5555")
    pdf.bullet("Token: the value from token.txt")

    pdf.h3("Step 6 — Test connectivity")
    pdf.body("Click the Ping button. The status indicator should turn green (online).")

    pdf.h2("3.3 Method B — Automated Deployment via UI")
    pdf.body(
        "If the target host has WinRM enabled (port 5985), you can deploy the agent "
        "directly from the BarysGuard UI without touching the remote machine manually."
    )

    pdf.h3("Prerequisites on the target host")
    pdf.code(
        "# Run as Administrator on the TARGET host:\n"
        "winrm quickconfig\n"
        "# For NTLM (domain environment):\n"
        "Set-Item WSMan:\\localhost\\Service\\Auth\\NTLM -Value true"
    )
    pdf.note("WinRM is disabled by default on Windows workstations.")

    pdf.h3("Build agent.exe (run once on your workstation)")
    pdf.code(
        "cd agent\n"
        "build.bat          # Produces: agent\\dist\\agent.exe"
    )

    pdf.h3("Deploy from UI")
    pdf.bullet("Open the Hosts tab and select or add a host.")
    pdf.bullet("Go to the Status sub-tab and click 'Deploy Agent'.")
    pdf.bullet("Enter the target host IP, administrator username, and password.")
    pdf.bullet("Click OK — BarysGuard copies agent.exe, installs the service, and retrieves the token automatically.")

    pdf.h2("3.4 Verifying the Agent")
    pdf.code(
        "$tok = Get-Content C:\\IOCAgent\\token.txt\n"
        "Invoke-WebRequest -Uri https://TARGET-IP:5555/ping `\n"
        "  -Headers @{\"X-Api-Token\"=$tok} -SkipCertificateCheck\n"
        "# Expected: {\"status\": \"ok\", \"hostname\": \"TARGET-HOST\", ...}"
    )

    # ── 4. Custom YARA Rules ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("4. Writing Custom YARA Rules")
    pdf.body(
        "Both the local YARA Scanner tab and the remote Hosts tab (File Scan and Memory Scan) "
        "include a full YARA rule editor. Custom rules are stored in memory for the current session "
        "and can be written, edited, updated, and deleted."
    )

    pdf.h2("4.1 Using the Rule Editor")
    pdf.bullet("Open the 'Custom Rules' inner tab inside File Scan or Memory Scan.")
    pdf.bullet("Write your rule in the editor on the right. The rule name is auto-detected from the 'rule <Name>' declaration.")
    pdf.bullet("Click 'Add / Update Rule'. The rule appears in the list on the left and is checked in the rule selector.")
    pdf.bullet("Click a rule in the left list to load it back into the editor for modification.")
    pdf.bullet("Click 'Delete Rule' to remove a custom rule from both the list and the rule selector.")

    pdf.h2("4.2 YARA Rule Template")
    pdf.code(
        "rule MyRule {\n"
        "    meta:\n"
        "        description = \"Detects suspicious pattern\"\n"
        "        author      = \"Your name\"\n"
        "        severity    = \"high\"\n"
        "    strings:\n"
        "        $s1 = \"malicious_string\" ascii nocase\n"
        "        $s2 = { 4D 5A 90 00 }          // hex pattern\n"
        "        $re = /http[s]?:\\/\\/[0-9]+\\.[0-9]+/ // regex\n"
        "    condition:\n"
        "        any of them\n"
        "}"
    )
    pdf.note("YARA 4.5+ treats unreferenced strings as errors. Every declared string must appear in the condition.")

    pdf.h2("4.3 Built-in Rules Reference")
    pdf.body("The following rules are included (40+ total):")
    categories = {
        "Ransomware": ["LockBit", "BlackCat_ALPHV", "Ransomware_Generic"],
        "RATs": ["AsyncRAT", "QuasarRAT", "Remcos_RAT"],
        "Stealers": ["RedLine_Stealer", "Vidar_Stealer", "AgentTesla"],
        "C2 Frameworks": ["Sliver_C2", "Havoc_C2", "Chisel_Tunnel", "CobaltStrike_Beacon"],
        "Droppers": ["GuLoader", "Emotet_Loader"],
        "Exploits": ["Log4Shell_CVE_2021_44228"],
        "Web Shells": ["WebShell_PHP", "WebShell_ASPX"],
        "Defense Evasion": ["AMSI_Bypass", "DefenderTampering", "Packed_UPX"],
        "Lateral Movement": ["Mimikatz_Strings", "LOLBins_Abuse"],
        "Persistence": ["Scheduled_Task_Abuse", "Network_Recon"],
    }
    for cat, rules in categories.items():
        pdf.bullet(f"{cat}: {', '.join(rules)}")

    # ── 5. Security Notes ─────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("5. Security Notes")
    pdf.bullet("The API token is a 64-character random hex string generated once at installation and stored in token.txt.")
    pdf.bullet("All agent traffic uses TLS (self-signed certificate). The client uses verify=False — acceptable for isolated internal networks.")
    pdf.bullet("Protect token.txt with filesystem ACLs. Anyone with the token can control the agent.")
    pdf.bullet("WinRM credentials used during Deploy are not stored by the application.")
    pdf.bullet("config.json stores API keys in plain text — do not commit to version control.")
    pdf.bullet("The agent runs as SYSTEM when installed as a service. Restrict access to C:\\IOCAgent\\.")
    pdf.bullet("Network Isolation requires the agent to run as Administrator (SYSTEM service satisfies this).")
    pdf.danger(
        "Always specify your management IP before isolating a host. "
        "If you isolate without a valid management IP, you will lose remote access."
    )

    # ── 6. Troubleshooting ────────────────────────────────────────────────────
    pdf.h1("6. Troubleshooting")

    pdf.h3("Agent shows 'offline' after ping")
    pdf.bullet("Verify agent.exe is running: tasklist | findstr agent")
    pdf.bullet("Check port 5555 is open: netstat -ano | findstr 5555")
    pdf.bullet("Confirm the token in hosts.json matches token.txt on the remote host.")
    pdf.bullet("Check Windows Firewall allows port 5555 inbound.")

    pdf.h3("Isolation fails with 500 error")
    pdf.bullet("The agent is not running as Administrator.")
    pdf.bullet("Fix: reinstall the agent as a Windows Service (runs as SYSTEM).")
    pdf.code(
        ".\\agent.exe --uninstall\n"
        ".\\agent.exe --install\n"
        ".\\agent.exe --start"
    )

    pdf.h3("Restore fails with connection timeout")
    pdf.bullet("Isolation was applied but the management IP was not allowlisted correctly.")
    pdf.body("Fix: go to the isolated host physically and run:")
    pdf.code("netsh advfirewall reset")

    pdf.h3("YARA scan returns COMPILE_ERR")
    pdf.bullet("The rule contains a syntax error. Open the Rule Editor and check the rule text.")
    pdf.bullet("YARA 4.5+ requires every declared string to be used in the condition.")

    pdf.h3("VirusTotal returns 'Quota exceeded'")
    pdf.bullet("Increase the rate limit delay in Settings (default 15 s for free API).")
    pdf.bullet("Verify the API key at virustotal.com.")

    pdf.h3("Deploy fails — pywinrm not installed")
    pdf.code("pip install pywinrm")

    pdf.h3("Deploy fails — WinRM connection error")
    pdf.bullet("Enable WinRM on target: winrm quickconfig")
    pdf.bullet("Check firewall rules for port 5985 on the target host.")


# =============================================================================
#  RUSSIAN
# =============================================================================
def build_ru(pdf: DocPDF):
    pdf.title_page(
        "Руководство администратора и инженера",
        "Полный справочник: функции, развёртывание и эксплуатация",
    )

    pdf.add_page()
    pdf.h1("1. Введение")
    pdf.body(
        "BarysGuard v2 — десктопная платформа threat intelligence и реагирования на инциденты "
        "для Windows. Позволяет аналитикам безопасности, администраторам и инженерам обнаруживать "
        "артефакты вредоносных программ, сканировать файлы и память процессов правилами YARA, "
        "проверять хэши через VirusTotal, управлять несколькими удалёнными хостами "
        "и выполнять сетевую изоляцию — всё с единой рабочей станции."
    )

    pdf.h2("1.1 Системные требования")
    for item in [
        "ОС: Windows 10 / 11 (64-bit) на рабочей станции аналитика и контролируемых хостах",
        "Python 3.11+ с библиотеками PyQt6, requests, psutil, cryptography",
        "Сетевой доступ для API (VirusTotal, AbuseIPDB)",
        "yara64.exe или yara-python для YARA-сканирования",
        "pywinrm для автоматического развёртывания агента (опционально)",
    ]:
        pdf.bullet(item)

    pdf.h2("1.2 Первый запуск")
    pdf.body("Запустите приложение из корня проекта:")
    pdf.code("python main.py")
    pdf.body(
        "При первом запуске автоматически создаётся config.json. "
        "Откройте вкладку Настройки и введите API-ключи."
    )

    pdf.add_page()
    pdf.h1("2. Справочник функций")

    pdf.h2("2.1 Dashboard (Главная)")
    pdf.body(
        "Главная страница отображает активность сканирования в реальном времени — четыре подвкладки: "
        "Обзор (счётчики и лента событий), Сканирования, Сеть, Хосты. "
        "Каждая значимая находка из любой вкладки автоматически попадает в ленту событий."
    )

    pdf.h2("2.2 Проверка хэшей (Hash Lookup)")
    pdf.body(
        "Введите один или несколько хэшей SHA-256/MD5/SHA-1 для запроса в VirusTotal. "
        "Результаты: соотношение обнаружений, имя файла, тип, ссылка на отчёт. "
        "Бесплатный API VT — 4 запроса/мин; задержку настраивают в Настройках."
    )

    pdf.h2("2.3 Сбор IOC")
    pdf.body(
        "Сбор индикаторов компрометации с локального хоста: запущенные процессы, "
        "активные сетевые соединения и записи автозапуска в реестре. "
        "Подозрительные процессы (за пределами C:\\Windows и C:\\Program Files) выделяются автоматически."
    )

    pdf.h2("2.4 YARA-сканер (локальный)")
    pdf.body(
        "Сканирование локального файла или папки правилами YARA. В комплекте 40+ встроенных правил: "
        "шифровальщики (LockBit, BlackCat/ALPHV), RAT (AsyncRAT, QuasarRAT, Remcos), "
        "похитители данных (RedLine, Vidar), C2-фреймворки (Sliver, Havoc, Chisel), "
        "инструменты уклонения (AMSI bypass, отключение Defender, LOLBins). "
        "Можно писать собственные правила во встроенном редакторе."
    )
    pdf.bullet("Выберите правила на левой панели (поиск по 40+ правилам).")
    pdf.bullet("Укажите файл или папку.")
    pdf.bullet("Нажмите «Сканировать YARA». Результаты отобразятся с цветовой маркировкой по серьёзности.")
    pdf.note("YARA-сканирование требует yara64.exe в папке проекта или yara-python.")

    pdf.h2("2.5 Сетевая разведка (Network Intel)")
    pdf.body(
        "Поиск IP-адресов и доменов в AbuseIPDB и VirusTotal. "
        "Результаты: оценка доверия к злоупотреблениям, страна, провайдер, категории угроз."
    )

    pdf.h2("2.6 Конструктор отчётов")
    pdf.body(
        "Создание отчётов об инцидентах в формате HTML. "
        "Отчёты агрегируют данные со всех вкладок, включают временные метки, "
        "уровни серьёзности и рекомендации. Включите автосохранение в Настройках."
    )

    pdf.h2("2.7 Сканер памяти (локальный)")
    pdf.body(
        "Просмотр всех локальных процессов и сканирование их исполняемых файлов правилами YARA. "
        "Обнаруживает вредоносные программы в памяти без файлов на диске. "
        "Для защищённых процессов требуются права администратора."
    )

    pdf.h2("2.8 Карантин")
    pdf.body(
        "Перемещение подозрительных файлов в изолированную папку карантина. "
        "Файлы переименовываются для предотвращения случайного запуска. "
        "Можно восстановить или удалить безвозвратно."
    )

    pdf.h2("2.9 Настройки")
    pdf.body("Конфигурация приложения:")
    pdf.bullet("API-ключи VirusTotal, AbuseIPDB")
    pdf.bullet("Папки по умолчанию для результатов и карантина")
    pdf.bullet("Задержка запросов к VirusTotal")
    pdf.bullet("Автосохранение отчётов")
    pdf.bullet("Язык интерфейса: English / Русский / Қазақша")

    pdf.add_page()
    pdf.h2("2.10 Хосты — многохостовое удалённое сканирование")
    pdf.body(
        "Вкладка Хосты позволяет управлять несколькими Windows-машинами и сканировать их "
        "с единой рабочей станции. На каждом удалённом хосте работает лёгкий Flask HTTPS-агент "
        "(agent.exe) на порту 5555. Выберите хост слева для доступа к пяти подвкладкам."
    )

    pdf.h3("Подвкладка: Статус")
    pdf.body(
        "Данные хоста (IP, порт, последний пинг, скан) и кнопки быстрых действий: "
        "Пинг, Развернуть агент, навигация к другим вкладкам."
    )

    pdf.h3("Подвкладка: Файловый скан")
    pdf.body("Запуск YARA, сбор IOC и хэширование файлов на удалённом пути. Две внутренние вкладки:")
    pdf.bullet("Сканирование — компактный выбор правил с поиском, путь, опции IOC/хэши, кнопка Сканировать.")
    pdf.bullet("Свои правила — полноценный редактор YARA-правил. Пишите правила справа, управляйте сохранёнными слева.")

    pdf.h3("Подвкладка: Memory Scan")
    pdf.body("Просмотр процессов и сканирование их памяти правилами YARA. Две внутренние вкладки:")
    pdf.bullet("Сканирование — таблица процессов с фильтром, выбор правил с поиском, кнопки Scan Memory / Стоп.")
    pdf.bullet("Свои правила — тот же редактор YARA-правил.")

    pdf.h3("Подвкладка: Результаты")
    pdf.body(
        "Таблица находок (Правило, Серьёзность, Файл/Процесс) и лог сканирования. "
        "Цветовая маркировка: Critical (красный), High (оранжевый), Medium (синий), Low (зелёный)."
    )

    pdf.h3("Подвкладка: Изоляция")
    pdf.body("Сетевая изоляция удалённого хоста через Windows Firewall. Подробнее — в разделе 2.11.")

    pdf.h2("2.11 Сетевая изоляция (реагирование на инциденты)")
    pdf.body(
        "Сетевая изоляция блокирует весь входящий и исходящий трафик на скомпрометированном хосте, "
        "сохраняя доступ аналитика. Это ключевая возможность для сдерживания активной атаки "
        "без физического доступа к хосту."
    )
    pdf.danger(
        "Изоляция изменяет дефолтное действие профиля Windows Firewall. "
        "Агент ДОЛЖЕН запускаться с правами администратора, иначе изоляция вернёт ошибку 500."
    )

    pdf.h3("Как работает изоляция")
    pdf.body(
        "Используется Set-NetFirewallProfile для установки Block как действия по умолчанию "
        "для всех профилей брандмауэра (Domain, Private, Public), затем создаются явные "
        "Allow-правила для управляющего IP. Allow-правила побеждают дефолт профиля, "
        "поэтому соединение с аналитиком всегда сохраняется."
    )
    pdf.bullet("Введите ваш IP-адрес в поле управляющего IP (заполняется автоматически).")
    pdf.bullet("Нажмите «Изолировать хост» и подтвердите.")
    pdf.bullet("Хост изолирован. Доступ с вашего IP сохранён.")
    pdf.bullet("Нажмите «Восстановить сеть» для снятия изоляции.")
    pdf.note(
        "Если Восстановление не проходит (таймаут), подойдите к хосту физически и выполните: "
        "netsh advfirewall reset"
    )

    pdf.add_page()
    pdf.h1("3. Развёртывание агента")

    pdf.h2("3.1 Что делает агент")
    pdf.body(
        "agent.exe — самодостаточный исполняемый файл, работающий как Flask HTTPS-сервер "
        "на каждом контролируемом хосте. Python на целевом хосте не требуется. "
        "Весь трафик шифруется TLS-сертификатом, создаваемым автоматически. "
        "Каждый запрос требует токен в заголовке X-Api-Token."
    )
    pdf.h3("Конечные точки API")
    for ep in [
        "GET  /ping              — имя хоста, ОС, версия агента",
        "GET  /info              — загрузка CPU/RAM/диск и пользователи",
        "POST /scan/yara         — YARA-сканирование пути",
        "POST /scan/ioc          — сбор процессов, соединений, автозапуска",
        "POST /scan/memory       — сканирование памяти процесса",
        "POST /scan/hashes       — хэши файлов в пути",
        "GET  /processes         — список запущенных процессов",
        "GET  /network/status    — статус изоляции (isolated: true/false)",
        "POST /network/isolate   — применить изоляцию (требует admin)",
        "POST /network/restore   — снять изоляцию и восстановить профиль",
    ]:
        pdf.bullet(ep)

    pdf.h2("3.2 Метод A — Ручное развёртывание")
    pdf.body("Используйте, если WinRM недоступен на целевом хосте.")

    pdf.h3("Шаг 1 — Скопируйте agent.exe на целевой хост")
    pdf.body("Python на целевой машине не нужен — agent.exe самодостаточен.")
    pdf.code(
        "# С рабочей станции (замените TARGET-HOST на реальный адрес):\n"
        "copy agent\\dist\\agent.exe \\\\TARGET-HOST\\c$\\IOCAgent\\"
    )

    pdf.h3("Шаг 2 — Запустите агент для генерации токена")
    pdf.code(
        "# На целевом хосте, PowerShell от администратора:\n"
        "cd C:\\IOCAgent\n"
        ".\\agent.exe\n"
        "# [IOCAgent] Generating self-signed certificate...\n"
        "# [IOCAgent] v2.0 starting on https://0.0.0.0:5555\n"
        "# [IOCAgent] Token: a3f7c9d2...  (32-символьный hex)"
    )
    pdf.tip("Токен также сохранён в C:\\IOCAgent\\token.txt.")

    pdf.h3("Шаг 3 — Установите как службу Windows (рекомендуется)")
    pdf.code(
        "# От администратора:\n"
        ".\\agent.exe --install\n"
        ".\\agent.exe --start"
    )
    pdf.note("Служба запускается от имени SYSTEM — это даёт права администратора для изоляции.")

    pdf.h3("Шаг 4 — Откройте порт 5555 в брандмауэре")
    pdf.code(
        "netsh advfirewall firewall add rule name=\"IOCAgent\" ^\n"
        "  dir=in action=allow protocol=TCP localport=5555"
    )

    pdf.h3("Шаг 5 — Добавьте хост в BarysGuard")
    pdf.body("Вкладка Хосты → «+ Добавить»:")
    pdf.bullet("Имя: любая метка (например, SRV-DC01)")
    pdf.bullet("IP: IP-адрес целевого хоста")
    pdf.bullet("Порт: 5555")
    pdf.bullet("Токен: значение из token.txt")

    pdf.h3("Шаг 6 — Проверьте подключение")
    pdf.body("Нажмите кнопку Ping. Статус должен стать зелёным.")

    pdf.h2("3.3 Метод Б — Автоматическое развёртывание через UI")
    pdf.body(
        "Если на целевом хосте включён WinRM (порт 5985), агента можно развернуть "
        "прямо из интерфейса BarysGuard."
    )
    pdf.h3("Требования на целевом хосте")
    pdf.code(
        "# От администратора на ЦЕЛЕВОМ хосте:\n"
        "winrm quickconfig\n"
        "# Для NTLM (домен):\n"
        "Set-Item WSMan:\\localhost\\Service\\Auth\\NTLM -Value true"
    )
    pdf.h3("Сборка agent.exe (один раз)")
    pdf.code("cd agent && build.bat   # Создаёт: agent\\dist\\agent.exe")
    pdf.h3("Развёртывание из UI")
    pdf.bullet("Вкладка Хосты → подвкладка Статус → кнопка «Развернуть агент».")
    pdf.bullet("Введите IP целевого хоста, имя администратора и пароль.")
    pdf.bullet("BarysGuard скопирует agent.exe, установит службу и автоматически получит токен.")

    pdf.add_page()
    pdf.h1("4. Собственные YARA-правила")
    pdf.body(
        "Редактор YARA-правил встроен в вкладки Файловый скан и Memory Scan (как удалённого хоста, "
        "так и локальный сканер). Правила хранятся в памяти текущей сессии."
    )
    pdf.h2("4.1 Использование редактора")
    pdf.bullet("Откройте внутреннюю вкладку «Свои правила» в Файловом скане или Memory Scan.")
    pdf.bullet("Напишите правило в редакторе (справа). Имя определяется автоматически из объявления rule.")
    pdf.bullet("Нажмите «Добавить / Обновить правило». Правило появится в списке слева и будет отмечено галочкой.")
    pdf.bullet("Кликните правило в левом списке, чтобы загрузить его обратно в редактор.")
    pdf.bullet("Кнопка «Удалить правило» удаляет его из списка и из выбора правил.")

    pdf.h2("4.2 Шаблон правила YARA")
    pdf.code(
        "rule MyRule {\n"
        "    meta:\n"
        "        description = \"Описание правила\"\n"
        "        author      = \"Ваше имя\"\n"
        "        severity    = \"high\"\n"
        "    strings:\n"
        "        $s1 = \"подозрительная_строка\" ascii nocase\n"
        "        $s2 = { 4D 5A 90 00 }     // hex-паттерн\n"
        "    condition:\n"
        "        any of them\n"
        "}"
    )
    pdf.note("YARA 4.5+ считает ошибкой объявленные строки, не использованные в condition.")

    pdf.h1("5. Замечания по безопасности")
    pdf.bullet("API-токен — случайная строка из 64 hex-символов, создаётся единожды при установке.")
    pdf.bullet("Весь трафик агента шифруется TLS (самоподписанный сертификат). verify=False у клиента приемлемо для изолированных внутренних сетей.")
    pdf.bullet("Ограничьте доступ к token.txt через ACL — владелец токена полностью контролирует агент.")
    pdf.bullet("Учётные данные WinRM не сохраняются приложением.")
    pdf.bullet("config.json содержит ключи API в открытом виде — не добавляйте в VCS.")
    pdf.bullet("Агент работает от SYSTEM при установке как служба. Ограничьте доступ к C:\\IOCAgent\\.")
    pdf.danger("Всегда указывайте управляющий IP перед изоляцией. Без него вы потеряете удалённый доступ.")

    pdf.h1("6. Устранение неполадок")

    pdf.h3("Агент отображается как offline")
    pdf.bullet("Проверьте: tasklist | findstr agent")
    pdf.bullet("Порт открыт: netstat -ano | findstr 5555")
    pdf.bullet("Токен в hosts.json совпадает с token.txt на удалённом хосте.")
    pdf.bullet("Правило брандмауэра для порта 5555 создано.")

    pdf.h3("Изоляция не работает, ошибка 500")
    pdf.bullet("Агент запущен без прав администратора.")
    pdf.body("Решение: переустановить как службу Windows:")
    pdf.code(".\\agent.exe --uninstall && .\\agent.exe --install && .\\agent.exe --start")

    pdf.h3("Восстановление — таймаут соединения")
    pdf.bullet("Изоляция применена, но управляющий IP не получил доступ.")
    pdf.body("Решение: физически подойти к хосту и выполнить:")
    pdf.code("netsh advfirewall reset")

    pdf.h3("YARA-скан возвращает COMPILE_ERR")
    pdf.bullet("Синтаксическая ошибка в правиле — откройте вкладку «Свои правила» и исправьте.")
    pdf.bullet("YARA 4.5+: все объявленные строки должны быть использованы в condition.")

    pdf.h3("VirusTotal: Quota exceeded")
    pdf.bullet("Увеличьте задержку запросов в Настройках.")

    pdf.h3("Deploy: pywinrm not installed")
    pdf.code("pip install pywinrm")

    pdf.h3("Deploy: ошибка подключения WinRM")
    pdf.bullet("winrm quickconfig — на целевом хосте от администратора.")
    pdf.bullet("Правило брандмауэра для порта 5985.")


# =============================================================================
#  KAZAKH
# =============================================================================
def build_kz(pdf: DocPDF):
    pdf.title_page(
        "Әкімші және инженер нұсқаулығы",
        "Толық анықтамалық: мүмкіндіктер, орналастыру және пайдалану",
    )

    pdf.add_page()
    pdf.h1("1. Кіріспе")
    pdf.body(
        "BarysGuard v2 — Windows үшін threat intelligence және оқиғаларға жауап беру десктоп платформасы. "
        "Қауіпсіздік талдаушыларына, әкімшілерге және инженерлерге зиянды бағдарламалардың "
        "артефактілерін анықтауға, YARA ережелерімен файлдар мен процесс жадын сканерлеуге, "
        "VirusTotal арқылы файл хэштерін тексеруге, желі барлауын жүргізуге, "
        "бірнеше қашықтағы хостты басқаруға және желі оқшаулауын орындауға — "
        "бәрін бір жұмыс станциясынан мүмкіндік береді."
    )

    pdf.h2("1.1 Жүйелік талаптар")
    for item in [
        "ОЖ: Windows 10 / 11 (64-bit) — аналитик станциясы мен бақыланатын хосттарда",
        "Python 3.11+ (PyQt6, requests, psutil, cryptography)",
        "API қоңырауларына желіге қол жетімділік (VirusTotal, AbuseIPDB)",
        "yara64.exe немесе yara-python — YARA сканерлеу үшін",
        "pywinrm — агентті автоматты орналастыру үшін (міндетті емес)",
    ]:
        pdf.bullet(item)

    pdf.h2("1.2 Алғашқы іске қосу")
    pdf.body("Қолданбаны жоба түбірінен іске қосыңыз:")
    pdf.code("python main.py")
    pdf.body("Алғашқы іске қосуда config.json автоматты жасалады. API кілттерін Параметрлер бөлімінде енгізіңіз.")

    pdf.add_page()
    pdf.h1("2. Мүмкіндіктер анықтамалығы")

    pdf.h2("2.1 Басты бет (Dashboard)")
    pdf.body(
        "Сканерлеу белсенділігіне нақты уақытта шолу — төрт ішкі бөлім: "
        "Шолу (есептегіштер мен оқиғалар тізімі), Сканерлеулер, Желі, Хосттар. "
        "Кез келген бөлімдегі маңызды нәтиже оқиғалар тізіміне автоматты тіркеледі."
    )

    pdf.h2("2.2 Хэш іздеу (Hash Lookup)")
    pdf.body(
        "VirusTotal API-ын сұрастыру үшін SHA-256/MD5/SHA-1 хэштерін енгізіңіз. "
        "Нәтижелер: анықтау үлесі, файл атауы, түрі, есепке сілтеме. "
        "Тегін VT API — 4 сұрау/мин."
    )

    pdf.h2("2.3 IOC жинақ")
    pdf.body(
        "Жергілікті хосттан компромисс индикаторларын жинау: процестер, "
        "желі қосылымдары және реестрдің автожүктеу жазбалары. "
        "Күдікті процестер (C:\\Windows және C:\\Program Files сыртында) автоматты белгіленеді."
    )

    pdf.h2("2.4 YARA сканер (жергілікті)")
    pdf.body(
        "YARA ережелерімен жергілікті файл немесе қалтаны сканерлеу. "
        "40-тан астам кірістірілген ережелермен жеткізіледі: "
        "шифрлаушылар (LockBit, BlackCat/ALPHV), RAT (AsyncRAT, QuasarRAT, Remcos), "
        "деректер ұрлаушылар (RedLine, Vidar), C2 фреймворктары (Sliver, Havoc, Chisel). "
        "Өзіндік ережелерді кірістірілген редактор арқылы жазуға болады."
    )
    pdf.note("YARA сканерлеу үшін жоба қалтасында yara64.exe немесе yara-python болуы керек.")

    pdf.h2("2.5 Желі барлауы (Network Intel)")
    pdf.body("IP-мекенжайлар мен домендерді AbuseIPDB және VirusTotal арқылы тексеру.")

    pdf.h2("2.6 Есептер (Report Builder)")
    pdf.body("HTML форматында оқиға есептерін жасау. Барлық бөлімдердің нәтижелерін біріктіреді.")

    pdf.h2("2.7 Жады сканері (жергілікті)")
    pdf.body(
        "Жергілікті процестерді тізімдеу және олардың жадын YARA ережелерімен сканерлеу. "
        "Дискідегі файлсыз жадыдағы зиянды бағдарламаларды анықтайды."
    )

    pdf.h2("2.8 Карантин")
    pdf.body("Күдікті файлдарды оқшауланған қалтаға жылжыту, қалпына келтіру немесе жою.")

    pdf.h2("2.9 Параметрлер")
    pdf.bullet("VirusTotal, AbuseIPDB API кілттері")
    pdf.bullet("Нәтижелер мен карантин үшін әдепкі қалталар")
    pdf.bullet("VirusTotal сұрау кідірісі  |  Есептерді автосақтау")
    pdf.bullet("Интерфейс тілі: English / Русский / Қазақша")

    pdf.add_page()
    pdf.h2("2.10 Хосттар — Көп хостты қашықтан сканерлеу")
    pdf.body(
        "Хосттар бөлімі бірнеше Windows машиналарын бір жұмыс станциясынан басқаруға мүмкіндік береді. "
        "Әр қашықтағы хостта 5555 портында Flask HTTPS-агент (agent.exe) жұмыс істейді. "
        "Сол тізімнен хостты таңдаңыз — бес ішкі бөлімге қол жеткізіледі."
    )

    pdf.h3("Ішкі бөлім: Мәртебе (Статус)")
    pdf.body("Хост деректері және жылдам әрекет батырмалары: Ping, Агент орнату, навигация.")

    pdf.h3("Ішкі бөлім: Файлдық сканерлеу")
    pdf.body("Қашықтағы жолда YARA, IOC жинақ және хэшті іске қосу. Екі ішкі бөлім:")
    pdf.bullet("Сканерлеу — ережелер тізімі, жол, IOC/хэш опциялары, Сканерлеу батырмасы.")
    pdf.bullet("Өз ережелері — толыққанды YARA ережелер редакторы.")

    pdf.h3("Ішкі бөлім: Memory Scan")
    pdf.body("Қашықтағы процестерді тізімдеу және жадын сканерлеу. Екі ішкі бөлім:")
    pdf.bullet("Сканерлеу — процестер кестесі, ережелер тізімі, Scan Memory / Стоп батырмалары.")
    pdf.bullet("Өз ережелері — YARA ережелер редакторы.")

    pdf.h3("Ішкі бөлім: Нәтижелер")
    pdf.body("Барлық нәтижелердің кестесі (Ереже, Деңгей, Файл/Процесс) және сканерлеу журналы.")

    pdf.h3("Ішкі бөлім: Оқшаулау")
    pdf.body("Windows Firewall арқылы желі оқшаулау. 2.11 бөлімін қараңыз.")

    pdf.h2("2.11 Желі оқшаулау (Оқиғаларға жауап беру)")
    pdf.body(
        "Желі оқшаулау бұзылған хосттың барлық трафигін блоктайды, "
        "аналитиктің қол жетімділігін сақтай отырып. "
        "Физикалық қол жеткізусіз белсенді шабуылды тоқтату үшін пайдаланылады."
    )
    pdf.danger(
        "Оқшаулау Windows Firewall профиль әдепкісін өзгертеді. "
        "Агент Әкімші құқықтарымен іске қосылуы ТИІС."
    )

    pdf.h3("Қалай жұмыс істейді")
    pdf.body(
        "Set-NetFirewallProfile барлық профильдер үшін Block әдепкі әрекетін орнатады, "
        "содан кейін басқарушы IP үшін Allow ережелері жасалады. "
        "Allow ережелері профиль әдепкісін басады — аналитик қосылымы сақталады."
    )
    pdf.bullet("Басқарушы IP-мекенжайды (автоматты толтырылады) растаңыз.")
    pdf.bullet("«Хостты оқшаулау» батырмасын басып, растаңыз.")
    pdf.bullet("«Желіні қалпына келтіру» батырмасы оқшаулауды алып тастайды.")
    pdf.note(
        "Егер қалпына келтіру таймаут берсе, хостқа физикалық барып орындаңыз: "
        "netsh advfirewall reset"
    )

    pdf.add_page()
    pdf.h1("3. Агентті орналастыру")

    pdf.h2("3.1 Агент не жасайды")
    pdf.body(
        "agent.exe — бақыланатын хостта жұмыс істейтін өздігінен Flask HTTPS сервері. "
        "Мақсатты машинада Python қажет емес. Барлық трафик TLS арқылы шифрланады. "
        "Әр сұрау X-Api-Token тақырыбындағы токенді талап етеді."
    )
    pdf.h3("API конечных нүктелері")
    for ep in [
        "GET  /ping              — хост аты, ОЖ, агент нұсқасы",
        "GET  /info              — CPU/RAM/диск жүктемесі",
        "POST /scan/yara         — YARA жолды сканерлеу",
        "POST /scan/ioc          — процестер, қосылымдар, автожүктеу жинақ",
        "POST /scan/memory       — процесс жадын сканерлеу",
        "POST /scan/hashes       — жолдағы файл хэштері",
        "GET  /processes         — іске қосылған процестер тізімі",
        "GET  /network/status    — оқшаулау мәртебесі",
        "POST /network/isolate   — оқшаулауды қолдану (admin керек)",
        "POST /network/restore   — оқшаулауды алып тастау",
    ]:
        pdf.bullet(ep)

    pdf.h2("3.2 A Әдісі — Қолмен орналастыру")

    pdf.h3("1-қадам — agent.exe-ді мақсатты хостқа көшіру")
    pdf.code("copy agent\\dist\\agent.exe \\\\МАҚСАТ-ХОСТ\\c$\\IOCAgent\\")

    pdf.h3("2-қадам — Токен жасау үшін агентті іске қосу")
    pdf.code(
        "# Мақсатты хостта Әкімші PowerShell:\n"
        "cd C:\\IOCAgent\n"
        ".\\agent.exe\n"
        "# [IOCAgent] Token: a3f7c9d2...  (32 таңбалы hex)"
    )
    pdf.tip("Токен C:\\IOCAgent\\token.txt файлына да сақталады.")

    pdf.h3("3-қадам — Windows Service ретінде орнату (ұсынылады)")
    pdf.code(".\\agent.exe --install && .\\agent.exe --start")
    pdf.note("Қызмет SYSTEM атынан іске қосылады — оқшаулау үшін қажет Әкімші құқықтары беріледі.")

    pdf.h3("4-қадам — 5555 портын ашу")
    pdf.code("netsh advfirewall firewall add rule name=\"IOCAgent\" dir=in action=allow protocol=TCP localport=5555")

    pdf.h3("5-қадам — Хостты BarysGuard-ге қосу")
    pdf.body("Хосттар бөлімі → «+ Қосу»: атауы, IP, порт (5555), токен.")

    pdf.h2("3.3 Б Әдісі — UI арқылы автоматты орналастыру")
    pdf.body("Мақсатты хостта WinRM қосылған болса (5985 порты).")
    pdf.h3("Алғышарттар")
    pdf.code(
        "# Мақсатты хостта Әкімші ретінде:\n"
        "winrm quickconfig"
    )
    pdf.h3("agent.exe жинау")
    pdf.code("cd agent && build.bat")
    pdf.h3("UI-дан орналастыру")
    pdf.bullet("Хосттар → Мәртебе → «Агент орнату» батырмасы.")
    pdf.bullet("IP, Әкімші аты, құпия сөз → OK.")

    pdf.add_page()
    pdf.h1("4. Өзіндік YARA ережелері")
    pdf.body(
        "YARA ережелер редакторы Файлдық сканерлеу және Memory Scan ішкі бөлімдерінде бар "
        "(қашықтағы хоста да, жергілікті сканерде де). Ережелер ағымдағы сессия жадында сақталады."
    )
    pdf.h2("4.1 Редакторды пайдалану")
    pdf.bullet("«Өз ережелері» ішкі бөлімін ашыңыз.")
    pdf.bullet("Оң жақ редакторда ереже жазыңыз. Атауы rule декларациясынан автоматты алынады.")
    pdf.bullet("«Қосу / Жаңарту» батырмасын басыңыз.")
    pdf.bullet("Сол жақ тізімдегі ережені нұқыңыз — редакторға жүктеледі.")
    pdf.bullet("«Жою» батырмасы тізімнен және ережелер таңдауынан алып тастайды.")

    pdf.h2("4.2 YARA ережесінің үлгісі")
    pdf.code(
        "rule MyRule {\n"
        "    meta:\n"
        "        description = \"Ереже сипаттамасы\"\n"
        "        severity    = \"high\"\n"
        "    strings:\n"
        "        $s1 = \"зиянды_жол\" ascii nocase\n"
        "        $s2 = { 4D 5A 90 00 }\n"
        "    condition:\n"
        "        any of them\n"
        "}"
    )
    pdf.note("YARA 4.5+: condition-да пайдаланылмаған жолдар — қате.")

    pdf.h1("5. Қауіпсіздік ескертпелері")
    pdf.bullet("API токені — 64 таңбалы кездейсоқ hex, token.txt файлында сақталады.")
    pdf.bullet("Барлық трафик TLS шифрланады (өздігінен қол қойылған сертификат).")
    pdf.bullet("token.txt қол жетімділігін ACL арқылы шектеңіз.")
    pdf.bullet("config.json API кілттерін ашық сақтайды — VCS-қа қоспаңыз.")
    pdf.danger("Оқшаулаудан бұрын басқарушы IP-ді міндетті түрде көрсетіңіз. Болмаса қашықтан кіруден айрыласыз.")

    pdf.h1("6. Ақауларды жою")

    pdf.h3("Агент 'офлайн'")
    pdf.bullet("tasklist | findstr agent — іске қосылғанын тексеріңіз.")
    pdf.bullet("netstat -ano | findstr 5555 — порт ашық па.")
    pdf.bullet("Токен token.txt мәніне сәйкес келуі тиіс.")

    pdf.h3("Оқшаулау 500 қатесі")
    pdf.bullet("Агент Әкімші құқықтарынсыз іске қосылған.")
    pdf.code(".\\agent.exe --uninstall && .\\agent.exe --install && .\\agent.exe --start")

    pdf.h3("Қалпына келтіру — таймаут")
    pdf.body("Хостқа физикалық барып орындаңыз:")
    pdf.code("netsh advfirewall reset")

    pdf.h3("YARA COMPILE_ERR")
    pdf.bullet("Ережеде синтаксис қатесі бар — «Өз ережелері» бөлімін ашыңыз.")

    pdf.h3("Deploy: pywinrm орнатылмаған")
    pdf.code("pip install pywinrm")

    pdf.h3("Deploy: WinRM қосылым қатесі")
    pdf.bullet("winrm quickconfig — мақсатты хостта Әкімші ретінде.")


# =============================================================================
#  Main
# =============================================================================
def main():
    docs = [
        ("BarysGuard_Manual_EN.pdf", "English",  build_en),
        ("BarysGuard_Manual_RU.pdf", "Русский",  build_ru),
        ("BarysGuard_Manual_KZ.pdf", "Қазақша",  build_kz),
    ]
    for fname, lang_name, builder in docs:
        print(f"Generating {fname} ...", end=" ", flush=True)
        pdf = DocPDF(lang_name)
        builder(pdf)
        out = OUT_DIR / fname
        pdf.output(str(out))
        print(f"OK  ({out.stat().st_size // 1024} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
