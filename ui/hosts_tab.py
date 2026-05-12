import re
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
)
from constants import BUILTIN_YARA_RULES
from core.i18n import t
from core.lang_signal import lang_signal
from ui.dashboard_tab import DashboardTab
from datetime import datetime


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
        note.setStyleSheet("color:#8b949e;font-size:11px;")
        note.setWordWrap(True)
        layout.addRow(note)
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


class HostsTab(QWidget):
    def __init__(self, on_host_changed=None, on_hosts_list_changed=None):
        super().__init__()
        self._on_host_changed       = on_host_changed
        self._on_hosts_list_changed = on_hosts_list_changed
        self._selected_id: str | None = None
        self._ping_worker:  PingWorker | None = None
        self._scan_worker:  RemoteScanWorker | None = None
        self._deploy_worker: DeployWorker | None = None
        self._proc_worker:  RemoteProcessListWorker | None = None
        self._mem_worker:   RemoteMemScanWorker | None = None
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
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.setContentsMargins(12, 12, 12, 12)

        outer = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: host list ───────────────────────────────────────────────
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)

        self._lbl_count = QLabel(t("hosts_count", n=0))
        self._lbl_count.setStyleSheet("color:#6e7681;font-size:11px;font-weight:bold;letter-spacing:0.5px;")
        ll.addWidget(self._lbl_count)

        self._host_list = QListWidget()
        self._host_list.setMinimumWidth(220)
        self._host_list.currentRowChanged.connect(self._on_host_select)
        ll.addWidget(self._host_list, 1)

        row_btns = QHBoxLayout()
        self._btn_add = QPushButton("+ " + t("hosts_add_btn"))
        self._btn_add.setObjectName("secondaryBtn")
        self._btn_add.clicked.connect(self._add_host)
        self._btn_remove = QPushButton(t("hosts_remove_btn"))
        self._btn_remove.setObjectName("dangerBtn")
        self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._remove_host)
        row_btns.addWidget(self._btn_add)
        row_btns.addWidget(self._btn_remove)
        ll.addLayout(row_btns)

        outer.addWidget(left)

        # ── RIGHT: content ─────────────────────────────────────────────────
        right = QWidget()
        rl    = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)

        # Info bar
        self._info_label = QLabel(t("hosts_select_hint"))
        self._info_label.setStyleSheet(
            "color:#8b949e;font-size:12px;padding:6px 10px;"
            "background:#161b22;border:1px solid #21262d;border-radius:6px;"
        )
        self._info_label.setWordWrap(True)
        rl.addWidget(self._info_label)

        # Action buttons
        act_row = QHBoxLayout()
        self._btn_deploy = QPushButton("⚙ " + t("hosts_deploy_btn"))
        self._btn_deploy.setObjectName("secondaryBtn")
        self._btn_deploy.setEnabled(False)
        self._btn_deploy.clicked.connect(self._deploy)
        self._btn_ping = QPushButton("⟳ " + t("hosts_ping_btn"))
        self._btn_ping.setObjectName("secondaryBtn")
        self._btn_ping.setEnabled(False)
        self._btn_ping.clicked.connect(self._ping_selected)
        act_row.addWidget(self._btn_deploy)
        act_row.addWidget(self._btn_ping)
        act_row.addStretch()
        rl.addLayout(act_row)

        # Inner splitter: config | results+log
        inner = QSplitter(Qt.Orientation.Horizontal)

        # Config sub-tabs
        self._sub_tabs = QTabWidget()
        self._sub_tabs.setEnabled(False)
        self._sub_tabs.addTab(self._build_file_tab(),   "📁  Файловый скан")
        self._sub_tabs.addTab(self._build_memory_tab(), "🔍  Memory Scan")
        inner.addWidget(self._sub_tabs)

        # Results + Log sub-tabs
        self._result_tabs = QTabWidget()
        self._result_tabs.addTab(self._build_results_panel(), "📋  Результаты")
        self._result_tabs.addTab(self._build_log_panel(),     "📝  Лог сканирования")
        inner.addWidget(self._result_tabs)

        inner.setSizes([420, 560])
        rl.addWidget(inner, 1)

        outer.addWidget(right)
        outer.setSizes([250, 880])
        lay.addWidget(outer)

    # ── File Scan tab ──────────────────────────────────────────────────────

    def _build_file_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        # Rules
        grp_rules = QGroupBox("YARA ПРАВИЛА")
        gr = QVBoxLayout(grp_rules)
        gr.setSpacing(4)

        top_row = QHBoxLayout()
        btn_all_f  = QPushButton("Все");    btn_all_f.setObjectName("secondaryBtn");  btn_all_f.setFixedHeight(24)
        btn_none_f = QPushButton("Ничего"); btn_none_f.setObjectName("secondaryBtn"); btn_none_f.setFixedHeight(24)
        btn_all_f.clicked.connect(lambda: (
            self._toggle_rules(self._file_rule_list, True),
            self._update_rule_count(self._file_rule_list, self._file_rule_count)
        ))
        btn_none_f.clicked.connect(lambda: (
            self._toggle_rules(self._file_rule_list, False),
            self._update_rule_count(self._file_rule_list, self._file_rule_count)
        ))
        self._file_rule_count = QLabel("0 / 0 правил")
        self._file_rule_count.setStyleSheet("color:#6e7681;font-size:11px;")
        top_row.addWidget(btn_all_f); top_row.addWidget(btn_none_f)
        top_row.addStretch(); top_row.addWidget(self._file_rule_count)
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
        lay.addWidget(grp_rules, 3)  # stretch fills space

        # Custom rule
        grp_custom = QGroupBox("СВОЁ ПРАВИЛО")
        gc = QHBoxLayout(grp_custom)
        gc.setContentsMargins(8, 8, 8, 8)
        self._file_rule_edit = QTextEdit()
        self._file_rule_edit.setMaximumHeight(60)
        self._file_rule_edit.setPlaceholderText('rule MyRule { strings: $s = "evil" condition: $s }')
        btn_add_f = QPushButton("➕ Добавить")
        btn_add_f.setObjectName("secondaryBtn")
        btn_add_f.setFixedWidth(100); btn_add_f.setFixedHeight(60)
        btn_add_f.clicked.connect(lambda: self._add_custom_rule(
            self._file_rule_edit, self._file_rule_list, self._file_custom_rules))
        gc.addWidget(self._file_rule_edit); gc.addWidget(btn_add_f)
        lay.addWidget(grp_custom)

        # Options
        opt_row = QHBoxLayout()
        self._chk_ioc    = QCheckBox("IOC сбор");   self._chk_ioc.setChecked(True)
        self._chk_hashes = QCheckBox(t("hosts_hashes_chk"))
        self._lbl_path   = QLabel("Путь (remote):")
        self._path_inp   = QLineEdit(); self._path_inp.setText(r"C:\Users")
        self._path_inp.setToolTip(
            "Путь к папке на удалённом хосте.\n"
            "Вводите вручную — браузер открывает локальные папки,\n"
            "а сканирование выполняется на удалённой машине."
        )
        btn_browse = QPushButton("...")
        btn_browse.setObjectName("secondaryBtn")
        btn_browse.setFixedWidth(32)
        btn_browse.setToolTip("Открыть локальный браузер папок (для справки)")
        btn_browse.clicked.connect(self._browse_path)
        opt_row.addWidget(self._chk_ioc)
        opt_row.addWidget(self._chk_hashes)
        opt_row.addWidget(self._lbl_path)
        opt_row.addWidget(self._path_inp)
        opt_row.addWidget(btn_browse)
        lay.addLayout(opt_row)

        # Progress + status + scan button
        self._file_prog = QProgressBar()
        self._file_prog.setRange(0, 0); self._file_prog.setFixedHeight(4)
        self._file_prog.setVisible(False)
        lay.addWidget(self._file_prog)

        self._file_status = QLabel("Выберите правила и нажмите Сканировать")
        self._file_status.setStyleSheet("color:#6e7681;font-size:11px;")
        lay.addWidget(self._file_status)

        self._btn_scan = QPushButton("▶  Сканировать")
        self._btn_scan.setFixedHeight(38)
        self._btn_scan.clicked.connect(self._start_file_scan)
        lay.addWidget(self._btn_scan)
        return w

    # ── Memory Scan tab ────────────────────────────────────────────────────

    def _build_memory_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        # Process controls
        proc_ctrl = QHBoxLayout()
        self._btn_refresh_procs = QPushButton("⟳  Обновить процессы")
        self._btn_refresh_procs.setObjectName("secondaryBtn")
        self._btn_refresh_procs.setFixedHeight(32)
        self._btn_refresh_procs.clicked.connect(self._refresh_remote_procs)
        self._mem_filter = QLineEdit()
        self._mem_filter.setPlaceholderText("Фильтр по имени процесса...")
        self._mem_filter.textChanged.connect(self._filter_remote_procs)
        self._mem_proc_count = QLabel("0 процессов")
        self._mem_proc_count.setStyleSheet("color:#6e7681;font-size:11px;")
        proc_ctrl.addWidget(self._btn_refresh_procs)
        proc_ctrl.addWidget(self._mem_filter)
        proc_ctrl.addWidget(self._mem_proc_count)
        lay.addLayout(proc_ctrl)

        grp_procs = QGroupBox("ПРОЦЕССЫ УДАЛЁННОГО ХОСТА")
        gp = QVBoxLayout(grp_procs)
        self._mem_proc_tbl = QTableWidget(0, 3)
        self._mem_proc_tbl.setHorizontalHeaderLabels(["PID", "Имя", "Путь к EXE"])
        self._mem_proc_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._mem_proc_tbl.horizontalHeader().resizeSection(0, 55)
        self._mem_proc_tbl.horizontalHeader().resizeSection(1, 150)
        self._mem_proc_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._mem_proc_tbl.setMaximumHeight(140)
        gp.addWidget(self._mem_proc_tbl)
        lay.addWidget(grp_procs)

        # Memory YARA rules
        grp_rules_m = QGroupBox("YARA ПРАВИЛА ДЛЯ ПАМЯТИ")
        gr_m = QVBoxLayout(grp_rules_m)
        gr_m.setSpacing(4)

        top_row_m = QHBoxLayout()
        btn_all_m  = QPushButton("Все");    btn_all_m.setObjectName("secondaryBtn");  btn_all_m.setFixedHeight(24)
        btn_none_m = QPushButton("Ничего"); btn_none_m.setObjectName("secondaryBtn"); btn_none_m.setFixedHeight(24)
        btn_all_m.clicked.connect(lambda: (
            self._toggle_rules(self._mem_rule_list, True),
            self._update_rule_count(self._mem_rule_list, self._mem_rule_count)
        ))
        btn_none_m.clicked.connect(lambda: (
            self._toggle_rules(self._mem_rule_list, False),
            self._update_rule_count(self._mem_rule_list, self._mem_rule_count)
        ))
        self._mem_rule_count = QLabel("0 / 0 правил")
        self._mem_rule_count.setStyleSheet("color:#6e7681;font-size:11px;")
        top_row_m.addWidget(btn_all_m); top_row_m.addWidget(btn_none_m)
        top_row_m.addStretch(); top_row_m.addWidget(self._mem_rule_count)
        gr_m.addLayout(top_row_m)

        self._mem_rule_list = QListWidget()
        self._mem_rule_list.setMaximumHeight(140)
        for name in BUILTIN_YARA_RULES:
            item = QListWidgetItem(name)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._mem_rule_list.addItem(item)
        self._mem_rule_list.itemChanged.connect(
            lambda: self._update_rule_count(self._mem_rule_list, self._mem_rule_count))
        self._update_rule_count(self._mem_rule_list, self._mem_rule_count)
        gr_m.addWidget(self._mem_rule_list)

        grp_custom_m = QGroupBox("СВОЁ ПРАВИЛО")
        gc_m = QHBoxLayout(grp_custom_m)
        gc_m.setContentsMargins(8, 8, 8, 8)
        self._mem_rule_edit = QTextEdit()
        self._mem_rule_edit.setMaximumHeight(55)
        self._mem_rule_edit.setPlaceholderText('rule MyRule { strings: $s = "evil" condition: $s }')
        btn_add_m = QPushButton("➕ Добавить")
        btn_add_m.setObjectName("secondaryBtn")
        btn_add_m.setFixedWidth(100); btn_add_m.setFixedHeight(55)
        btn_add_m.clicked.connect(lambda: self._add_custom_rule(
            self._mem_rule_edit, self._mem_rule_list, self._mem_custom_rules))
        gc_m.addWidget(self._mem_rule_edit); gc_m.addWidget(btn_add_m)
        gr_m.addWidget(grp_custom_m)
        lay.addWidget(grp_rules_m)

        # Progress + status
        self._mem_prog = QProgressBar()
        self._mem_prog.setRange(0, 0); self._mem_prog.setFixedHeight(4)
        self._mem_prog.setVisible(False)
        lay.addWidget(self._mem_prog)

        self._mem_status = QLabel("Нажмите «Обновить процессы», затем выберите правила и «Scan Memory»")
        self._mem_status.setStyleSheet("color:#6e7681;font-size:11px;")
        self._mem_status.setWordWrap(True)
        lay.addWidget(self._mem_status)

        scan_row = QHBoxLayout()
        self._btn_mem_scan = QPushButton("▶  Scan Memory")
        self._btn_mem_scan.setFixedHeight(38)
        self._btn_mem_scan.clicked.connect(self._start_mem_scan)
        self._btn_mem_stop = QPushButton("⏹  Стоп")
        self._btn_mem_stop.setObjectName("dangerBtn")
        self._btn_mem_stop.setFixedWidth(90)
        self._btn_mem_stop.setEnabled(False)
        self._btn_mem_stop.clicked.connect(self._stop_mem_scan)
        scan_row.addWidget(self._btn_mem_scan); scan_row.addWidget(self._btn_mem_stop)
        lay.addLayout(scan_row)
        return w

    # ── Results panel ──────────────────────────────────────────────────────

    def _build_results_panel(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)

        self._tbl = QTableWidget(0, 3)
        self._tbl.setHorizontalHeaderLabels(["ТИП / ПРАВИЛО", "SEVERITY", "ФАЙЛ / ПРОЦЕСС"])
        self._tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tbl.horizontalHeader().resizeSection(0, 190)
        self._tbl.horizontalHeader().resizeSection(1, 80)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setStyleSheet(
            "QTableWidget{alternate-background-color:#0f1318;}")
        lay.addWidget(self._tbl)

        stats_row = QHBoxLayout()
        self._lbl_result_stats = QLabel("Нет данных")
        self._lbl_result_stats.setStyleSheet("color:#6e7681;font-size:11px;")
        btn_clear_tbl = QPushButton("Очистить")
        btn_clear_tbl.setObjectName("secondaryBtn"); btn_clear_tbl.setFixedHeight(24)
        btn_clear_tbl.clicked.connect(lambda: (self._tbl.setRowCount(0),
                                                self._lbl_result_stats.setText("Нет данных")))
        stats_row.addWidget(self._lbl_result_stats); stats_row.addStretch(); stats_row.addWidget(btn_clear_tbl)
        lay.addLayout(stats_row)
        return w

    # ── Log panel ──────────────────────────────────────────────────────────

    def _build_log_panel(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        self._scan_log = QTextEdit()
        self._scan_log.setReadOnly(True)
        self._scan_log.setStyleSheet(
            "background:#0a0e14;border:1px solid #21262d;border-radius:6px;"
            "font-family:Consolas,monospace;font-size:11px;color:#c9d1d9;padding:6px;"
        )
        lay.addWidget(self._scan_log)

        btn_clear_log = QPushButton("Очистить лог")
        btn_clear_log.setObjectName("secondaryBtn"); btn_clear_log.setFixedHeight(26)
        btn_clear_log.clicked.connect(self._scan_log.clear)
        lay.addWidget(btn_clear_log)
        return w

    # ── Shared helpers ─────────────────────────────────────────────────────

    def _log(self, msg: str, color: str = "#8b949e"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._scan_log.append(
            f'<span style="color:#484f58">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )
        self._result_tabs.setCurrentIndex(1)

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
            if rule_list.item(i).checkState() == Qt.CheckState.Checked
        )
        total = rule_list.count()
        label.setText(f"{checked} / {total} правил")
        label.setStyleSheet(
            f"font-size:11px;color:{'#3fb950' if checked else '#6e7681'};"
        )

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
        m    = re.search(r'rule\s+(\w+)', text)
        name = m.group(1) if m else f"Custom_{len(custom_store) + 1}"
        custom_store[name] = text
        # update existing item if already in list
        for i in range(rule_list.count()):
            if rule_list.item(i).text() == name:
                text_edit.clear()
                return
        item = QListWidgetItem(name)
        item.setCheckState(Qt.CheckState.Checked)
        item.setForeground(QColor("#58a6ff"))
        rule_list.addItem(item)
        text_edit.clear()

    def _browse_path(self):
        d = QFileDialog.getExistingDirectory(self, "Выберите директорию для сканирования")
        if d:
            self._path_inp.setText(d)

    def retranslate(self, _lang: str = ""):
        self._btn_add.setText("+ " + t("hosts_add_btn"))
        self._btn_remove.setText(t("hosts_remove_btn"))
        self._btn_deploy.setText("⚙ " + t("hosts_deploy_btn"))
        self._btn_ping.setText("⟳ " + t("hosts_ping_btn"))
        self._btn_scan.setText("▶  Сканировать")
        self._chk_hashes.setText(t("hosts_hashes_chk"))
        self._lbl_path.setText("Путь (remote):")
        self._tbl.setHorizontalHeaderLabels(["ТИП / ПРАВИЛО", "SEVERITY", "ФАЙЛ / ПРОЦЕСС"])
        if self._info_label.text() in (
            "Выбери хост слева", "Select a host on the left",
            "Сол жақтан хостты таңдаңыз", t("hosts_select_hint"),
        ):
            self._info_label.setText(t("hosts_select_hint"))
        self._reload_hosts()

    # ── Host list ──────────────────────────────────────────────────────────

    def _reload_hosts(self):
        self._host_list.clear()
        hosts = load_hosts()
        self._lbl_count.setText(t("hosts_count", n=len(hosts)))
        for h in hosts:
            item = QListWidgetItem(f"🖥  {h['name']}\n{h['ip']}:{h['port']}")
            item.setData(Qt.ItemDataRole.UserRole, h)
            self._host_list.addItem(item)

    def _on_host_select(self, row: int):
        # clear stale process data from previous host
        self._mem_proc_tbl.setRowCount(0)
        self._remote_procs = []
        self._mem_proc_count.setText("0 процессов")

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

        seen = host.get("last_seen") or "никогда"
        scan = host.get("last_scan") or "никогда"
        self._info_label.setText(
            f"<b style='color:#58a6ff'>{host['name']}</b>"
            f"  ·  <span style='color:#8b949e'>{host['ip']}:{host['port']}</span>"
            f"  ·  ping: {seen}"
            f"  ·  скан: {scan}"
        )
        if self._on_host_changed:
            self._on_host_changed(host)

    def _add_host(self):
        dlg = _AddHostDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["name"]:
            QMessageBox.warning(self, t("error"), t("hosts_add_error"))
            return
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

    # ── Ping ───────────────────────────────────────────────────────────────

    def _start_ping_timer(self):
        self._ping_timer = QTimer(self)
        self._ping_timer.timeout.connect(self._ping_all)
        self._ping_timer.start(30_000)

    def _ping_all(self):
        hosts = load_hosts()
        if not hosts:
            return
        if self._ping_worker is not None and self._ping_worker.isRunning():
            return
        self._ping_worker = PingWorker(hosts)
        self._ping_worker.result.connect(self._on_ping_result)
        self._ping_worker.start()

    def _ping_selected(self):
        if not self._selected_id:
            return
        if self._ping_worker is not None and self._ping_worker.isRunning():
            return
        hosts = [h for h in load_hosts() if h["id"] == self._selected_id]
        if hosts:
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
            if h["id"] == host_id:
                if online:
                    h["last_seen"] = ts
                item.setData(Qt.ItemDataRole.UserRole, h)
                status = "● online" if online else "● offline"
                color  = QColor("#3fb950") if online else QColor("#f85149")
                item.setForeground(color)
                item.setText(f"🖥  {h['name']}\n{h['ip']}:{h['port']}  {status}")
                # update info label if this host is selected
                if h["id"] == self._selected_id:
                    scan = h.get("last_scan") or "никогда"
                    self._info_label.setText(
                        f"<b style='color:#58a6ff'>{h['name']}</b>"
                        f"  ·  <span style='color:#8b949e'>{h['ip']}:{h['port']}</span>"
                        f"  ·  ping: {ts if online else '✗ offline'}"
                        f"  ·  скан: {scan}"
                    )
                break

    def _get_selected_host(self) -> dict | None:
        for i in range(self._host_list.count()):
            h = self._host_list.item(i).data(Qt.ItemDataRole.UserRole)
            if h["id"] == self._selected_id:
                return h
        return None

    # ── File scan ──────────────────────────────────────────────────────────

    def _start_file_scan(self):
        host = self._get_selected_host()
        if not host:
            return
        if self._scan_worker is not None and self._scan_worker.isRunning():
            self._file_status.setText("⚠ Сканирование уже выполняется")
            return

        rules = self._get_selected_rules(self._file_rule_list, self._file_custom_rules)
        scan_types = []
        if rules:
            scan_types.append("yara")
        if self._chk_ioc.isChecked():
            scan_types.append("ioc")
        if self._chk_hashes.isChecked():
            scan_types.append("hashes")

        if not scan_types:
            self._file_status.setText("⚠ Выберите хотя бы одно правило YARA, IOC или Хэши")
            self._log("Сканирование не запущено: не выбраны типы проверок", "#d29922")
            return

        path = self._path_inp.text().strip()
        if not path:
            self._file_status.setText("⚠ Укажите путь для сканирования")
            return

        host_label = f"{host['name']} ({host['ip']})"
        self._log(
            f"▶ Запуск файлового скана на <b>{host_label}</b>  "
            f"| YARA правил: {len(rules)}  | Путь: {path}",
            "#58a6ff"
        )
        if rules:
            self._log(f"  Правила: {', '.join(list(rules.keys())[:8])}{'...' if len(rules) > 8 else ''}", "#6e7681")

        self._btn_scan.setEnabled(False)
        self._file_prog.setVisible(True)
        self._tbl.setRowCount(0)
        self._lbl_result_stats.setText("Сканирование...")
        self._file_status.setText(f"Подключение к {host['ip']}...")

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
        self._file_status.setText(f"✘ Ошибка: {msg[:120]}")
        self._log(f"✘ Ошибка файлового скана: {msg}", "#f85149")
        self._result_tabs.setCurrentIndex(1)

    def _on_file_finished(self):
        self._btn_scan.setEnabled(True)
        self._file_prog.setVisible(False)

    # ── Memory scan ────────────────────────────────────────────────────────

    def _refresh_remote_procs(self):
        host = self._get_selected_host()
        if not host or (self._proc_worker and self._proc_worker.isRunning()):
            return
        self._btn_refresh_procs.setEnabled(False)
        self._mem_status.setText("Загрузка списка процессов...")
        self._log(f"⟳ Получение процессов с {host['name']} ({host['ip']})", "#58a6ff")
        self._proc_worker = RemoteProcessListWorker(host)
        self._proc_worker.done.connect(self._on_procs_loaded)
        self._proc_worker.error.connect(lambda e: (
            self._mem_status.setText(f"✘ Ошибка: {e}"),
            self._log(f"✘ Ошибка получения процессов: {e}", "#f85149")
        ))
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
            for col, txt in enumerate([
                str(p.get("pid", "")),
                p.get("name", ""),
                p.get("exe", ""),
            ]):
                item = QTableWidgetItem(txt)
                item.setFont(QFont("Consolas", 10))
                self._mem_proc_tbl.setItem(row, col, item)
        self._mem_proc_count.setText(f"{len(procs)} процессов")

    def _filter_remote_procs(self, text: str):
        lo = text.lower()
        filtered = [p for p in self._remote_procs
                    if not lo or lo in p.get("name", "").lower()]
        self._render_remote_procs(filtered)

    def _start_mem_scan(self):
        host = self._get_selected_host()
        if not host:
            return
        if self._mem_worker is not None and self._mem_worker.isRunning():
            self._mem_status.setText("⚠ Сканирование уже выполняется")
            return
        rules = self._get_selected_rules(self._mem_rule_list, self._mem_custom_rules)
        if not rules:
            self._mem_status.setText("⚠ Выберите хотя бы одно YARA правило")
            return

        host_label = f"{host['name']} ({host['ip']})"
        self._mem_stop_requested = False
        self._log(
            f"▶ Запуск Memory Scan на <b>{host_label}</b>  | правил: {len(rules)}",
            "#a371f7"
        )

        self._btn_mem_scan.setEnabled(False)
        self._btn_mem_stop.setEnabled(True)
        self._mem_prog.setVisible(True)
        self._tbl.setRowCount(0)
        self._lbl_result_stats.setText("Memory Scan...")
        self._mem_status.setText(f"Сканирование памяти на {host['ip']}...")

        self._mem_worker = RemoteMemScanWorker(host, rules)
        self._mem_worker.progress.connect(lambda m: (
            self._mem_status.setText(m),
            self._log(f"  {m}", "#6e7681")
        ))
        self._mem_worker.done.connect(
            lambda r: None if self._mem_stop_requested else self._on_results_done(r, host)
        )
        self._mem_worker.error.connect(lambda m: (
            self._mem_status.setText(f"✘ {m}"),
            self._log(f"✘ Ошибка Memory Scan: {m}", "#f85149")
        ))
        self._mem_worker.finished.connect(self._on_mem_finished)
        self._mem_worker.start()

    def _on_mem_finished(self):
        self._btn_mem_scan.setEnabled(True)
        self._btn_mem_stop.setEnabled(False)
        self._mem_prog.setVisible(False)

    def _stop_mem_scan(self):
        self._mem_stop_requested = True
        if self._mem_worker:
            self._mem_worker.stop()
        self._btn_mem_stop.setEnabled(False)
        self._mem_status.setText("Остановлено пользователем")
        self._log("⏹ Memory Scan остановлен пользователем", "#d29922")

    # ── Shared results handler ─────────────────────────────────────────────

    def _on_results_done(self, results: list, host: dict):
        try:
            ts         = datetime.now().strftime("%H:%M:%S")
            host_label = f"{host['name']} ({host['ip']})"

            # persist last_scan timestamp
            update_host(host["id"], last_scan=ts)
            for i in range(self._host_list.count()):
                item = self._host_list.item(i)
                h    = item.data(Qt.ItemDataRole.UserRole)
                if h.get("id") == host.get("id"):
                    h["last_scan"] = ts
                    item.setData(Qt.ItemDataRole.UserRole, h)
                    break

            colors = {
                "YARA":   "#58a6ff",
                "IOC":    "#d29922",
                "HASH":   "#8b949e",
                "MEMORY": "#a371f7",
            }
            sev_colors = {
                "critical": "#f85149", "high": "#d29922",
                "medium":   "#58a6ff", "low":  "#3fb950",
            }

            self._tbl.setRowCount(len(results))
            real_hits = 0
            for i, r in enumerate(results):
                typ  = r.get("type", "?")
                rule = r.get("rule", "?")
                proc = r.get("process_name", "")
                fil  = f"[{proc}] {r.get('file', '?')}" if proc else r.get("file", "?")
                sev  = r.get("severity", "")
                col  = sev_colors.get(sev.lower(), "") or colors.get(typ, "#8b949e")

                ri = QTableWidgetItem(f"[{typ}]  {rule}")
                si = QTableWidgetItem(sev.upper() if sev else typ)
                fi = QTableWidgetItem(fil)
                ri.setForeground(QColor(col)); si.setForeground(QColor(col))
                for it in (ri, si, fi):
                    it.setFont(QFont("Consolas", 11))
                self._tbl.setItem(i, 0, ri)
                self._tbl.setItem(i, 1, si)
                self._tbl.setItem(i, 2, fi)

                # log to dashboard
                DashboardTab.log_event(
                    typ, f"{rule} — {fil}",
                    level="high" if sev.lower() in ("critical", "high") else "info",
                    severity=sev.capitalize() if sev else typ,
                    scan=True, target=fil[:60], host=host_label,
                )

                # count real detections (skip meta sentinel entries)
                if rule not in ("ERROR", "TIMEOUT", "WARN", "INFO", "COMPILE_ERR", "DEBUG"):
                    real_hits += 1

            # Update stats
            yara_hits = sum(1 for r in results
                            if r.get("type") in ("YARA", "MEMORY")
                            and r.get("rule", "") not in ("ERROR", "TIMEOUT", "WARN", "INFO", "COMPILE_ERR"))
            sus_procs = sum(1 for r in results
                            if r.get("type") == "IOC"
                            and r.get("rule") == "Подозрит. процесс")
            DashboardTab.stats["yara_hits"]        += yara_hits
            DashboardTab.stats["suspicious_procs"] += sus_procs

            # Update UI
            if real_hits:
                msg_color = "#d29922"
                msg = f"✓ Найдено: {real_hits} совпадений (всего записей: {len(results)})"
            elif results:
                msg_color = "#8b949e"
                msg = f"✓ Сканирование завершено — чисто ({len(results)} записей)"
            else:
                msg_color = "#3fb950"
                msg = "✓ Сканирование завершено — угрозы не обнаружены"

            self._file_status.setText(msg)
            self._mem_status.setText(msg)
            self._lbl_result_stats.setText(
                f"{real_hits} совпадений · {len(results)} записей · {host_label}")
            self._log(msg, msg_color)

            # show results tab
            self._result_tabs.setCurrentIndex(0)

        except Exception as e:
            self._log(f"✘ Ошибка обработки результатов: {e}", "#f85149")

    # ── Deploy ─────────────────────────────────────────────────────────────

    def _deploy(self):
        dlg = _DeployDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["username"]:
            QMessageBox.warning(self, t("error"), t("hosts_deploy_required"))
            return
        if self._deploy_worker is not None and self._deploy_worker.isRunning():
            self._file_status.setText("Deploy уже выполняется...")
            return
        self._btn_deploy.setEnabled(False)
        self._file_prog.setVisible(True)
        self._file_status.setText("Деплой агента...")
        self._log(f"⚙ Начинаем деплой агента на {d['ip']}...", "#58a6ff")
        self._deploy_worker = DeployWorker(d["ip"], d["username"], d["password"])
        self._deploy_worker.progress.connect(lambda m: (
            self._file_status.setText(m),
            self._log(f"  {m}", "#6e7681")
        ))
        self._deploy_worker.error.connect(self._on_deploy_error)
        self._deploy_worker.done.connect(lambda tok: self._on_deploy_done(d["ip"], tok))
        self._deploy_worker.finished.connect(lambda: (
            self._btn_deploy.setEnabled(True),
            self._file_prog.setVisible(False),
        ))
        self._deploy_worker.start()

    def _on_deploy_done(self, ip: str, token: str):
        self._file_status.setText(f"✓ Агент задеплоен на {ip}")
        self._log(f"✓ Агент успешно задеплоен на {ip}. Токен: {token[:16]}...", "#3fb950")
        QMessageBox.information(
            self, t("hosts_deploy_done_title"),
            t("hosts_deploy_done_msg", ip=ip, tok=token),
        )

    def _on_deploy_error(self, msg: str):
        self._file_status.setText(f"✘ Deploy ошибка: {msg[:80]}")
        self._log(f"✘ Deploy ошибка: {msg}", "#f85149")
        QMessageBox.warning(self, t("hosts_deploy_error_title"), msg)
