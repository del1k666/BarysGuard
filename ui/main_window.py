from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel
from PyQt6.QtCore import Qt
from ui.dashboard_tab import DashboardTab
from ui.hash_tab import HashTab
from ui.ioc_tab import IOCTab
from ui.yara_tab import YARATab
from ui.ai_tab import AITab
from ui.report_tab import ReportTab
from ui.net_intel_tab import NetIntelTab
from ui.quarantine_tab import QuarantineTab
from ui.memory_scanner_tab import MemoryScannerTab
from ui.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IOC Analyzer — Threat Intelligence Platform")
        self.setMinimumSize(1000, 700)
        self.resize(1150, 780)

        central = QWidget()
        self.setCentralWidget(central)
        ml = QVBoxLayout(central)
        ml.setSpacing(0); ml.setContentsMargins(0,0,0,0)

        # Header
        hdr = QWidget()
        hdr.setStyleSheet("background:#161b22;border-bottom:1px solid #30363d;")
        hdr.setFixedHeight(64)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20,0,20,0)
        t = QLabel("IOC ANALYZER")
        t.setStyleSheet("font-size:20px;font-weight:bold;color:#58a6ff;letter-spacing:2px;")
        hl.addWidget(t)
        s = QLabel("Threat Intelligence & Incident Response Platform")
        s.setStyleSheet("font-size:10px;color:#8b949e;letter-spacing:1px;")
        s.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hl.addWidget(s)
        ml.addWidget(hdr)

        # Tabs
        tabs = QTabWidget()
        tabs.setContentsMargins(12,12,12,12)
        self.dash_tab = DashboardTab()
        tabs.addTab(self.dash_tab,   "  Dashboard  ")
        tabs.addTab(HashTab(),        "  Hash Lookup  ")
        tabs.addTab(IOCTab(),         "  IOC Collection  ")
        tabs.addTab(YARATab(),        "  YARA Scanner  ")
        tabs.addTab(NetIntelTab(),    "  Network Intel  ")
        tabs.addTab(AITab(),          "  AI Assistant  ")
        tabs.addTab(ReportTab(),      "  Report Builder  ")
        self.mem_tab = MemoryScannerTab()
        tabs.addTab(self.mem_tab,        "  Memory Scan  ")
        self.quarantine_tab = QuarantineTab()
        tabs.addTab(self.quarantine_tab, "  Quarantine  ")
        tabs.addTab(SettingsTab(),       "  Settings  ")
        ml.addWidget(tabs)

        # Footer
        ftr = QWidget()
        ftr.setStyleSheet("background:#161b22;border-top:1px solid #30363d;")
        ftr.setFixedHeight(26)
        fl = QHBoxLayout(ftr); fl.setContentsMargins(14,0,14,0)
        fl.addWidget(QLabel("VirusTotal API  ·  YARA Engine  ·  AbuseIPDB  ·  AI Assistant"))
        fl.addStretch()
        fl.addWidget(QLabel("© 2025 IOC Analyzer"))
        for w in ftr.findChildren(QLabel):
            w.setStyleSheet("color:#484f58;font-size:10px;")
        ml.addWidget(ftr)
