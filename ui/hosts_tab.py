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


class _AddHostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("hosts_add_dialog_title"))
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        self._name  = QLineEdit(); self._name.setPlaceholderText("WS-FINANCE01")
        self._ip    = QLineEdit(); self._ip.setPlaceholderText("192.168.1.10")
        self._port  = QSpinBox();  self._port.setRange(1, 65535); self._port.setValue(5555)
        self._token = QLineEdit(); self._token.setPlaceholderText("agent/token.txt")
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
        self._on_host_changed = on_host_changed
        self._on_hosts_list_changed = on_hosts_list_changed
        self._selected_id: str | None = None
        self._ping_worker: PingWorker | None = None
        self._scan_worker: RemoteScanWorker | None = None
        self._deploy_worker: DeployWorker | None = None
        self._proc_worker: RemoteProcessListWorker | None = None
        self._mem_worker:  RemoteMemScanWorker | None = None
        self._mem_stop_requested: bool = False
        self._file_custom_rules: dict = {}
        self._mem_custom_rules:  dict = {}
        self._remote_procs: list = []
        self._build()
        self._reload_hosts()
        self._start_ping_timer()
        lang_signal.changed.connect(self.retranslate)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel — host list
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)

        self._lbl_count = QLabel(t("hosts_count", n=0))
        self._lbl_count.setStyleSheet("color:#8b949e;font-size:11px;")
        ll.addWidget(self._lbl_count)

        self._host_list = QListWidget()
        self._host_list.currentRowChanged.connect(self._on_host_select)
        ll.addWidget(self._host_list)

        row_btns = QHBoxLayout()
        self._btn_add = QPushButton(t("hosts_add_btn"))
        self._btn_add.setObjectName("secondaryBtn")
        self._btn_add.clicked.connect(self._add_host)
        self._btn_remove = QPushButton(t("hosts_remove_btn"))
        self._btn_remove.setObjectName("secondaryBtn")
        self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._remove_host)
        row_btns.addWidget(self._btn_add)
        row_btns.addWidget(self._btn_remove)
        ll.addLayout(row_btns)

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

    # ── Shared helpers ────────────────────────────────────────────────

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
        for i in range(rule_list.count()):
            if rule_list.item(i).text() == name:
                text_edit.clear()
                return
        item = QListWidgetItem(name)
        item.setCheckState(Qt.CheckState.Checked)
        item.setForeground(QColor("#58a6ff"))
        rule_list.addItem(item)
        text_edit.clear()

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

    def _reload_hosts(self):
        self._host_list.clear()
        hosts = load_hosts()
        self._lbl_count.setText(t("hosts_count", n=len(hosts)))
        for h in hosts:
            item = QListWidgetItem(f"\U0001f5a5 {h['name']}\n{h['ip']}:{h['port']}")
            item.setData(Qt.ItemDataRole.UserRole, h)
            self._host_list.addItem(item)

    def _on_host_select(self, row: int):
        self._mem_proc_tbl.setRowCount(0)
        self._remote_procs = []
        self._mem_proc_count.setText("Процессов: 0")
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
                status = t("hosts_ping_online") if online else t("hosts_ping_offline")
                color  = QColor("#3fb950") if online else QColor("#f85149")
                item.setForeground(color)
                item.setText(f"\U0001f5a5 {h['name']}\n{h['ip']}:{h['port']}  {status}")
                break

    def _get_selected_host(self) -> dict | None:
        for i in range(self._host_list.count()):
            h = self._host_list.item(i).data(Qt.ItemDataRole.UserRole)
            if h["id"] == self._selected_id:
                return h
        return None

    # ── File scan ─────────────────────────────────────────────────────

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

    # ── Memory scan ───────────────────────────────────────────────────

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
            for i, txt in enumerate([str(p.get("pid", "")),
                                      p.get("name", ""), p.get("exe", "")]):
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

        self._mem_stop_requested = False
        self._btn_mem_scan.setEnabled(False)
        self._btn_mem_stop.setEnabled(True)
        self._mem_prog.setVisible(True)
        self._tbl.setRowCount(0)

        self._mem_worker = RemoteMemScanWorker(host, rules)
        self._mem_worker.progress.connect(self._mem_status.setText)
        self._mem_worker.done.connect(
            lambda r: None if self._mem_stop_requested else self._on_results_done(r, host)
        )
        self._mem_worker.error.connect(lambda m: self._mem_status.setText(f"Ошибка: {m}"))
        self._mem_worker.finished.connect(lambda: (
            self._btn_mem_scan.setEnabled(True),
            self._btn_mem_stop.setEnabled(False),
            self._mem_prog.setVisible(False),
        ))
        self._mem_worker.start()

    def _stop_mem_scan(self):
        self._mem_stop_requested = True
        if self._mem_worker:
            self._mem_worker.stop()
        self._btn_mem_stop.setEnabled(False)
        self._mem_status.setText("Остановлено пользователем")

    # ── Shared results handler ────────────────────────────────────────

    def _on_results_done(self, results: list, host: dict):
        ts = datetime.now().strftime("%H:%M:%S")
        host_label = f"{host['name']} ({host['ip']})"
        update_host(host["id"], last_scan=ts)
        for i in range(self._host_list.count()):
            item = self._host_list.item(i)
            h = item.data(Qt.ItemDataRole.UserRole)
            if h.get("id") == host.get("id"):
                h["last_scan"] = ts
                item.setData(Qt.ItemDataRole.UserRole, h)
                break
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
        sus_procs = sum(
            1 for r in results
            if r.get("type") == "IOC" and r.get("rule") == "Подозрит. процесс"
        )
        DashboardTab.stats["yara_hits"]       += yara_hits
        DashboardTab.stats["suspicious_procs"] += sus_procs

        hits = len([r for r in results if r.get("type") in ("YARA", "IOC", "MEMORY")])
        msg  = t("hosts_found", hits=hits, total=len(results))
        self._file_status.setText(msg)
        self._mem_status.setText(msg)

    # ── Deploy ────────────────────────────────────────────────────────

    def _deploy(self):
        dlg = _DeployDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["username"]:
            QMessageBox.warning(self, t("error"), t("hosts_deploy_required"))
            return
        if self._deploy_worker is not None and self._deploy_worker.isRunning():
            self._file_status.setText(t("hosts_deploy_running"))
            return
        self._btn_deploy.setEnabled(False)
        self._file_prog.setVisible(True)
        self._file_status.setText(t("hosts_deploying"))
        self._deploy_worker = DeployWorker(d["ip"], d["username"], d["password"])
        self._deploy_worker.progress.connect(self._file_status.setText)
        self._deploy_worker.error.connect(self._on_deploy_error)
        self._deploy_worker.done.connect(lambda tok: self._on_deploy_done(d["ip"], tok))
        self._deploy_worker.finished.connect(lambda: (
            self._btn_deploy.setEnabled(True), self._file_prog.setVisible(False)
        ))
        self._deploy_worker.start()

    def _on_deploy_done(self, ip: str, token: str):
        self._file_status.setText(t("hosts_deploy_done_status", ip=ip))
        QMessageBox.information(
            self, t("hosts_deploy_done_title"),
            t("hosts_deploy_done_msg", ip=ip, tok=token),
        )

    def _on_deploy_error(self, msg: str):
        self._file_status.setText(t("hosts_error", msg=msg))
        QMessageBox.warning(self, t("hosts_deploy_error_title"), msg)
