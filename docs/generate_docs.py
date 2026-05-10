"""
Generate IOC Analyzer documentation PDFs in three languages.
Run from project root:  python docs/generate_docs.py
Output: docs/IOC_Analyzer_Manual_EN.pdf
        docs/IOC_Analyzer_Manual_RU.pdf
        docs/IOC_Analyzer_Manual_KZ.pdf
"""
from fpdf import FPDF, XPos, YPos
from pathlib import Path
import sys

FONT_PATH = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
OUT_DIR   = Path(__file__).parent

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG      = (13,  17,  23)
C_HEADER  = (22,  27,  34)
C_ACCENT  = (88, 166, 255)
C_TEXT    = (201, 209, 217)
C_MUTED   = (139, 148, 158)
C_GREEN   = (63, 185, 80)
C_RED     = (248, 81,  73)
C_YELLOW  = (210, 153, 34)


# ─────────────────────────────────────────────────────────────────────────────
class DocPDF(FPDF):
    def __init__(self, lang_name: str):
        super().__init__()
        self.lang_name = lang_name
        self.add_font("Arial",      style="",  fname=FONT_PATH)
        self.add_font("Arial",      style="B", fname=FONT_BOLD)
        self.set_auto_page_break(auto=True, margin=20)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _txt(self, r, g, b):
        self.set_text_color(r, g, b)

    def h1(self, text: str):
        self.set_font("Arial", "B", 18)
        self._txt(*C_ACCENT)
        self.ln(4)
        self.multi_cell(0, 9, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def h2(self, text: str):
        self.set_font("Arial", "B", 13)
        self._txt(*C_ACCENT)
        self.ln(3)
        self.multi_cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*C_ACCENT)
        self.line(self.get_x(), self.get_y(), self.get_x() + 170, self.get_y())
        self.ln(3)

    def h3(self, text: str):
        self.set_font("Arial", "B", 11)
        self._txt(*C_TEXT)
        self.ln(2)
        self.multi_cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def body(self, text: str):
        self.set_font("Arial", "", 10)
        self._txt(*C_TEXT)
        self.multi_cell(0, 5.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def bullet(self, text: str, indent: int = 6):
        self.set_font("Arial", "", 10)
        self._txt(*C_TEXT)
        x0 = self.get_x()
        self.set_x(x0 + indent)
        self.multi_cell(0, 5.5, f"•  {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(x0)

    def note(self, text: str):
        self.set_font("Arial", "B", 9)
        self._txt(*C_YELLOW)
        self.multi_cell(0, 5, f"! {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self._txt(*C_TEXT)
        self.ln(1)

    def tip(self, text: str):
        self.set_font("Arial", "B", 9)
        self._txt(*C_GREEN)
        self.multi_cell(0, 5, f"OK  {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self._txt(*C_TEXT)
        self.ln(1)

    def code(self, text: str):
        self.set_font("Arial", "", 9)
        self._txt(*C_MUTED)
        for line in text.strip().splitlines():
            self.multi_cell(0, 5, "    " + line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self._txt(*C_TEXT)
        self.ln(1)

    def separator(self):
        self.set_draw_color(*C_HEADER)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(5)

    def header(self):
        self.set_fill_color(*C_HEADER)
        self.rect(0, 0, 210, 14, "F")
        self.set_font("Arial", "B", 9)
        self._txt(*C_MUTED)
        self.set_y(4)
        self.cell(0, 6, f"IOC Analyzer  —  {self.lang_name}", align="C")
        self.ln(10)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "", 8)
        self._txt(*C_MUTED)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def title_page(self, title: str, subtitle: str, version: str = "v2.0"):
        self.add_page()
        self.set_fill_color(*C_BG)
        self.rect(0, 0, 210, 297, "F")
        self.set_y(60)
        self.set_font("Arial", "B", 32)
        self._txt(*C_ACCENT)
        self.cell(0, 16, "IOC ANALYZER", align="C")
        self.ln(10)
        self.set_font("Arial", "B", 16)
        self._txt(*C_TEXT)
        self.cell(0, 9, title, align="C")
        self.ln(8)
        self.set_font("Arial", "", 11)
        self._txt(*C_MUTED)
        self.cell(0, 7, subtitle, align="C")
        self.ln(6)
        self.set_font("Arial", "", 10)
        self.cell(0, 6, version + "  ·  2025", align="C")
        self.ln(40)
        self.set_fill_color(*C_ACCENT)
        self.rect(40, self.get_y(), 130, 1, "F")
        self.ln(8)
        self.set_font("Arial", "", 10)
        self._txt(*C_MUTED)
        self.cell(0, 6, "Threat Intelligence & Incident Response Platform", align="C")


# ─────────────────────────────────────────────────────────────────────────────
#  ENGLISH
# ─────────────────────────────────────────────────────────────────────────────
def build_en(pdf: DocPDF):
    pdf.title_page(
        "Administrator & Engineer Manual",
        "Complete reference: features, deployment, and operations",
    )

    # ── 1. Introduction ───────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("1. Introduction")
    pdf.body(
        "IOC Analyzer is a desktop threat intelligence and incident-response platform "
        "for Windows. It enables security analysts, administrators, and engineers to "
        "detect malware artifacts, scan files with YARA rules, check file hashes "
        "against VirusTotal, collect network intelligence, and scan multiple hosts "
        "remotely from a single workstation."
    )

    pdf.h2("1.1 System Requirements")
    for item in [
        "OS: Windows 10 / 11 (64-bit)",
        "Python 3.11+ with PyQt6, requests, psutil",
        "Network access for API calls (VirusTotal, AbuseIPDB, Groq/Claude)",
        "yara64.exe OR yara-python for YARA scanning",
        "pywinrm for automated remote agent deployment (optional)",
    ]:
        pdf.bullet(item)

    pdf.h2("1.2 First Launch")
    pdf.body("Run the application from the project root:")
    pdf.code("python main.py")
    pdf.body(
        "On first launch, config.json is created automatically. Open Settings to "
        "enter your API keys (VirusTotal, AbuseIPDB, Groq or Claude)."
    )

    # ── 2. Features ───────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("2. Feature Reference")

    pdf.h2("2.1 Dashboard")
    pdf.body(
        "The Dashboard provides a real-time overview of scanning activity. "
        "It displays counters for YARA hits, scanned hashes, network lookups, "
        "and a live event feed that records every significant finding across all tabs."
    )

    pdf.h2("2.2 Hash Lookup")
    pdf.body(
        "Enter one or more SHA-256/MD5/SHA-1 file hashes to query the VirusTotal API. "
        "Results show the detection ratio, file name, file type, and a direct link "
        "to the VirusTotal report. The free VT API supports 4 requests/minute; "
        "configure the delay in Settings."
    )

    pdf.h2("2.3 IOC Collection")
    pdf.body(
        "Collect and manage Indicators of Compromise from the local host: running "
        "processes, active network connections, and autorun registry entries. "
        "Suspicious processes (outside C:\\Windows and C:\\Program Files) are "
        "highlighted automatically."
    )

    pdf.h2("2.4 YARA Scanner")
    pdf.body(
        "Scan a file or directory using YARA rules. The scanner ships with 40+ built-in "
        "rules covering ransomware, RATs, credential stealers, C2 frameworks, and "
        "offensive tools. You can also load custom .yar files or write rules in the "
        "built-in editor."
    )
    pdf.bullet("Select one or more rules (or 'Select all') from the left panel.")
    pdf.bullet("Choose a target file or folder using the File / Folder buttons.")
    pdf.bullet("Click Scan YARA. Results appear in the table with severity colour coding.")
    pdf.note("YARA scanning requires either yara64.exe in the project folder or yara-python installed.")

    pdf.h2("2.5 Network Intel")
    pdf.body(
        "Look up IP addresses and domains against AbuseIPDB and VirusTotal. "
        "Results include abuse confidence score, country, ISP, and threat categories."
    )

    pdf.h2("2.6 AI Assistant")
    pdf.body(
        "Chat with an AI model (Groq / Claude) for threat analysis. Paste IOC data, "
        "log snippets, or YARA rule code to get explanations, MITRE ATT&CK mapping, "
        "and remediation recommendations. Configure the provider and API key in Settings."
    )

    pdf.h2("2.7 Report Builder")
    pdf.body(
        "Generate incident reports in PDF or HTML format. Reports aggregate findings "
        "from all tabs, include timestamps, severity levels, and recommendations. "
        "Enable auto-save in Settings to export a report after every scan automatically."
    )

    pdf.h2("2.8 Memory Scanner")
    pdf.body(
        "List all running processes and scan a selected process's executable image "
        "with YARA rules. Useful for detecting in-memory malware that has not written "
        "files to disk. Requires elevated privileges for some processes."
    )

    pdf.h2("2.9 Quarantine")
    pdf.body(
        "Move suspicious files to an isolated quarantine folder. Quarantined files "
        "are renamed to prevent accidental execution. You can restore or permanently "
        "delete them from this tab."
    )

    pdf.h2("2.10 Settings")
    pdf.body("Configure the application:")
    pdf.bullet("API keys for VirusTotal, AbuseIPDB, Groq, Claude")
    pdf.bullet("Default folders for results and quarantine")
    pdf.bullet("VirusTotal request rate limit")
    pdf.bullet("Auto-save reports toggle")
    pdf.bullet("Interface language: ENG / RUS / ҚАЗ")

    pdf.h2("2.11 Hosts (Multi-Host Scanning)")
    pdf.body(
        "The Hosts tab lets you manage and scan multiple Windows machines from a single "
        "IOC Analyzer instance. Each remote host runs a lightweight Flask HTTPS agent "
        "(agent.exe) that exposes scanning endpoints over port 5555."
    )
    pdf.bullet("Add a host: enter its IP, port (5555), and API token.")
    pdf.bullet("Ping: verify connectivity to the agent.")
    pdf.bullet("Scan: run YARA, IOC collection, and/or file hash scanning on the remote host.")
    pdf.bullet("Deploy: automatically install the agent via WinRM (requires WinRM enabled).")
    pdf.body(
        "The host selector dropdown in the main header shows the currently active host. "
        "Selecting a host here makes it the default for all scanning operations."
    )

    # ── 3. Deploying the Agent ────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("3. Deploying a Remote Agent — Step by Step")

    pdf.h2("3.1 What the Agent Does")
    pdf.body(
        "agent.py is a self-contained Flask HTTPS server that runs as a Windows Service "
        "on each monitored host. It exposes six scanning endpoints protected by an "
        "API token. All traffic is encrypted with a self-signed TLS certificate "
        "generated automatically on first run."
    )
    pdf.bullet("GET  /ping   — returns hostname, OS, agent version")
    pdf.bullet("GET  /info   — returns CPU/RAM/disk usage and logged-on users")
    pdf.bullet("POST /scan/yara    — runs YARA rules against a path")
    pdf.bullet("POST /scan/ioc     — collects processes, connections, autoruns")
    pdf.bullet("POST /scan/memory  — scans a process executable with YARA")
    pdf.bullet("POST /scan/hashes  — returns SHA-256 hashes of files in a path")

    pdf.h2("3.2 Method A — Manual Deployment")
    pdf.body("Use this method when WinRM is not available on the target host.")

    pdf.h3("Step 1 — Install Python on the target host")
    pdf.code("winget install Python.Python.3.12")

    pdf.h3("Step 2 — Copy the agent folder to the target host")
    pdf.body("Copy the agent/ directory to C:\\IOCAgent\\ on the remote machine.")
    pdf.code(
        "# From your workstation:\n"
        "copy agent\\agent.py \\\\TARGET-HOST\\c$\\IOCAgent\\\n"
        "# Or use USB / shared folder"
    )

    pdf.h3("Step 3 — Install agent dependencies on the target")
    pdf.code("pip install flask psutil cryptography pywin32")

    pdf.h3("Step 4 — Run the agent in foreground to generate token")
    pdf.code(
        "cd C:\\IOCAgent\n"
        "python agent.py\n"
        "# Output:\n"
        "# [IOCAgent] Generating self-signed certificate...\n"
        "# [IOCAgent] v1.0.0 starting on https://0.0.0.0:5555\n"
        "# [IOCAgent] Token: a3f7c9d2... (32-char hex)"
    )
    pdf.tip("Copy the token — you will need it in Step 7. It is also saved in C:\\IOCAgent\\token.txt.")

    pdf.h3("Step 5 — Install as Windows Service (optional but recommended)")
    pdf.code(
        "# Run as Administrator:\n"
        "python agent.py --install\n"
        "python agent.py --start\n"
        "# Or use: net start IOCAgent"
    )

    pdf.h3("Step 6 — Allow port 5555 in Windows Firewall")
    pdf.code(
        "netsh advfirewall firewall add rule name=\"IOCAgent\" "
        "dir=in action=allow protocol=TCP localport=5555"
    )

    pdf.h3("Step 7 — Add the host in IOC Analyzer")
    pdf.body("Open the 🌐 Hosts tab, click '+ Add', and fill in:")
    pdf.bullet("Name: any label (e.g. SRV-DC01)")
    pdf.bullet("IP: the target host IP address")
    pdf.bullet("Port: 5555")
    pdf.bullet("Token: the value from token.txt")

    pdf.h3("Step 8 — Test connectivity")
    pdf.body("Click the ⟳ Ping button. The status should turn green (● online).")

    pdf.h3("Step 9 — Run a scan")
    pdf.body(
        "Select YARA and/or IOC checkboxes, set a scan path (e.g. C:\\Users), "
        "and click ▶ Scan. Results appear in the table below."
    )

    pdf.h2("3.3 Method B — Automated Deployment via UI")
    pdf.body(
        "If the target host has WinRM enabled (port 5985), you can deploy the agent "
        "directly from the IOC Analyzer UI without touching the remote machine manually."
    )

    pdf.h3("Prerequisites on the target host")
    pdf.code(
        "# Run as Administrator on the TARGET host:\n"
        "winrm quickconfig\n"
        "Set-Item WSMan:\\localhost\\Service\\AllowUnencrypted -Value true\n"
        "Set-Item WSMan:\\localhost\\Service\\Auth\\Basic -Value true\n"
        "# Or for NTLM (domain environment):\n"
        "Set-Item WSMan:\\localhost\\Service\\Auth\\NTLM -Value true"
    )
    pdf.note("WinRM is disabled by default on Windows workstations. The commands above must be run with admin rights.")

    pdf.h3("Build agent.exe first (run once on your workstation)")
    pdf.code(
        "cd agent\n"
        "build.bat\n"
        "# Produces: agent\\dist\\agent.exe"
    )

    pdf.h3("Deploy from UI")
    pdf.bullet("Open the 🌐 Hosts tab.")
    pdf.bullet("Click 📦 Deploy Agent.")
    pdf.bullet("Enter the target host IP, administrator username, and password.")
    pdf.bullet("Click OK — IOC Analyzer copies agent.exe, installs the service, and retrieves the token automatically.")
    pdf.bullet("Click '+ Add' and paste the displayed token to register the host.")

    pdf.h2("3.4 Verifying the Agent is Running")
    pdf.body("From a browser or PowerShell on the local network:")
    pdf.code(
        "$tok = Get-Content C:\\IOCAgent\\token.txt\n"
        "Invoke-WebRequest -Uri https://TARGET-IP:5555/ping \\\n"
        "  -Headers @{\"X-Api-Token\"=$tok} -SkipCertificateCheck"
    )
    pdf.body("Expected response:")
    pdf.code(
        "{\"status\": \"ok\", \"hostname\": \"TARGET-HOST\", "
        "\"os\": \"Windows 11\", \"agent_version\": \"1.0.0\"}"
    )

    # ── 4. Security Notes ─────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("4. Security Notes")
    pdf.bullet("The API token is a 64-character random hex string generated once at installation.")
    pdf.bullet("All agent traffic is encrypted with TLS (self-signed certificate). verify=False is used by the client since the cert is self-signed — this is acceptable for isolated internal networks.")
    pdf.bullet("The token is stored in plain text in token.txt on the agent host. Protect this file with filesystem ACLs.")
    pdf.bullet("WinRM credentials are not stored by the application. They are used only during the Deploy operation and then discarded.")
    pdf.bullet("config.json contains API keys in plain text. Do not commit it to version control or share it.")
    pdf.bullet("The agent runs as a Windows Service under SYSTEM or a dedicated service account. Restrict access to C:\\Program Files\\IOCAgent\\.")

    # ── 5. Troubleshooting ────────────────────────────────────────────────────
    pdf.h1("5. Troubleshooting")

    pdf.h3("Agent shows 'offline' after ping")
    pdf.bullet("Verify agent.exe / agent.py is running on the remote host.")
    pdf.bullet("Check that port 5555 is open in the firewall: netstat -ano | findstr 5555")
    pdf.bullet("Confirm the token in hosts.json matches token.txt on the remote host.")

    pdf.h3("YARA scan returns COMPILE_ERR")
    pdf.bullet("The rule contains a syntax error. Open the Rule Editor and check the rule text.")
    pdf.bullet("YARA 4.5.5+ treats unreferenced strings as errors. Ensure every declared string is used in the condition.")

    pdf.h3("VirusTotal returns 'Quota exceeded'")
    pdf.bullet("The free VT API is limited to 4 requests/minute. Increase the rate limit delay in Settings.")
    pdf.bullet("Check that your API key is valid at virustotal.com.")

    pdf.h3("Deploy fails with 'pywinrm not installed'")
    pdf.code("pip install pywinrm")

    pdf.h3("Deploy fails with WinRM connection error")
    pdf.bullet("Ensure WinRM is enabled on the target: winrm quickconfig")
    pdf.bullet("Check firewall rules for port 5985 on the target host.")
    pdf.bullet("Try pinging the target to verify basic connectivity.")


# ─────────────────────────────────────────────────────────────────────────────
#  RUSSIAN
# ─────────────────────────────────────────────────────────────────────────────
def build_ru(pdf: DocPDF):
    pdf.title_page(
        "Руководство администратора и инженера",
        "Полный справочник: функции, развёртывание и эксплуатация",
    )

    pdf.add_page()
    pdf.h1("1. Введение")
    pdf.body(
        "IOC Analyzer — это десктопная платформа threat intelligence и реагирования на инциденты "
        "для Windows. Она позволяет аналитикам безопасности, администраторам и инженерам "
        "обнаруживать артефакты вредоносных программ, сканировать файлы правилами YARA, "
        "проверять хэши файлов через VirusTotal, собирать сетевую разведку и сканировать "
        "несколько хостов удалённо с одной рабочей станции."
    )

    pdf.h2("1.1 Системные требования")
    for item in [
        "ОС: Windows 10 / 11 (64-bit)",
        "Python 3.11+ с библиотеками PyQt6, requests, psutil",
        "Сетевой доступ для API (VirusTotal, AbuseIPDB, Groq/Claude)",
        "yara64.exe ИЛИ yara-python для YARA-сканирования",
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
        "Dashboard отображает статистику сканирования в реальном времени: "
        "количество срабатываний YARA, проверенных хэшей, сетевых запросов, "
        "а также живую ленту событий со всех вкладок."
    )

    pdf.h2("2.2 Hash Lookup (Проверка хэшей)")
    pdf.body(
        "Введите один или несколько хэшей (SHA-256/MD5/SHA-1) для запроса в VirusTotal. "
        "Результаты показывают соотношение обнаружений, имя файла, тип и ссылку на отчёт. "
        "Бесплатный API VT — 4 запроса/мин; настройте задержку в Настройках."
    )

    pdf.h2("2.3 IOC Collection (Сбор IOC)")
    pdf.body(
        "Сбор индикаторов компрометации с локального хоста: запущенные процессы, "
        "активные сетевые соединения и записи автозапуска в реестре. "
        "Подозрительные процессы (за пределами C:\\Windows и C:\\Program Files) "
        "выделяются автоматически."
    )

    pdf.h2("2.4 YARA Scanner (YARA-сканер)")
    pdf.body(
        "Сканирование файла или папки с помощью правил YARA. В комплекте поставляется "
        "более 40 встроенных правил: шифровальщики, RAT, похитители учётных данных, "
        "C2-фреймворки и наступательные инструменты. Можно загружать собственные .yar-файлы "
        "или писать правила во встроенном редакторе."
    )
    pdf.bullet("Выберите одно или несколько правил (или «Выбрать все») на левой панели.")
    pdf.bullet("Укажите файл или папку кнопками Файл / Папка.")
    pdf.bullet("Нажмите «Сканировать YARA». Результаты отобразятся в таблице с цветовой маркировкой.")
    pdf.note("YARA-сканирование требует yara64.exe в папке проекта или установленный yara-python.")

    pdf.h2("2.5 Network Intel (Сетевая разведка)")
    pdf.body(
        "Поиск IP-адресов и доменов в AbuseIPDB и VirusTotal. "
        "Результаты включают оценку доверия к злоупотреблениям, страну, провайдера и категории угроз."
    )

    pdf.h2("2.6 AI Assistant (ИИ-ассистент)")
    pdf.body(
        "Чат с моделью ИИ (Groq / Claude) для анализа угроз. Вставьте данные IOC, "
        "фрагменты логов или код YARA-правила, чтобы получить пояснения, маппинг MITRE ATT&CK "
        "и рекомендации по устранению. Настройте провайдера и ключ API в Настройках."
    )

    pdf.h2("2.7 Report Builder (Конструктор отчётов)")
    pdf.body(
        "Создание отчётов об инцидентах в форматах PDF или HTML. "
        "Отчёты агрегируют данные со всех вкладок, включают временны́е метки, "
        "уровни серьёзности и рекомендации. "
        "Включите автосохранение в Настройках для экспорта после каждого сканирования."
    )

    pdf.h2("2.8 Memory Scan (Сканирование памяти)")
    pdf.body(
        "Просмотр всех запущенных процессов и сканирование образа исполняемого файла "
        "выбранного процесса правилами YARA. Полезно для обнаружения вредоносных программ "
        "в памяти без файлов на диске. Для некоторых процессов требуются права администратора."
    )

    pdf.h2("2.9 Quarantine (Карантин)")
    pdf.body(
        "Перемещение подозрительных файлов в изолированную папку карантина. "
        "Файлы в карантине переименовываются для предотвращения случайного запуска. "
        "Их можно восстановить или удалить безвозвратно."
    )

    pdf.h2("2.10 Settings (Настройки)")
    pdf.body("Конфигурация приложения:")
    pdf.bullet("API-ключи VirusTotal, AbuseIPDB, Groq, Claude")
    pdf.bullet("Папки по умолчанию для результатов и карантина")
    pdf.bullet("Задержка запросов к VirusTotal")
    pdf.bullet("Автосохранение отчётов")
    pdf.bullet("Язык интерфейса: ENG / RUS / ҚАЗ")

    pdf.h2("2.11 Hosts (Многохостовое сканирование)")
    pdf.body(
        "Вкладка Hosts позволяет управлять несколькими Windows-машинами и сканировать их "
        "с единой рабочей станции. На каждом удалённом хосте работает лёгкий Flask HTTPS-агент "
        "(agent.exe), предоставляющий конечные точки сканирования через порт 5555."
    )
    pdf.bullet("Добавить хост: введите IP, порт (5555) и API-токен.")
    pdf.bullet("Ping: проверьте доступность агента.")
    pdf.bullet("Сканировать: запустите YARA, IOC и/или хэширование файлов на удалённом хосте.")
    pdf.bullet("Deploy: автоматически установите агент через WinRM (требует включённого WinRM).")

    pdf.add_page()
    pdf.h1("3. Развёртывание агента — пошаговая инструкция")

    pdf.h2("3.1 Что делает агент")
    pdf.body(
        "agent.py — самодостаточный Flask HTTPS-сервер, работающий как служба Windows "
        "на каждом контролируемом хосте. Он предоставляет шесть конечных точек сканирования, "
        "защищённых API-токеном. Весь трафик зашифрован самоподписанным TLS-сертификатом, "
        "создаваемым автоматически при первом запуске."
    )

    pdf.h2("3.2 Метод A — Ручное развёртывание")
    pdf.body("Используйте этот метод, если WinRM недоступен на целевом хосте.")

    pdf.h3("Шаг 1 — Установите Python на целевом хосте")
    pdf.code("winget install Python.Python.3.12")

    pdf.h3("Шаг 2 — Скопируйте папку agent/ на целевой хост")
    pdf.body("Скопируйте содержимое agent/ в C:\\IOCAgent\\ на удалённой машине.")

    pdf.h3("Шаг 3 — Установите зависимости агента на целевом хосте")
    pdf.code("pip install flask psutil cryptography pywin32")

    pdf.h3("Шаг 4 — Запустите агент в фоновом режиме для генерации токена")
    pdf.code(
        "cd C:\\IOCAgent\n"
        "python agent.py\n"
        "# Вывод:\n"
        "# [IOCAgent] Generating self-signed certificate...\n"
        "# [IOCAgent] v1.0.0 starting on https://0.0.0.0:5555\n"
        "# [IOCAgent] Token: a3f7c9d2... (32-символьный hex)"
    )
    pdf.tip("Скопируйте токен — он понадобится на шаге 7. Также сохранён в C:\\IOCAgent\\token.txt.")

    pdf.h3("Шаг 5 — Установите как службу Windows (рекомендуется)")
    pdf.code(
        "# Запустить от имени администратора:\n"
        "python agent.py --install\n"
        "python agent.py --start"
    )

    pdf.h3("Шаг 6 — Откройте порт 5555 в брандмауэре Windows")
    pdf.code(
        "netsh advfirewall firewall add rule name=\"IOCAgent\" "
        "dir=in action=allow protocol=TCP localport=5555"
    )

    pdf.h3("Шаг 7 — Добавьте хост в IOC Analyzer")
    pdf.body("Откройте вкладку Hosts, нажмите «+ Добавить» и заполните:")
    pdf.bullet("Имя: любая метка (например, SRV-DC01)")
    pdf.bullet("IP: IP-адрес целевого хоста")
    pdf.bullet("Порт: 5555")
    pdf.bullet("Токен: значение из token.txt")

    pdf.h3("Шаг 8 — Проверьте подключение")
    pdf.body("Нажмите кнопку ⟳ Ping. Статус должен стать зелёным (● online).")

    pdf.h3("Шаг 9 — Запустите сканирование")
    pdf.body(
        "Установите флажки YARA и/или IOC, задайте путь сканирования (например, C:\\Users) "
        "и нажмите ▶ Сканировать. Результаты появятся в таблице ниже."
    )

    pdf.h2("3.3 Метод Б — Автоматическое развёртывание через UI")
    pdf.body(
        "Если на целевом хосте включён WinRM (порт 5985), агента можно развернуть "
        "прямо из интерфейса IOC Analyzer без ручного вмешательства."
    )

    pdf.h3("Требования на целевом хосте")
    pdf.code(
        "# Запустить от имени администратора на ЦЕЛЕВОМ хосте:\n"
        "winrm quickconfig\n"
        "# Для NTLM (доменная среда):\n"
        "Set-Item WSMan:\\localhost\\Service\\Auth\\NTLM -Value true"
    )
    pdf.note("WinRM по умолчанию отключён на рабочих станциях Windows. Команды выполняются с правами администратора.")

    pdf.h3("Соберите agent.exe (один раз на рабочей станции)")
    pdf.code(
        "cd agent\n"
        "build.bat\n"
        "# Создаёт: agent\\dist\\agent.exe"
    )

    pdf.h3("Развёртывание из UI")
    pdf.bullet("Откройте вкладку Hosts.")
    pdf.bullet("Нажмите 📦 Deploy агента.")
    pdf.bullet("Введите IP целевого хоста, имя администратора и пароль.")
    pdf.bullet("Нажмите OK — IOC Analyzer скопирует agent.exe, установит службу и получит токен автоматически.")
    pdf.bullet("Нажмите «+ Добавить» и вставьте отображённый токен.")

    pdf.h2("3.4 Проверка работы агента")
    pdf.code(
        "$tok = Get-Content C:\\IOCAgent\\token.txt\n"
        "Invoke-WebRequest -Uri https://TARGET-IP:5555/ping \\\n"
        "  -Headers @{\"X-Api-Token\"=$tok} -SkipCertificateCheck"
    )

    pdf.add_page()
    pdf.h1("4. Замечания по безопасности")
    pdf.bullet("API-токен — случайная строка из 64 hex-символов, создаётся единожды при установке.")
    pdf.bullet("Весь трафик агента шифруется TLS (самоподписанный сертификат).")
    pdf.bullet("Токен хранится в открытом виде в token.txt — ограничьте доступ к этому файлу через ACL.")
    pdf.bullet("Учётные данные WinRM не сохраняются приложением и используются только при операции Deploy.")
    pdf.bullet("config.json содержит ключи API в открытом виде — не добавляйте в VCS и не передавайте третьим лицам.")

    pdf.h1("5. Устранение неполадок")

    pdf.h3("Агент отображается как offline")
    pdf.bullet("Проверьте, запущен ли agent.exe / agent.py на удалённом хосте.")
    pdf.bullet("Убедитесь, что порт 5555 открыт: netstat -ano | findstr 5555")
    pdf.bullet("Токен в hosts.json должен совпадать с token.txt на удалённом хосте.")

    pdf.h3("YARA-скан возвращает COMPILE_ERR")
    pdf.bullet("Правило содержит синтаксическую ошибку — откройте Редактор правил и исправьте.")
    pdf.bullet("YARA 4.5.5+ считает ошибкой неиспользуемые строки — убедитесь, что все переменные присутствуют в condition.")

    pdf.h3("Deploy не работает: 'pywinrm not installed'")
    pdf.code("pip install pywinrm")

    pdf.h3("Deploy не работает: ошибка подключения WinRM")
    pdf.bullet("Убедитесь, что WinRM включён: winrm quickconfig")
    pdf.bullet("Проверьте правила брандмауэра для порта 5985 на целевом хосте.")


# ─────────────────────────────────────────────────────────────────────────────
#  KAZAKH
# ─────────────────────────────────────────────────────────────────────────────
def build_kz(pdf: DocPDF):
    pdf.title_page(
        "Әкімші және инженер нұсқаулығы",
        "Толық анықтамалық: мүмкіндіктер, орналастыру және пайдалану",
    )

    pdf.add_page()
    pdf.h1("1. Кіріспе")
    pdf.body(
        "IOC Analyzer — Windows үшін threat intelligence және оқиғаларға жауап беру десктоп платформасы. "
        "Ол қауіпсіздік талдаушыларына, әкімшілерге және инженерлерге зиянды бағдарламалардың "
        "артефактілерін анықтауға, YARA ережелерімен файлдарды сканерлеуге, "
        "файл хэштерін VirusTotal арқылы тексеруге және бір жұмыс станциясынан "
        "бірнеше хостты қашықтан сканерлеуге мүмкіндік береді."
    )

    pdf.h2("1.1 Жүйелік талаптар")
    for item in [
        "ОЖ: Windows 10 / 11 (64-bit)",
        "Python 3.11+ (PyQt6, requests, psutil)",
        "API қоңырауларына желіге қол жетімділік (VirusTotal, AbuseIPDB, Groq/Claude)",
        "yara64.exe НЕМЕСЕ yara-python — YARA сканерлеу үшін",
        "pywinrm — агентті автоматты орналастыру үшін (міндетті емес)",
    ]:
        pdf.bullet(item)

    pdf.h2("1.2 Алғашқы іске қосу")
    pdf.body("Қолданбаны жоба түбірінен іске қосыңыз:")
    pdf.code("python main.py")
    pdf.body(
        "Алғашқы іске қосуда config.json автоматты жасалады. "
        "API кілттерін енгізу үшін Параметрлер бөлімін ашыңыз."
    )

    pdf.add_page()
    pdf.h1("2. Мүмкіндіктер анықтамалығы")

    pdf.h2("2.1 Басты бет (Dashboard)")
    pdf.body(
        "Басты бет сканерлеу белсенділігіне шолуды нақты уақытта ұсынады: "
        "YARA ескертулерінің, тексерілген хэштердің, желі сұрауларының есептегіштері "
        "және барлық бөлімдердегі маңызды нәтижелерді тіркейтін оқиғалар тізімі."
    )

    pdf.h2("2.2 Хэш іздеу (Hash Lookup)")
    pdf.body(
        "VirusTotal API-ын сұрастыру үшін бір немесе бірнеше хэш (SHA-256/MD5/SHA-1) енгізіңіз. "
        "Нәтижелер анықтау үлесін, файл атауын, түрін және есепке сілтемені көрсетеді. "
        "Тегін VT API — 4 сұрау/мин; Параметрлерде кідірісті реттеңіз."
    )

    pdf.h2("2.3 IOC жинақ (IOC Collection)")
    pdf.body(
        "Жергілікті хосттан компромисс индикаторларын жинау: іске қосылған процестер, "
        "белсенді желі қосылымдары және реестрдің автожүктеу жазбалары. "
        "Күдікті процестер (C:\\Windows және C:\\Program Files сыртында) автоматты белгіленеді."
    )

    pdf.h2("2.4 YARA сканер (YARA Scanner)")
    pdf.body(
        "YARA ережелерін пайдаланып файл немесе қалтаны сканерлеу. "
        "40-тан астам кірістірілген ережелермен жеткізіледі: "
        "шифрлаушылар, RAT, тіркелгі деректерін ұрлаушылар, C2 фреймворктары. "
        "Өзіндік .yar файлдарын жүктеп немесе кірістірілген редактор арқылы ережелер жазуға болады."
    )
    pdf.bullet("Сол панельден бір немесе бірнеше ережені таңдаңыз.")
    pdf.bullet("Файл немесе Қалта батырмалары арқылы нысанды көрсетіңіз.")
    pdf.bullet("«YARA сканерлеу» батырмасын басыңыз. Нәтижелер кесте арқылы түс белгілерімен көрсетіледі.")
    pdf.note("YARA сканерлеу үшін жоба қалтасында yara64.exe немесе yara-python орнатылған болуы керек.")

    pdf.h2("2.5 Желі барлауы (Network Intel)")
    pdf.body(
        "IP-мекенжайлар мен домендерді AbuseIPDB және VirusTotal арқылы тексеру. "
        "Нәтижелер теріс пайдалану сенімділік ұпайын, елді, провайдерді және қауіп санаттарын қамтиды."
    )

    pdf.h2("2.6 ЖИ Көмекшісі (AI Assistant)")
    pdf.body(
        "Қауіптерді талдауға арналған ЖИ модельмен (Groq / Claude) чат. "
        "IOC деректерін, журнал үзінділерін немесе YARA ережелерінің кодын жіберіп, "
        "түсініктемелер, MITRE ATT&CK маппинг және жою ұсыныстарын алыңыз."
    )

    pdf.h2("2.7 Есептер (Report Builder)")
    pdf.body(
        "PDF немесе HTML форматында оқиға есептерін жасау. "
        "Есептер барлық бөлімдердің нәтижелерін, уақыт белгілерін, "
        "ауырлық деңгейлерін және ұсыныстарды біріктіреді."
    )

    pdf.h2("2.8 Жады сканері (Memory Scan)")
    pdf.body(
        "Барлық іске қосылған процестерді тізімдеу және таңдалған процестің "
        "орындалатын файл кескінін YARA ережелерімен сканерлеу. "
        "Дискідегі файлсыз жадыдағы зиянды бағдарламаларды анықтауға пайдалы."
    )

    pdf.h2("2.9 Карантин (Quarantine)")
    pdf.body(
        "Күдікті файлдарды оқшауланған карантин қалтасына жылжыту. "
        "Карантиндегі файлдар кездейсоқ іске қосуды болдырмау үшін аты өзгертіледі. "
        "Оларды қалпына келтіруге немесе біржола жоюға болады."
    )

    pdf.h2("2.10 Параметрлер (Settings)")
    pdf.body("Қолданбаны конфигурациялау:")
    pdf.bullet("VirusTotal, AbuseIPDB, Groq, Claude API кілттері")
    pdf.bullet("Нәтижелер мен карантин үшін әдепкі қалталар")
    pdf.bullet("VirusTotal сұрау кідірісі")
    pdf.bullet("Есептерді автосақтау")
    pdf.bullet("Интерфейс тілі: ENG / RUS / ҚАЗ")

    pdf.h2("2.11 Хосттар (Hosts) — Көп хостты сканерлеу")
    pdf.body(
        "Хосттар бөлімі бірнеше Windows машиналарын бір жұмыс станциясынан басқаруға және сканерлеуге мүмкіндік береді. "
        "Әр қашықтағы хостта 5555 портында сканерлеу конечных нүктелерін ұсынатын жеңіл Flask HTTPS-агент (agent.exe) жұмыс істейді."
    )
    pdf.bullet("Хост қосу: IP, порт (5555) және API токенін енгізіңіз.")
    pdf.bullet("Ping: агентке қол жетімділікті тексеріңіз.")
    pdf.bullet("Сканерлеу: қашықтағы хостта YARA, IOC және/немесе файл хэшін іске қосыңыз.")
    pdf.bullet("Орнату (Deploy): WinRM арқылы агентті автоматты орнатыңыз.")

    pdf.add_page()
    pdf.h1("3. Агентті орналастыру — кезең-кезеңімен нұсқаулық")

    pdf.h2("3.1 Агент не жасайды")
    pdf.body(
        "agent.py — бақыланатын әр хостта Windows Service ретінде жұмыс істейтін "
        "өз алдына Flask HTTPS сервері. Ол API токенімен қорғалған алты сканерлеу конечных нүктесін ұсынады. "
        "Барлық трафик алғашқы іске қосуда автоматты жасалатын өздігінен қол қойылған TLS сертификатымен шифрланады."
    )

    pdf.h2("3.2 A Әдісі — Қолмен орналастыру")
    pdf.body("Мақсатты хостта WinRM қол жетімді болмаса осы әдісті қолданыңыз.")

    pdf.h3("1-қадам — Мақсатты хостта Python орнату")
    pdf.code("winget install Python.Python.3.12")

    pdf.h3("2-қадам — agent/ қалтасын мақсатты хостқа көшіру")
    pdf.body("agent/ мазмұнын қашықтағы машинаның C:\\IOCAgent\\ қалтасына көшіріңіз.")

    pdf.h3("3-қадам — Мақсатты хостта агент тәуелділіктерін орнату")
    pdf.code("pip install flask psutil cryptography pywin32")

    pdf.h3("4-қадам — Токен жасау үшін агентті алдыңғы режимде іске қосу")
    pdf.code(
        "cd C:\\IOCAgent\n"
        "python agent.py\n"
        "# Шығыс:\n"
        "# [IOCAgent] Generating self-signed certificate...\n"
        "# [IOCAgent] v1.0.0 starting on https://0.0.0.0:5555\n"
        "# [IOCAgent] Token: a3f7c9d2... (32 таңбалы hex)"
    )
    pdf.tip("Токенді көшіріңіз — 7-қадамда қажет болады. C:\\IOCAgent\\token.txt файлына да сақталады.")

    pdf.h3("5-қадам — Windows Service ретінде орнату (ұсынылады)")
    pdf.code(
        "# Әкімші ретінде іске қосыңыз:\n"
        "python agent.py --install\n"
        "python agent.py --start"
    )

    pdf.h3("6-қадам — Windows Firewall-да 5555 портын ашу")
    pdf.code(
        "netsh advfirewall firewall add rule name=\"IOCAgent\" "
        "dir=in action=allow protocol=TCP localport=5555"
    )

    pdf.h3("7-қадам — IOC Analyzer-ге хостты қосу")
    pdf.body("Хосттар бөлімін ашыңыз, «+ Қосу» батырмасын басыңыз және толтырыңыз:")
    pdf.bullet("Атауы: кез келген белгі (мысалы, SRV-DC01)")
    pdf.bullet("IP: мақсатты хосттың IP мекенжайы")
    pdf.bullet("Порт: 5555")
    pdf.bullet("Токен: token.txt мәні")

    pdf.h3("8-қадам — Байланысты тексеру")
    pdf.body("⟳ Ping батырмасын басыңыз. Күй жасыл (● онлайн) болуы тиіс.")

    pdf.h3("9-қадам — Сканерлеуді іске қосу")
    pdf.body(
        "YARA және/немесе IOC жалауларын белгілеңіз, сканерлеу жолын (мысалы, C:\\Users) орнатыңыз "
        "және ▶ Сканерлеу батырмасын басыңыз. Нәтижелер төмендегі кестеде пайда болады."
    )

    pdf.h2("3.3 Б Әдісі — UI арқылы автоматты орналастыру")
    pdf.body(
        "Мақсатты хостта WinRM қосылған болса (5985 порты), агентті IOC Analyzer "
        "интерфейсінен тікелей орналастыруға болады."
    )

    pdf.h3("Мақсатты хосттағы алғышарттар")
    pdf.code(
        "# МАҚСАТТЫ хостта Әкімші ретінде іске қосыңыз:\n"
        "winrm quickconfig\n"
        "# NTLM үшін (домен ортасы):\n"
        "Set-Item WSMan:\\localhost\\Service\\Auth\\NTLM -Value true"
    )
    pdf.note("WinRM Windows жұмыс станцияларында әдепкі өшірулі. Командалар әкімші құқықтарымен орындалады.")

    pdf.h3("agent.exe жинау (жұмыс станциясында бір рет)")
    pdf.code(
        "cd agent\n"
        "build.bat\n"
        "# Жасайды: agent\\dist\\agent.exe"
    )

    pdf.h3("UI-дан орналастыру")
    pdf.bullet("Хосттар бөлімін ашыңыз.")
    pdf.bullet("📦 Агент орнату батырмасын басыңыз.")
    pdf.bullet("Мақсатты хосттың IP, әкімші атын және құпия сөзді енгізіңіз.")
    pdf.bullet("OK басыңыз — IOC Analyzer agent.exe-ді көшіреді, қызметті орнатады және токенді автоматты алады.")
    pdf.bullet("«+ Қосу» батырмасын басып, көрсетілген токенді хостты тіркеу үшін қойыңыз.")

    pdf.add_page()
    pdf.h1("4. Қауіпсіздік ескертпелері")
    pdf.bullet("API токені — орнату кезінде бір рет жасалатын 64 таңбалы кездейсоқ hex жолы.")
    pdf.bullet("Барлық агент трафигі TLS (өздігінен қол қойылған сертификат) арқылы шифрланады.")
    pdf.bullet("Токен token.txt файлында ашық түрде сақталады — ACL арқылы қол жетімділікті шектеңіз.")
    pdf.bullet("WinRM тіркелгі деректері қолданбамен сақталмайды, тек Deploy операциясы кезінде пайдаланылады.")
    pdf.bullet("config.json API кілттерін ашық түрде сақтайды — VCS-қа қоспаңыз.")

    pdf.h1("5. Ақауларды жою")

    pdf.h3("Агент 'офлайн' ретінде көрсетілуде")
    pdf.bullet("Қашықтағы хостта agent.exe / agent.py іске қосылғанын тексеріңіз.")
    pdf.bullet("5555 порты ашық екенін тексеріңіз: netstat -ano | findstr 5555")
    pdf.bullet("hosts.json-дағы токен қашықтағы хосттың token.txt мәніне сәйкес болуы тиіс.")

    pdf.h3("YARA сканерлеу COMPILE_ERR қайтарады")
    pdf.bullet("Ережеде синтаксис қатесі бар — Ережелер редакторын ашыңыз.")
    pdf.bullet("YARA 4.5.5+ пайдаланылмаған жолдарды қате ретінде қабылдайды — барлық айнымалылар condition-да болуы тиіс.")

    pdf.h3("Deploy: 'pywinrm not installed'")
    pdf.code("pip install pywinrm")

    pdf.h3("Deploy: WinRM қосылым қатесі")
    pdf.bullet("WinRM қосылғанын тексеріңіз: winrm quickconfig")
    pdf.bullet("Мақсатты хостта 5985 порты үшін брандмауэр ережелерін тексеріңіз.")


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    docs = [
        ("IOC_Analyzer_Manual_EN.pdf", "English",   build_en),
        ("IOC_Analyzer_Manual_RU.pdf", "Русский",   build_ru),
        ("IOC_Analyzer_Manual_KZ.pdf", "Қазақша",   build_kz),
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
