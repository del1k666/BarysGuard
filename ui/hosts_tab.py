import re
import socket
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QListWidget,
    QListWidgetItem, QCheckBox, QSplitter, QLineEdit, QDialog, QFormLayout,
    QDialogButtonBox, QMessageBox, QSpinBox, QTabWidget, QTextEdit,
    QFileDialog, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from core.hosts_config import load_hosts, add_host, remove_host, update_host
from workers.host_worker import (
    PingWorker, RemoteScanWorker, DeployWorker,
    RemoteProcessListWorker, RemoteMemScanWorker,
    NetworkIsolationWorker,
)
from constants import BUILTIN_YARA_RULES
from core.i18n import t
from core.lang_signal import lang_signal
from ui.dashboard_tab import DashboardTab


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


class _AddHostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("hosts_add_dialog_title"))
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        self._name  = QLineEdit(); self._name.setPlaceholderText("WS-FINANCE01")
        self._ip    = QLineEdit(); self._ip.setPlaceholderText("192.168.1.10")
        self._port  = QSpinBox();  self._port.setRange(1, 65535); self._port.setValue(5555)
        self._token = QLineEdit(); self._token.setPlaceholderText("вставьте токен из token.txt")
        layout.addRow(t("hosts_add_name"),  self._name)
        layout.addRow(t("hosts_add_ip"),    self._ip)
        layout.addRow(t("hosts_add_port"),  self._port)
        layout.addRow(t("hosts_add_token"), self._token)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def data(self):
        return {"name": self._name.text().strip(), "ip": self._ip.text().strip(),
                "port": self._port.value(), "token": self._token.text().strip()}


class _DeployDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("hosts_deploy_dialog_title"))
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        self._ip   = QLineEdit(); self._ip.setPlaceholderText("192.168.1.10")
        self._user = QLineEdit(); self._user.setPlaceholderText("DOMAIN\\admin")
        self._pwd  = QLineEdit(); self._pwd.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow(t("hosts_deploy_ip"),   self._ip)
        layout.addRow(t("hosts_deploy_user"), self._user)
        layout.addRow(t("hosts_deploy_pwd"),  self._pwd)
        note = QLabel(t("hosts_deploy_note"))
        note.setStyleSheet("color:#8b949e;font-size:11px;"); note.setWordWrap(True)
        layout.addRow(note)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def data(self):
        return {"ip": self._ip.text().strip(),
                "username": self._user.text().strip(),
                "password": self._pwd.text()}


# ─────────────────────────────────────────────────────────────────────────────

class HostsTab(QWidget):
    _TAB_STATUS   = 0
    _TAB_FILE     = 1
    _TAB_MEMORY   = 2
    _TAB_RESULTS  = 3
    _TAB_ISOLATE  = 4

    def __init__(self, on_host_changed=None, on_hosts_list_changed=None):
        super().__init__()
        self._on_host_changed       = on_host_changed
        self._on_hosts_list_changed = on_hosts_list_changed
        self._selected_id: str | None = None

        self._ping_worker:   PingWorker | None = None
        self._scan_worker:   RemoteScanWorker | None = None
        self._deploy_worker: DeployWorker | None = None
        self._proc_worker:   RemoteProcessListWorker | None = None
        self._mem_worker:    RemoteMemScanWorker | None = None
        self._iso_worker:    NetworkIsolationWorker | None = None

        self._mem_stop_requested: bool = False
        self._file_custom_rules: dict = {}
        self._mem_custom_rules:  dict = {}
        self._remote_procs: list = []

        self._build()
        self._reload_hosts()
        self._start_ping_timer()
        lang_signal.changed.connect(self.retranslate)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(8); lay.setContentsMargins(12, 12, 12, 12)

        outer = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: host list ───────────────────────────────────────────────
        left = QWidget(); ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0); ll.setSpacing(6)

        self._lbl_count = QLabel(t("hosts_count", n=0))
        self._lbl_count.setStyleSheet(
            "color:#6e7681;font-size:11px;font-weight:bold;letter-spacing:0.5px;")
        ll.addWidget(self._lbl_count)

        self._host_list = QListWidget()
        self._host_list.setMinimumWidth(220)
        self._host_list.currentRowChanged.connect(self._on_host_select)
        ll.addWidget(self._host_list, 1)

        row_btns = QHBoxLayout()
        self._btn_add = QPushButton(t("hosts_add_btn"))
        self._btn_add.setObjectName("secondaryBtn")
        self._btn_add.clicked.connect(self._add_host)
        self._btn_remove = QPushButton(t("hosts_remove_btn"))
        self._btn_remove.setObjectName("dangerBtn"); self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._remove_host)
        row_btns.addWidget(self._btn_add); row_btns.addWidget(self._btn_remove)
        ll.addLayout(row_btns)
        outer.addWidget(left)

        # ── RIGHT: content ─────────────────────────────────────────────────
        right = QWidget(); rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(6)

        self._info_label = QLabel(t("hosts_select_hint"))
        self._info_label.setStyleSheet(
            "color:#8b949e;font-size:12px;padding:6px 10px;"
            "background:#161b22;border:1px solid #21262d;border-radius:6px;")
        self._info_label.setWordWrap(True)
        rl.addWidget(self._info_label)

        self._sub_tabs = QTabWidget()
        self._sub_tabs.setEnabled(False)
        self._sub_tabs.setStyleSheet(
            "QTabBar::tab{padding:8px 16px;font-size:12px;}"
            "QTabBar::tab:selected{font-weight:bold;}")
        self._sub_tabs.addTab(self._build_status_tab(),  "📊  Статус")
        self._sub_tabs.addTab(self._build_file_tab(),    "📁  Файловый скан")
        self._sub_tabs.addTab(self._build_memory_tab(),  "🔍  Memory Scan")
        self._sub_tabs.addTab(self._build_results_tab(), "📋  Результаты")
        self._sub_tabs.addTab(self._build_isolate_tab(), "🔒  Изоляция")
        self._sub_tabs.currentChanged.connect(self._on_tab_changed)
        rl.addWidget(self._sub_tabs, 1)

        outer.addWidget(right)
        outer.setSizes([250, 900])
        lay.addWidget(outer)

    # ── Tab 0: Статус ─────────────────────────────────────────────────────────

    def _build_status_tab(self) -> QWidget:
        w   = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(12)

        # Host details card
        card = QFrame()
        card.setStyleSheet(
            "QFrame{background:#161b22;border:1px solid #21262d;border-radius:8px;}")
        cl = QVBoxLayout(card); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(8)

        self._st_name   = QLabel("—")
        self._st_name.setStyleSheet("font-size:18px;font-weight:bold;color:#58a6ff;")
        self._st_addr   = self._detail_row(cl, "Адрес")
        self._st_seen   = self._detail_row(cl, "Последний пинг")
        self._st_scan   = self._detail_row(cl, "Последний скан")
        self._st_status = self._detail_row(cl, "Статус")
        cl.insertWidget(0, self._st_name)
        lay.addWidget(card)

        # Action buttons
        grp_act = QGroupBox("Действия с хостом")
        ga = QHBoxLayout(grp_act); ga.setSpacing(8)
        self._btn_ping = QPushButton("⟳  Пинговать")
        self._btn_ping.setObjectName("secondaryBtn"); self._btn_ping.setFixedHeight(36)
        self._btn_ping.clicked.connect(self._ping_selected)
        self._btn_deploy = QPushButton("⚙  Развернуть агент")
        self._btn_deploy.setObjectName("secondaryBtn"); self._btn_deploy.setFixedHeight(36)
        self._btn_deploy.clicked.connect(self._deploy)
        ga.addWidget(self._btn_ping); ga.addWidget(self._btn_deploy); ga.addStretch()
        lay.addWidget(grp_act)

        # Quick navigation
        grp_nav = QGroupBox("Быстрый переход")
        gn = QHBoxLayout(grp_nav); gn.setSpacing(8)
        btn_go_file = QPushButton("📁  Файловый скан")
        btn_go_file.setObjectName("secondaryBtn"); btn_go_file.setFixedHeight(36)
        btn_go_file.clicked.connect(lambda: self._sub_tabs.setCurrentIndex(self._TAB_FILE))
        btn_go_mem = QPushButton("🔍  Memory Scan")
        btn_go_mem.setObjectName("secondaryBtn"); btn_go_mem.setFixedHeight(36)
        btn_go_mem.clicked.connect(lambda: self._sub_tabs.setCurrentIndex(self._TAB_MEMORY))
        btn_go_iso = QPushButton("🔒  Изоляция сети")
        btn_go_iso.setObjectName("dangerBtn"); btn_go_iso.setFixedHeight(36)
        btn_go_iso.clicked.connect(lambda: self._sub_tabs.setCurrentIndex(self._TAB_ISOLATE))
        gn.addWidget(btn_go_file); gn.addWidget(btn_go_mem); gn.addWidget(btn_go_iso)
        lay.addWidget(grp_nav)

        lay.addStretch()
        return w

    def _detail_row(self, parent_layout, label: str) -> QLabel:
        row = QHBoxLayout()
        lbl = QLabel(label + ":"); lbl.setFixedWidth(130)
        lbl.setStyleSheet("color:#6e7681;font-size:12px;")
        val = QLabel("—"); val.setStyleSheet("color:#e6edf3;font-size:12px;")
        row.addWidget(lbl); row.addWidget(val); row.addStretch()
        parent_layout.addLayout(row)
        return val

    # ── Tab 1: Файловый скан ──────────────────────────────────────────────────

    _INNER_TAB_STYLE = (
        "QTabBar::tab{padding:5px 14px;font-size:11px;}"
        "QTabBar::tab:selected{font-weight:bold;color:#58a6ff;}"
        "QTabBar::tab:!selected{color:#6e7681;}"
        "QTabWidget::pane{border:1px solid #21262d;border-radius:4px;margin-top:2px;}")

    def _build_file_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        inner = QTabWidget()
        inner.setStyleSheet(self._INNER_TAB_STYLE)
        inner.addTab(self._build_file_scan_tab(),  "⚙  Сканирование")
        inner.addTab(self._build_file_rules_tab(), "📝  Свои правила")
        lay.addWidget(inner, 1)
        return w

    def _build_file_scan_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(6)

        grp_rules = QGroupBox("YARA ПРАВИЛА")
        gr = QVBoxLayout(grp_rules); gr.setSpacing(4)

        top_row = QHBoxLayout()
        btn_all  = QPushButton("Все");    btn_all.setObjectName("secondaryBtn");  btn_all.setFixedHeight(24)
        btn_none = QPushButton("Ничего"); btn_none.setObjectName("secondaryBtn"); btn_none.setFixedHeight(24)
        btn_all.clicked.connect(lambda: (
            self._toggle_rules(self._file_rule_list, True),
            self._update_rule_count(self._file_rule_list, self._file_rule_count)))
        btn_none.clicked.connect(lambda: (
            self._toggle_rules(self._file_rule_list, False),
            self._update_rule_count(self._file_rule_list, self._file_rule_count)))
        self._file_rule_count = QLabel("0 / 0 правил")
        self._file_rule_count.setStyleSheet("color:#6e7681;font-size:11px;")
        self._file_rule_filter = QLineEdit()
        self._file_rule_filter.setPlaceholderText("🔍  Поиск...")
        self._file_rule_filter.setFixedHeight(26)
        self._file_rule_filter.textChanged.connect(self._filter_file_rules)
        top_row.addWidget(btn_all); top_row.addWidget(btn_none)
        top_row.addWidget(self._file_rule_filter, 1)
        top_row.addWidget(self._file_rule_count)
        gr.addLayout(top_row)

        self._file_rule_list = QListWidget()
        for name in BUILTIN_YARA_RULES:
            item = QListWidgetItem(name)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._file_rule_list.addItem(item)
        self._file_rule_list.itemChanged.connect(
            lambda: self._update_rule_count(self._file_rule_list, self._file_rule_count))
        self._update_rule_count(self._file_rule_list, self._file_rule_count)
        gr.addWidget(self._file_rule_list)
        lay.addWidget(grp_rules, 1)

        opt_row = QHBoxLayout()
        self._chk_ioc    = QCheckBox("IOC сбор"); self._chk_ioc.setChecked(True)
        self._chk_hashes = QCheckBox(t("hosts_hashes_chk"))
        self._lbl_path   = QLabel("Путь (remote):")
        self._path_inp   = QLineEdit(); self._path_inp.setText(r"C:\Users")
        self._path_inp.setToolTip(
            "Путь к папке на удалённом хосте.\n"
            "Вводите вручную — браузер открывает локальные папки.")
        btn_browse = QPushButton("..."); btn_browse.setObjectName("secondaryBtn")
        btn_browse.setFixedWidth(32)
        btn_browse.setToolTip("Открыть локальный браузер (для справки)")
        btn_browse.clicked.connect(self._browse_path)
        opt_row.addWidget(self._chk_ioc); opt_row.addWidget(self._chk_hashes)
        opt_row.addWidget(self._lbl_path); opt_row.addWidget(self._path_inp)
        opt_row.addWidget(btn_browse)
        lay.addLayout(opt_row)

        self._file_prog = QProgressBar()
        self._file_prog.setRange(0, 0); self._file_prog.setFixedHeight(4)
        self._file_prog.setVisible(False)
        lay.addWidget(self._file_prog)

        self._file_status = QLabel("Выберите правила и нажмите Сканировать")
        self._file_status.setStyleSheet("color:#6e7681;font-size:11px;")
        lay.addWidget(self._file_status)

        self._btn_scan = QPushButton("▶  Сканировать"); self._btn_scan.setFixedHeight(38)
        self._btn_scan.clicked.connect(self._start_file_scan)
        lay.addWidget(self._btn_scan)
        return w

    def _build_file_rules_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(8)

        hdr = QLabel("ПОЛЬЗОВАТЕЛЬСКИЕ YARA ПРАВИЛА")
        hdr.setStyleSheet("color:#6e7681;font-size:11px;font-weight:bold;letter-spacing:0.5px;")
        lay.addWidget(hdr)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: list of added custom rules ─────────────────────────────
        left_w = QWidget(); ll = QVBoxLayout(left_w)
        ll.setContentsMargins(0, 0, 6, 0); ll.setSpacing(4)
        lbl_l = QLabel("Добавленные правила")
        lbl_l.setStyleSheet("color:#8b949e;font-size:11px;")
        ll.addWidget(lbl_l)
        self._file_custom_list = QListWidget()
        self._file_custom_list.setStyleSheet(
            "QListWidget{background:#0a0e14;border:1px solid #21262d;border-radius:4px;}")
        self._file_custom_list.currentRowChanged.connect(
            lambda _: self._load_custom_rule(
                self._file_custom_list, self._file_rule_edit, self._file_custom_rules))
        ll.addWidget(self._file_custom_list, 1)
        btn_del_f = QPushButton("🗑  Удалить правило")
        btn_del_f.setObjectName("dangerBtn"); btn_del_f.setFixedHeight(30)
        btn_del_f.clicked.connect(lambda: self._delete_custom_rule(
            self._file_custom_list, self._file_rule_list,
            self._file_custom_rules, self._file_rule_edit))
        ll.addWidget(btn_del_f)
        splitter.addWidget(left_w)

        # ── Right: code editor ───────────────────────────────────────────
        right_w = QWidget(); rl = QVBoxLayout(right_w)
        rl.setContentsMargins(6, 0, 0, 0); rl.setSpacing(4)
        lbl_r = QLabel("Редактор YARA правила")
        lbl_r.setStyleSheet("color:#8b949e;font-size:11px;")
        rl.addWidget(lbl_r)
        self._file_rule_edit = QTextEdit()
        self._file_rule_edit.setStyleSheet(
            "background:#0a0e14;border:1px solid #21262d;border-radius:4px;"
            "font-family:Consolas,monospace;font-size:12px;color:#c9d1d9;padding:8px;")
        self._file_rule_edit.setPlaceholderText(
            "rule MyRule {\n"
            "    meta:\n"
            "        description = \"My custom rule\"\n"
            "    strings:\n"
            "        $s1 = \"pattern\" ascii nocase\n"
            "    condition:\n"
            "        any of them\n"
            "}")
        rl.addWidget(self._file_rule_edit, 1)

        btn_add_f = QPushButton("➕  Добавить / Обновить правило")
        btn_add_f.setObjectName("secondaryBtn"); btn_add_f.setFixedHeight(34)
        btn_add_f.clicked.connect(lambda: self._add_custom_rule(
            self._file_rule_edit, self._file_rule_list,
            self._file_custom_rules, self._file_custom_list))
        rl.addWidget(btn_add_f)
        splitter.addWidget(right_w)

        splitter.setSizes([200, 520])
        lay.addWidget(splitter, 1)
        return w

    # ── Tab 2: Memory Scan ────────────────────────────────────────────────────

    def _build_memory_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        inner = QTabWidget()
        inner.setStyleSheet(self._INNER_TAB_STYLE)
        inner.addTab(self._build_mem_scan_tab(),  "⚙  Сканирование")
        inner.addTab(self._build_mem_rules_tab(), "📝  Свои правила")
        lay.addWidget(inner, 1)
        return w

    def _build_mem_scan_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(6)

        proc_ctrl = QHBoxLayout()
        self._btn_refresh_procs = QPushButton("⟳  Обновить процессы")
        self._btn_refresh_procs.setObjectName("secondaryBtn"); self._btn_refresh_procs.setFixedHeight(32)
        self._btn_refresh_procs.clicked.connect(self._refresh_remote_procs)
        self._mem_filter = QLineEdit(); self._mem_filter.setPlaceholderText("Фильтр по процессу...")
        self._mem_filter.textChanged.connect(self._filter_remote_procs)
        self._mem_proc_count = QLabel("0 процессов")
        self._mem_proc_count.setStyleSheet("color:#6e7681;font-size:11px;")
        proc_ctrl.addWidget(self._btn_refresh_procs)
        proc_ctrl.addWidget(self._mem_filter, 1)
        proc_ctrl.addWidget(self._mem_proc_count)
        lay.addLayout(proc_ctrl)

        grp_procs = QGroupBox("ПРОЦЕССЫ УДАЛЁННОГО ХОСТА")
        gp = QVBoxLayout(grp_procs); gp.setContentsMargins(8, 6, 8, 6)
        self._mem_proc_tbl = QTableWidget(0, 3)
        self._mem_proc_tbl.setHorizontalHeaderLabels(["PID", "Имя", "Путь к EXE"])
        self._mem_proc_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._mem_proc_tbl.horizontalHeader().resizeSection(0, 55)
        self._mem_proc_tbl.horizontalHeader().resizeSection(1, 150)
        self._mem_proc_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._mem_proc_tbl.setMaximumHeight(130)
        gp.addWidget(self._mem_proc_tbl)
        lay.addWidget(grp_procs)

        grp_rules_m = QGroupBox("YARA ПРАВИЛА ДЛЯ ПАМЯТИ")
        gr_m = QVBoxLayout(grp_rules_m); gr_m.setSpacing(4)
        top_row_m = QHBoxLayout()
        btn_all_m  = QPushButton("Все");    btn_all_m.setObjectName("secondaryBtn");  btn_all_m.setFixedHeight(24)
        btn_none_m = QPushButton("Ничего"); btn_none_m.setObjectName("secondaryBtn"); btn_none_m.setFixedHeight(24)
        btn_all_m.clicked.connect(lambda: (
            self._toggle_rules(self._mem_rule_list, True),
            self._update_rule_count(self._mem_rule_list, self._mem_rule_count)))
        btn_none_m.clicked.connect(lambda: (
            self._toggle_rules(self._mem_rule_list, False),
            self._update_rule_count(self._mem_rule_list, self._mem_rule_count)))
        self._mem_rule_count = QLabel("0 / 0 правил")
        self._mem_rule_count.setStyleSheet("color:#6e7681;font-size:11px;")
        self._mem_rule_filter = QLineEdit()
        self._mem_rule_filter.setPlaceholderText("🔍  Поиск...")
        self._mem_rule_filter.setFixedHeight(26)
        self._mem_rule_filter.textChanged.connect(self._filter_mem_rules)
        top_row_m.addWidget(btn_all_m); top_row_m.addWidget(btn_none_m)
        top_row_m.addWidget(self._mem_rule_filter, 1)
        top_row_m.addWidget(self._mem_rule_count)
        gr_m.addLayout(top_row_m)

        self._mem_rule_list = QListWidget()
        for name in BUILTIN_YARA_RULES:
            item = QListWidgetItem(name)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._mem_rule_list.addItem(item)
        self._mem_rule_list.itemChanged.connect(
            lambda: self._update_rule_count(self._mem_rule_list, self._mem_rule_count))
        self._update_rule_count(self._mem_rule_list, self._mem_rule_count)
        gr_m.addWidget(self._mem_rule_list)
        lay.addWidget(grp_rules_m, 1)

        self._mem_prog = QProgressBar()
        self._mem_prog.setRange(0, 0); self._mem_prog.setFixedHeight(4)
        self._mem_prog.setVisible(False)
        lay.addWidget(self._mem_prog)

        self._mem_status = QLabel("Нажмите «Обновить процессы», выберите правила и «Scan Memory»")
        self._mem_status.setStyleSheet("color:#6e7681;font-size:11px;")
        self._mem_status.setWordWrap(True)
        lay.addWidget(self._mem_status)

        scan_row = QHBoxLayout()
        self._btn_mem_scan = QPushButton("▶  Scan Memory"); self._btn_mem_scan.setFixedHeight(38)
        self._btn_mem_scan.clicked.connect(self._start_mem_scan)
        self._btn_mem_stop = QPushButton("⏹  Стоп"); self._btn_mem_stop.setObjectName("dangerBtn")
        self._btn_mem_stop.setFixedWidth(90); self._btn_mem_stop.setEnabled(False)
        self._btn_mem_stop.clicked.connect(self._stop_mem_scan)
        scan_row.addWidget(self._btn_mem_scan); scan_row.addWidget(self._btn_mem_stop)
        lay.addLayout(scan_row)
        return w

    def _build_mem_rules_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(8)

        hdr = QLabel("ПОЛЬЗОВАТЕЛЬСКИЕ YARA ПРАВИЛА ДЛЯ ПАМЯТИ")
        hdr.setStyleSheet("color:#6e7681;font-size:11px;font-weight:bold;letter-spacing:0.5px;")
        lay.addWidget(hdr)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: list of added custom rules ─────────────────────────────
        left_w = QWidget(); ll = QVBoxLayout(left_w)
        ll.setContentsMargins(0, 0, 6, 0); ll.setSpacing(4)
        lbl_l = QLabel("Добавленные правила")
        lbl_l.setStyleSheet("color:#8b949e;font-size:11px;")
        ll.addWidget(lbl_l)
        self._mem_custom_list = QListWidget()
        self._mem_custom_list.setStyleSheet(
            "QListWidget{background:#0a0e14;border:1px solid #21262d;border-radius:4px;}")
        self._mem_custom_list.currentRowChanged.connect(
            lambda _: self._load_custom_rule(
                self._mem_custom_list, self._mem_rule_edit, self._mem_custom_rules))
        ll.addWidget(self._mem_custom_list, 1)
        btn_del_m = QPushButton("🗑  Удалить правило")
        btn_del_m.setObjectName("dangerBtn"); btn_del_m.setFixedHeight(30)
        btn_del_m.clicked.connect(lambda: self._delete_custom_rule(
            self._mem_custom_list, self._mem_rule_list,
            self._mem_custom_rules, self._mem_rule_edit))
        ll.addWidget(btn_del_m)
        splitter.addWidget(left_w)

        # ── Right: code editor ───────────────────────────────────────────
        right_w = QWidget(); rl = QVBoxLayout(right_w)
        rl.setContentsMargins(6, 0, 0, 0); rl.setSpacing(4)
        lbl_r = QLabel("Редактор YARA правила")
        lbl_r.setStyleSheet("color:#8b949e;font-size:11px;")
        rl.addWidget(lbl_r)
        self._mem_rule_edit = QTextEdit()
        self._mem_rule_edit.setStyleSheet(
            "background:#0a0e14;border:1px solid #21262d;border-radius:4px;"
            "font-family:Consolas,monospace;font-size:12px;color:#c9d1d9;padding:8px;")
        self._mem_rule_edit.setPlaceholderText(
            "rule MyRule {\n"
            "    meta:\n"
            "        description = \"My custom rule\"\n"
            "    strings:\n"
            "        $s1 = \"pattern\" ascii nocase\n"
            "    condition:\n"
            "        any of them\n"
            "}")
        rl.addWidget(self._mem_rule_edit, 1)

        btn_add_m = QPushButton("➕  Добавить / Обновить правило")
        btn_add_m.setObjectName("secondaryBtn"); btn_add_m.setFixedHeight(34)
        btn_add_m.clicked.connect(lambda: self._add_custom_rule(
            self._mem_rule_edit, self._mem_rule_list,
            self._mem_custom_rules, self._mem_custom_list))
        rl.addWidget(btn_add_m)
        splitter.addWidget(right_w)

        splitter.setSizes([200, 520])
        lay.addWidget(splitter, 1)
        return w

    # ── Tab 3: Результаты ─────────────────────────────────────────────────────

    def _build_results_tab(self) -> QWidget:
        w   = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(6)

        # Stats row
        stats_row = QHBoxLayout()
        self._lbl_result_stats = QLabel("Нет данных")
        self._lbl_result_stats.setStyleSheet("color:#6e7681;font-size:11px;")
        btn_clear_tbl = QPushButton("Очистить")
        btn_clear_tbl.setObjectName("secondaryBtn"); btn_clear_tbl.setFixedHeight(24)
        btn_clear_tbl.clicked.connect(self._clear_results)
        stats_row.addWidget(self._lbl_result_stats); stats_row.addStretch()
        stats_row.addWidget(btn_clear_tbl)
        lay.addLayout(stats_row)

        # Vertical splitter: table (top) + log (bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._tbl = QTableWidget(0, 3)
        self._tbl.setHorizontalHeaderLabels(["ТИП / ПРАВИЛО", "SEVERITY", "ФАЙЛ / ПРОЦЕСС"])
        self._tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tbl.horizontalHeader().resizeSection(0, 190)
        self._tbl.horizontalHeader().resizeSection(1, 80)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setStyleSheet("QTableWidget{alternate-background-color:#0f1318;}")
        splitter.addWidget(self._tbl)

        log_w = QWidget(); lw = QVBoxLayout(log_w); lw.setContentsMargins(0, 4, 0, 0)
        log_header = QHBoxLayout()
        lbl_log = QLabel("Лог сканирования")
        lbl_log.setStyleSheet("color:#6e7681;font-size:11px;font-weight:bold;")
        btn_clear_log = QPushButton("Очистить лог")
        btn_clear_log.setObjectName("secondaryBtn"); btn_clear_log.setFixedHeight(22)
        btn_clear_log.clicked.connect(lambda: self._scan_log.clear())
        log_header.addWidget(lbl_log); log_header.addStretch(); log_header.addWidget(btn_clear_log)
        lw.addLayout(log_header)
        self._scan_log = QTextEdit()
        self._scan_log.setReadOnly(True)
        self._scan_log.setStyleSheet(
            "background:#0a0e14;border:1px solid #21262d;border-radius:6px;"
            "font-family:Consolas,monospace;font-size:11px;color:#c9d1d9;padding:6px;")
        lw.addWidget(self._scan_log)
        splitter.addWidget(log_w)

        splitter.setSizes([300, 200])
        lay.addWidget(splitter, 1)
        return w

    # ── Tab 4: Изоляция ───────────────────────────────────────────────────────

    def _build_isolate_tab(self) -> QWidget:
        w   = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(12)

        # Warning banner
        warn = QLabel(
            "⚠  ВНИМАНИЕ: Изоляция заблокирует весь сетевой трафик хоста через Windows Firewall.\n"
            "Убедитесь, что ваш IP-адрес указан ниже — иначе потеряете доступ к агенту.")
        warn.setWordWrap(True)
        warn.setStyleSheet(
            "color:#d29922;font-size:12px;padding:10px 12px;"
            "background:#2d2208;border:1px solid #4d3800;border-radius:6px;")
        lay.addWidget(warn)

        # Status card
        self._iso_status_card = QFrame()
        self._iso_status_card.setStyleSheet(
            "QFrame{background:#161b22;border:1px solid #21262d;border-radius:8px;}")
        sc = QHBoxLayout(self._iso_status_card)
        sc.setContentsMargins(16, 12, 16, 12)
        self._iso_status_icon  = QLabel("●")
        self._iso_status_icon.setStyleSheet("font-size:24px;color:#6e7681;")
        self._iso_status_text  = QLabel("Статус неизвестен")
        self._iso_status_text.setStyleSheet("font-size:14px;font-weight:bold;color:#8b949e;")
        sc.addWidget(self._iso_status_icon); sc.addWidget(self._iso_status_text); sc.addStretch()
        btn_check = QPushButton("⟳ Проверить")
        btn_check.setObjectName("secondaryBtn"); btn_check.setFixedHeight(32)
        btn_check.clicked.connect(self._check_isolation_status)
        sc.addWidget(btn_check)
        lay.addWidget(self._iso_status_card)

        # Management IP
        grp_ip = QGroupBox("Управляющий IP (будет разрешён через firewall)")
        gi = QHBoxLayout(grp_ip)
        self._iso_mgmt_ip = QLineEdit()
        self._iso_mgmt_ip.setPlaceholderText("192.168.1.X — ваш IP-адрес")
        self._iso_mgmt_ip.setText(_local_ip())
        gi.addWidget(self._iso_mgmt_ip)
        lay.addWidget(grp_ip)

        # Action buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self._btn_isolate = QPushButton("🔒  Изолировать хост")
        self._btn_isolate.setObjectName("dangerBtn"); self._btn_isolate.setFixedHeight(42)
        self._btn_isolate.clicked.connect(self._isolate_host)
        self._btn_restore = QPushButton("🔓  Восстановить сеть")
        self._btn_restore.setObjectName("secondaryBtn"); self._btn_restore.setFixedHeight(42)
        self._btn_restore.clicked.connect(self._restore_host)
        btn_row.addWidget(self._btn_isolate); btn_row.addWidget(self._btn_restore)
        lay.addLayout(btn_row)

        # Isolation log
        grp_log = QGroupBox("Журнал изоляции")
        gl = QVBoxLayout(grp_log)
        self._iso_log = QTextEdit()
        self._iso_log.setReadOnly(True)
        self._iso_log.setMaximumHeight(160)
        self._iso_log.setStyleSheet(
            "background:#0a0e14;border:1px solid #21262d;border-radius:6px;"
            "font-family:Consolas,monospace;font-size:11px;color:#c9d1d9;padding:6px;")
        gl.addWidget(self._iso_log)
        lay.addWidget(grp_log)
        lay.addStretch()
        return w

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def _log(self, msg: str, color: str = "#8b949e"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._scan_log.append(
            f'<span style="color:#484f58">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>')

    def _iso_log_append(self, msg: str, color: str = "#8b949e"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._iso_log.append(
            f'<span style="color:#484f58">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>')

    def _clear_results(self):
        self._tbl.setRowCount(0)
        self._scan_log.clear()
        self._lbl_result_stats.setText("Нет данных")

    @staticmethod
    def _toggle_rules(rule_list: QListWidget, checked: bool) -> None:
        rule_list.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(rule_list.count()):
            rule_list.item(i).setCheckState(state)
        rule_list.blockSignals(False)

    @staticmethod
    def _update_rule_count(rule_list: QListWidget, label: QLabel) -> None:
        checked = sum(
            1 for i in range(rule_list.count())
            if rule_list.item(i).checkState() == Qt.CheckState.Checked)
        total = rule_list.count()
        label.setText(f"{checked} / {total} правил")
        label.setStyleSheet(
            f"font-size:11px;color:{'#3fb950' if checked else '#6e7681'};")

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

    def _add_custom_rule(self, text_edit: QTextEdit, rule_list: QListWidget,
                         custom_store: dict,
                         custom_list: "QListWidget | None" = None) -> None:
        text = text_edit.toPlainText().strip()
        if not text:
            return
        m    = re.search(r'rule\s+(\w+)', text)
        name = m.group(1) if m else f"Custom_{len(custom_store) + 1}"
        custom_store[name] = text
        # Update existing item in rule_list (for re-add / update)
        for i in range(rule_list.count()):
            if rule_list.item(i).text() == name:
                if custom_list:
                    self._refresh_custom_list(custom_list, custom_store)
                text_edit.clear()
                return
        item = QListWidgetItem(name)
        item.setCheckState(Qt.CheckState.Checked)
        item.setForeground(QColor("#58a6ff"))
        rule_list.addItem(item)
        if custom_list:
            self._refresh_custom_list(custom_list, custom_store)
        text_edit.clear()

    def _refresh_custom_list(self, custom_list: QListWidget,
                              custom_store: dict) -> None:
        custom_list.blockSignals(True)
        custom_list.clear()
        for name in custom_store:
            item = QListWidgetItem(name)
            item.setForeground(QColor("#58a6ff"))
            custom_list.addItem(item)
        custom_list.blockSignals(False)

    def _load_custom_rule(self, custom_list: QListWidget,
                          editor: QTextEdit, custom_store: dict) -> None:
        item = custom_list.currentItem()
        if not item:
            return
        text = custom_store.get(item.text(), "")
        if text:
            editor.blockSignals(True)
            editor.setPlainText(text)
            editor.blockSignals(False)

    def _delete_custom_rule(self, custom_list: QListWidget,
                            rule_list: QListWidget,
                            custom_store: dict, editor: QTextEdit) -> None:
        item = custom_list.currentItem()
        if not item:
            return
        name = item.text()
        custom_store.pop(name, None)
        for i in range(rule_list.count()):
            if rule_list.item(i).text() == name:
                rule_list.takeItem(i)
                break
        custom_list.takeItem(custom_list.currentRow())
        editor.clear()

    def _filter_file_rules(self, text: str) -> None:
        lo = text.lower()
        for i in range(self._file_rule_list.count()):
            item = self._file_rule_list.item(i)
            item.setHidden(bool(lo) and lo not in item.text().lower())

    def _filter_mem_rules(self, text: str) -> None:
        lo = text.lower()
        for i in range(self._mem_rule_list.count()):
            item = self._mem_rule_list.item(i)
            item.setHidden(bool(lo) and lo not in item.text().lower())

    def _browse_path(self):
        d = QFileDialog.getExistingDirectory(self, "Выберите директорию")
        if d:
            self._path_inp.setText(d)

    def retranslate(self, _lang: str = ""):
        self._btn_add.setText(t("hosts_add_btn"))
        self._btn_remove.setText(t("hosts_remove_btn"))
        self._chk_hashes.setText(t("hosts_hashes_chk"))
        self._lbl_path.setText("Путь (remote):")
        self._tbl.setHorizontalHeaderLabels(["ТИП / ПРАВИЛО", "SEVERITY", "ФАЙЛ / ПРОЦЕСС"])
        if self._info_label.text() in (t("hosts_select_hint"),
                                        "Выбери хост слева", "Select a host on the left",
                                        "Сол жақтан хостты таңдаңыз"):
            self._info_label.setText(t("hosts_select_hint"))
        self._reload_hosts()

    # ── Host list ──────────────────────────────────────────────────────────────

    def _reload_hosts(self):
        self._host_list.clear()
        hosts = load_hosts()
        self._lbl_count.setText(t("hosts_count", n=len(hosts)))
        for h in hosts:
            item = QListWidgetItem(f"🖥  {h['name']}\n{h['ip']}:{h['port']}")
            item.setData(Qt.ItemDataRole.UserRole, h)
            self._host_list.addItem(item)

    def _on_host_select(self, row: int):
        self._mem_proc_tbl.setRowCount(0)
        self._remote_procs = []
        self._mem_proc_count.setText("0 процессов")
        self._clear_results()

        if row < 0:
            self._selected_id = None
            self._btn_remove.setEnabled(False)
            self._sub_tabs.setEnabled(False)
            self._info_label.setText(t("hosts_select_hint"))
            return

        host = self._host_list.item(row).data(Qt.ItemDataRole.UserRole)
        self._selected_id = host["id"]
        self._btn_remove.setEnabled(True)
        self._sub_tabs.setEnabled(True)

        seen = host.get("last_seen") or "никогда"
        scan = host.get("last_scan") or "никогда"
        self._info_label.setText(
            f"<b style='color:#58a6ff'>{host['name']}</b>"
            f"  ·  <span style='color:#8b949e'>{host['ip']}:{host['port']}</span>"
            f"  ·  ping: {seen}  ·  скан: {scan}")
        self._update_status_tab(host)
        if self._on_host_changed:
            self._on_host_changed(host)

    def _update_status_tab(self, host: dict):
        self._st_name.setText(host.get("name", "—"))
        self._st_addr.setText(f"{host.get('ip','—')}:{host.get('port','—')}")
        self._st_seen.setText(host.get("last_seen") or "никогда")
        self._st_scan.setText(host.get("last_scan") or "никогда")
        self._st_status.setText("⟳ Статус неизвестен")

    def _on_tab_changed(self, idx: int):
        if idx == self._TAB_ISOLATE:
            self._check_isolation_status()

    def _add_host(self):
        dlg = _AddHostDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["name"]:
            QMessageBox.warning(self, t("error"), t("hosts_add_error")); return
        add_host(d["name"], d["ip"], d["port"], d["token"])
        self._reload_hosts()
        if self._on_hosts_list_changed:
            self._on_hosts_list_changed()

    def _remove_host(self):
        if not self._selected_id:
            return
        if QMessageBox.question(
            self, t("hosts_remove_confirm_title"), t("hosts_remove_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        remove_host(self._selected_id)
        self._selected_id = None
        if self._on_host_changed:
            self._on_host_changed(None)
        self._reload_hosts()
        if self._on_hosts_list_changed:
            self._on_hosts_list_changed()

    # ── Ping ──────────────────────────────────────────────────────────────────

    def _start_ping_timer(self):
        self._ping_timer = QTimer(self)
        self._ping_timer.timeout.connect(self._ping_all)
        self._ping_timer.start(30_000)

    def _ping_all(self):
        hosts = load_hosts()
        if not hosts or (self._ping_worker and self._ping_worker.isRunning()):
            return
        self._ping_worker = PingWorker(hosts)
        self._ping_worker.result.connect(self._on_ping_result)
        self._ping_worker.start()

    def _ping_selected(self):
        if not self._selected_id or (self._ping_worker and self._ping_worker.isRunning()):
            return
        hosts = [h for h in load_hosts() if h["id"] == self._selected_id]
        if not hosts:
            return
        self._st_status.setText("⟳ Пинг...")
        self._ping_worker = PingWorker(hosts)
        self._ping_worker.result.connect(self._on_ping_result)
        self._ping_worker.start()

    def _on_ping_result(self, host_id: str, online: bool, info: dict):
        ts = datetime.now().strftime("%H:%M:%S")
        if online:
            update_host(host_id, last_seen=ts)
        for i in range(self._host_list.count()):
            item = self._host_list.item(i)
            h    = item.data(Qt.ItemDataRole.UserRole)
            if h["id"] != host_id:
                continue
            if online:
                h["last_seen"] = ts
            item.setData(Qt.ItemDataRole.UserRole, h)
            item.setForeground(QColor("#3fb950") if online else QColor("#f85149"))
            item.setText(
                f"🖥  {h['name']}\n{h['ip']}:{h['port']}  "
                f"{'● online' if online else '● offline'}")
            if h["id"] == self._selected_id:
                ping_str = ts if online else "✗ offline"
                self._st_seen.setText(ping_str)
                self._st_status.setText(
                    f"<span style='color:#3fb950'>● Online</span>" if online
                    else "<span style='color:#f85149'>✗ Offline</span>")
                scan = h.get("last_scan") or "никогда"
                self._info_label.setText(
                    f"<b style='color:#58a6ff'>{h['name']}</b>"
                    f"  ·  <span style='color:#8b949e'>{h['ip']}:{h['port']}</span>"
                    f"  ·  ping: {ping_str}  ·  скан: {scan}")
            break

    def _get_selected_host(self) -> dict | None:
        for i in range(self._host_list.count()):
            h = self._host_list.item(i).data(Qt.ItemDataRole.UserRole)
            if h["id"] == self._selected_id:
                return h
        return None

    # ── File scan ─────────────────────────────────────────────────────────────

    def _start_file_scan(self):
        host = self._get_selected_host()
        if not host:
            return
        if self._scan_worker and self._scan_worker.isRunning():
            self._file_status.setText("⚠ Сканирование уже выполняется"); return

        rules = self._get_selected_rules(self._file_rule_list, self._file_custom_rules)
        scan_types = []
        if rules:               scan_types.append("yara")
        if self._chk_ioc.isChecked():    scan_types.append("ioc")
        if self._chk_hashes.isChecked(): scan_types.append("hashes")
        if not scan_types:
            self._file_status.setText("⚠ Выберите хотя бы одно правило YARA, IOC или Хэши")
            self._log("Сканирование не запущено: не выбраны типы проверок", "#d29922")
            return
        path = self._path_inp.text().strip()
        if not path:
            self._file_status.setText("⚠ Укажите путь"); return

        host_label = f"{host['name']} ({host['ip']})"
        self._log(
            f"▶ Файловый скан на <b>{host_label}</b>  "
            f"| YARA: {len(rules)}  | Путь: {path}", "#58a6ff")
        if rules:
            self._log(f"  Правила: {', '.join(list(rules.keys())[:8])}"
                      f"{'...' if len(rules) > 8 else ''}", "#6e7681")

        self._btn_scan.setEnabled(False)
        self._file_prog.setVisible(True)
        self._tbl.setRowCount(0)
        self._lbl_result_stats.setText("Сканирование...")
        self._file_status.setText(f"Подключение к {host['ip']}...")
        self._sub_tabs.setTabText(self._TAB_RESULTS, "📋  Результаты (сканирование...)")

        self._scan_worker = RemoteScanWorker(host, scan_types, path, rules)
        self._scan_worker.progress.connect(self._on_file_progress)
        self._scan_worker.done.connect(lambda r: self._on_results_done(r, host))
        self._scan_worker.error.connect(self._on_file_error)
        self._scan_worker.finished.connect(self._on_file_finished)
        self._scan_worker.start()

    def _on_file_progress(self, msg: str):
        self._file_status.setText(msg)
        self._log(f"  {msg}", "#6e7681")

    def _on_file_error(self, msg: str):
        self._file_status.setText(f"✘ {msg[:120]}")
        self._log(f"✘ Ошибка: {msg}", "#f85149")
        self._sub_tabs.setCurrentIndex(self._TAB_RESULTS)

    def _on_file_finished(self):
        self._btn_scan.setEnabled(True)
        self._file_prog.setVisible(False)
        self._sub_tabs.setTabText(self._TAB_RESULTS, "📋  Результаты")

    # ── Memory scan ───────────────────────────────────────────────────────────

    def _refresh_remote_procs(self):
        host = self._get_selected_host()
        if not host or (self._proc_worker and self._proc_worker.isRunning()):
            return
        self._btn_refresh_procs.setEnabled(False)
        self._mem_status.setText("Загрузка процессов...")
        self._log(f"⟳ Получение процессов с {host['name']}", "#58a6ff")
        self._proc_worker = RemoteProcessListWorker(host)
        self._proc_worker.done.connect(self._on_procs_loaded)
        self._proc_worker.error.connect(lambda e: (
            self._mem_status.setText(f"✘ {e}"),
            self._log(f"✘ Ошибка процессов: {e}", "#f85149")))
        self._proc_worker.finished.connect(lambda: self._btn_refresh_procs.setEnabled(True))
        self._proc_worker.start()

    def _on_procs_loaded(self, procs: list):
        self._remote_procs = procs
        self._render_remote_procs(procs)
        msg = f"Загружено {len(procs)} процессов"
        self._mem_status.setText(msg)
        self._log(f"✓ {msg}", "#3fb950")

    def _render_remote_procs(self, procs: list):
        self._mem_proc_tbl.setRowCount(0)
        for p in procs:
            row = self._mem_proc_tbl.rowCount()
            self._mem_proc_tbl.insertRow(row)
            for col, txt in enumerate([str(p.get("pid","")), p.get("name",""), p.get("exe","")]):
                item = QTableWidgetItem(txt); item.setFont(QFont("Consolas", 10))
                self._mem_proc_tbl.setItem(row, col, item)
        self._mem_proc_count.setText(f"{len(procs)} процессов")

    def _filter_remote_procs(self, text: str):
        lo = text.lower()
        self._render_remote_procs(
            [p for p in self._remote_procs if not lo or lo in p.get("name","").lower()])

    def _start_mem_scan(self):
        host = self._get_selected_host()
        if not host:
            return
        if self._mem_worker and self._mem_worker.isRunning():
            self._mem_status.setText("⚠ Уже выполняется"); return
        rules = self._get_selected_rules(self._mem_rule_list, self._mem_custom_rules)
        if not rules:
            self._mem_status.setText("⚠ Выберите хотя бы одно YARA правило"); return

        host_label = f"{host['name']} ({host['ip']})"
        self._mem_stop_requested = False
        self._log(f"▶ Memory Scan на <b>{host_label}</b>  | правил: {len(rules)}", "#a371f7")

        self._btn_mem_scan.setEnabled(False); self._btn_mem_stop.setEnabled(True)
        self._mem_prog.setVisible(True)
        self._tbl.setRowCount(0); self._lbl_result_stats.setText("Memory Scan...")
        self._mem_status.setText(f"Сканирование памяти на {host['ip']}...")
        self._sub_tabs.setTabText(self._TAB_RESULTS, "📋  Результаты (сканирование...)")

        self._mem_worker = RemoteMemScanWorker(host, rules)
        self._mem_worker.progress.connect(lambda m: (
            self._mem_status.setText(m), self._log(f"  {m}", "#6e7681")))
        self._mem_worker.done.connect(
            lambda r: None if self._mem_stop_requested else self._on_results_done(r, host))
        self._mem_worker.error.connect(lambda m: (
            self._mem_status.setText(f"✘ {m}"),
            self._log(f"✘ Memory Scan ошибка: {m}", "#f85149")))
        self._mem_worker.finished.connect(self._on_mem_finished)
        self._mem_worker.start()

    def _on_mem_finished(self):
        self._btn_mem_scan.setEnabled(True); self._btn_mem_stop.setEnabled(False)
        self._mem_prog.setVisible(False)
        self._sub_tabs.setTabText(self._TAB_RESULTS, "📋  Результаты")

    def _stop_mem_scan(self):
        self._mem_stop_requested = True
        if self._mem_worker:
            self._mem_worker.stop()
        self._btn_mem_stop.setEnabled(False)
        self._mem_status.setText("Остановлено")
        self._log("⏹ Memory Scan остановлен", "#d29922")

    # ── Shared results handler ────────────────────────────────────────────────

    def _on_results_done(self, results: list, host: dict):
        try:
            ts         = datetime.now().strftime("%H:%M:%S")
            host_label = f"{host['name']} ({host['ip']})"

            update_host(host["id"], last_scan=ts)
            for i in range(self._host_list.count()):
                item = self._host_list.item(i)
                h    = item.data(Qt.ItemDataRole.UserRole)
                if h.get("id") == host.get("id"):
                    h["last_scan"] = ts
                    item.setData(Qt.ItemDataRole.UserRole, h)
                    if h["id"] == self._selected_id:
                        self._st_scan.setText(ts)
                    break

            colors     = {"YARA":"#58a6ff","IOC":"#d29922","HASH":"#8b949e","MEMORY":"#a371f7"}
            sev_colors = {"critical":"#f85149","high":"#d29922","medium":"#58a6ff","low":"#3fb950"}

            self._tbl.setRowCount(len(results))
            real_hits = 0
            for i, r in enumerate(results):
                typ  = r.get("type","?"); rule = r.get("rule","?")
                proc = r.get("process_name","")
                fil  = f"[{proc}] {r.get('file','?')}" if proc else r.get("file","?")
                sev  = r.get("severity","")
                col  = sev_colors.get(sev.lower(),"") or colors.get(typ,"#8b949e")
                ri   = QTableWidgetItem(f"[{typ}]  {rule}")
                si   = QTableWidgetItem(sev.upper() if sev else typ)
                fi   = QTableWidgetItem(fil)
                ri.setForeground(QColor(col)); si.setForeground(QColor(col))
                for it in (ri, si, fi):
                    it.setFont(QFont("Consolas", 11))
                self._tbl.setItem(i, 0, ri); self._tbl.setItem(i, 1, si); self._tbl.setItem(i, 2, fi)
                DashboardTab.log_event(typ, f"{rule} — {fil}",
                    level="high" if sev.lower() in ("critical","high") else "info",
                    severity=sev.capitalize() if sev else typ,
                    scan=True, target=fil[:60], host=host_label)
                if rule not in ("ERROR","TIMEOUT","WARN","INFO","COMPILE_ERR","DEBUG"):
                    real_hits += 1

            yara_hits = sum(1 for r in results
                if r.get("type") in ("YARA","MEMORY")
                and r.get("rule","") not in ("ERROR","TIMEOUT","WARN","INFO","COMPILE_ERR"))
            sus_procs = sum(1 for r in results
                if r.get("type") == "IOC" and r.get("rule") == "Подозрит. процесс")
            DashboardTab.stats["yara_hits"]        += yara_hits
            DashboardTab.stats["suspicious_procs"] += sus_procs

            if real_hits:
                msg_color = "#d29922"
                msg = f"✓ Найдено: {real_hits} совпадений (всего: {len(results)})"
            elif results:
                msg_color = "#8b949e"
                msg = f"✓ Завершено — чисто ({len(results)} записей)"
            else:
                msg_color = "#3fb950"
                msg = "✓ Завершено — угрозы не обнаружены"

            self._file_status.setText(msg)
            self._mem_status.setText(msg)
            self._lbl_result_stats.setText(
                f"{real_hits} совпадений · {len(results)} записей · {host_label}")
            self._log(msg, msg_color)
            self._sub_tabs.setCurrentIndex(self._TAB_RESULTS)

        except Exception as e:
            self._log(f"✘ Ошибка обработки результатов: {e}", "#f85149")

    # ── Deploy ────────────────────────────────────────────────────────────────

    def _deploy(self):
        dlg = _DeployDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["username"]:
            QMessageBox.warning(self, t("error"), t("hosts_deploy_required")); return
        if self._deploy_worker and self._deploy_worker.isRunning():
            return
        self._btn_deploy.setEnabled(False)
        self._log(f"⚙ Деплой агента на {d['ip']}...", "#58a6ff")
        self._deploy_worker = DeployWorker(d["ip"], d["username"], d["password"])
        self._deploy_worker.progress.connect(lambda m: self._log(f"  {m}", "#6e7681"))
        self._deploy_worker.error.connect(self._on_deploy_error)
        self._deploy_worker.done.connect(lambda tok: self._on_deploy_done(d["ip"], tok))
        self._deploy_worker.finished.connect(lambda: self._btn_deploy.setEnabled(True))
        self._deploy_worker.start()

    def _on_deploy_done(self, ip: str, token: str):
        self._log(f"✓ Агент задеплоен на {ip}. Токен: {token[:16]}...", "#3fb950")
        QMessageBox.information(self, t("hosts_deploy_done_title"),
            t("hosts_deploy_done_msg", ip=ip, tok=token))

    def _on_deploy_error(self, msg: str):
        self._log(f"✘ Deploy ошибка: {msg}", "#f85149")
        QMessageBox.warning(self, t("hosts_deploy_error_title"), msg)

    # ── Network Isolation ─────────────────────────────────────────────────────

    def _check_isolation_status(self):
        host = self._get_selected_host()
        if not host:
            return
        self._iso_status_text.setText("⟳ Проверка...")
        self._iso_status_icon.setStyleSheet("font-size:24px;color:#6e7681;")
        self._iso_worker = NetworkIsolationWorker(host, "status")
        self._iso_worker.done.connect(self._on_iso_status)
        self._iso_worker.error.connect(lambda e: (
            self._iso_status_text.setText(f"✘ Ошибка: {e[:60]}"),
            self._iso_log_append(f"✘ Ошибка проверки: {e}", "#f85149")))
        self._iso_worker.start()

    def _on_iso_status(self, data: dict):
        isolated = data.get("isolated", False)
        if isolated:
            self._iso_status_icon.setStyleSheet("font-size:24px;color:#f85149;")
            self._iso_status_text.setText(
                "<span style='color:#f85149;font-weight:bold'>🔴  ИЗОЛИРОВАН</span>")
            self._iso_status_card.setStyleSheet(
                "QFrame{background:#2d0f0f;border:1px solid #6e1212;border-radius:8px;}")
        else:
            self._iso_status_icon.setStyleSheet("font-size:24px;color:#3fb950;")
            self._iso_status_text.setText(
                "<span style='color:#3fb950;font-weight:bold'>🟢  Подключён к сети</span>")
            self._iso_status_card.setStyleSheet(
                "QFrame{background:#0f2d14;border:1px solid #1a6e2c;border-radius:8px;}")

    def _isolate_host(self):
        host = self._get_selected_host()
        if not host:
            return
        mgmt_ip = self._iso_mgmt_ip.text().strip()
        if not mgmt_ip:
            QMessageBox.warning(self, "Изоляция",
                "Укажите управляющий IP-адрес, иначе потеряете доступ к агенту."); return
        if QMessageBox.question(
            self, "Подтверждение изоляции",
            f"Изолировать хост <b>{host['name']}</b> ({host['ip']}) от сети?\n\n"
            f"Разрешённый IP: {mgmt_ip}\n\n"
            "Весь остальной трафик будет заблокирован через Windows Firewall.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        self._btn_isolate.setEnabled(False)
        self._iso_status_text.setText("⟳ Применение правил firewall...")
        self._iso_log_append(
            f"▶ Изоляция {host['name']} ({host['ip']}) | mgmt: {mgmt_ip}", "#d29922")
        DashboardTab.log_event("ISOLATE", f"Изоляция {host['name']} ({host['ip']})",
            level="critical", severity="Critical", host=f"{host['name']} ({host['ip']})")

        self._iso_worker = NetworkIsolationWorker(host, "isolate", mgmt_ip)
        self._iso_worker.done.connect(self._on_isolate_done)
        self._iso_worker.error.connect(lambda e: (
            self._iso_log_append(f"✘ Ошибка изоляции: {e}", "#f85149"),
            self._btn_isolate.setEnabled(True)))
        self._iso_worker.start()

    def _on_isolate_done(self, data: dict):
        self._btn_isolate.setEnabled(True)
        if data.get("status") == "isolated":
            self._iso_log_append("✓ Хост изолирован от сети", "#d29922")
            self._on_iso_status({"isolated": True})
        else:
            errs = "; ".join(data.get("errors", [str(data)]))
            self._iso_log_append(f"✘ Ошибка: {errs}", "#f85149")

    def _restore_host(self):
        host = self._get_selected_host()
        if not host:
            return
        self._btn_restore.setEnabled(False)
        self._iso_log_append(
            f"▶ Восстановление сети {host['name']} ({host['ip']})", "#58a6ff")
        DashboardTab.log_event("RESTORE", f"Восстановление сети {host['name']}",
            level="info", host=f"{host['name']} ({host['ip']})")

        self._iso_worker = NetworkIsolationWorker(host, "restore")
        self._iso_worker.done.connect(self._on_restore_done)
        self._iso_worker.error.connect(lambda e: (
            self._iso_log_append(f"✘ Ошибка: {e}", "#f85149"),
            self._btn_restore.setEnabled(True)))
        self._iso_worker.start()

    def _on_restore_done(self, data: dict):
        self._btn_restore.setEnabled(True)
        if data.get("status") == "restored":
            self._iso_log_append("✓ Сеть восстановлена", "#3fb950")
            self._on_iso_status({"isolated": False})
        else:
            self._iso_log_append(f"✘ Ошибка: {data}", "#f85149")
