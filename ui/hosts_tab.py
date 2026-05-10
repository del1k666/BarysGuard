from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QListWidget,
    QListWidgetItem, QCheckBox, QSplitter, QLineEdit, QDialog, QFormLayout,
    QDialogButtonBox, QMessageBox, QSpinBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from core.hosts_config import load_hosts, add_host, remove_host, update_host
from workers.host_worker import PingWorker, RemoteScanWorker, DeployWorker
from constants import BUILTIN_YARA_RULES
from core.i18n import t
from core.lang_signal import lang_signal
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

        # Right panel — detail and scan
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
        self._btn_scan = QPushButton(t("hosts_scan_btn"))
        self._btn_scan.setFixedHeight(34)
        self._btn_scan.setEnabled(False)
        self._btn_scan.clicked.connect(self._scan)
        act_row.addWidget(self._btn_deploy)
        act_row.addWidget(self._btn_ping)
        act_row.addStretch()
        act_row.addWidget(self._btn_scan)
        rl.addLayout(act_row)

        self._grp_opt = QGroupBox(t("hosts_what_to_scan"))
        opt_lay = QHBoxLayout(self._grp_opt)
        self._chk_yara   = QCheckBox("YARA")
        self._chk_yara.setChecked(True)
        self._chk_ioc    = QCheckBox("IOC")
        self._chk_ioc.setChecked(True)
        self._chk_hashes = QCheckBox(t("hosts_hashes_chk"))
        self._path_inp   = QLineEdit()
        self._path_inp.setPlaceholderText(r"C:\Users")
        self._path_inp.setText(r"C:\Users")
        self._lbl_path = QLabel(t("hosts_path_label"))
        opt_lay.addWidget(self._chk_yara)
        opt_lay.addWidget(self._chk_ioc)
        opt_lay.addWidget(self._chk_hashes)
        opt_lay.addWidget(self._lbl_path)
        opt_lay.addWidget(self._path_inp)
        rl.addWidget(self._grp_opt)

        self._prog = QProgressBar()
        self._prog.setRange(0, 0)
        self._prog.setFixedHeight(5)
        self._prog.setVisible(False)
        self._status = QLabel(t("hosts_ready"))
        self._status.setStyleSheet("color:#8b949e;font-size:11px;")
        rl.addWidget(self._prog)
        rl.addWidget(self._status)

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

    def retranslate(self, _lang: str = ""):
        self._btn_add.setText(t("hosts_add_btn"))
        self._btn_remove.setText(t("hosts_remove_btn"))
        self._btn_deploy.setText(t("hosts_deploy_btn"))
        self._btn_ping.setText(t("hosts_ping_btn"))
        self._btn_scan.setText(t("hosts_scan_btn"))
        self._grp_opt.setTitle(t("hosts_what_to_scan"))
        self._chk_hashes.setText(t("hosts_hashes_chk"))
        self._lbl_path.setText(t("hosts_path_label"))
        self._grp_res.setTitle(t("hosts_results"))
        self._tbl.setHorizontalHeaderLabels([
            t("hosts_tbl_type"), "Severity", t("hosts_tbl_file")
        ])
        if self._status.text() in (
            "Готов", "Ready", "Дайын",
            t("hosts_ready"),
        ):
            self._status.setText(t("hosts_ready"))
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
        if row < 0:
            self._selected_id = None
            self._btn_remove.setEnabled(False)
            self._btn_deploy.setEnabled(False)
            self._btn_ping.setEnabled(False)
            self._btn_scan.setEnabled(False)
            self._info_label.setText(t("hosts_select_hint"))
            return
        host = self._host_list.item(row).data(Qt.ItemDataRole.UserRole)
        self._selected_id = host["id"]
        self._btn_remove.setEnabled(True)
        self._btn_deploy.setEnabled(True)
        self._btn_ping.setEnabled(True)
        self._btn_scan.setEnabled(True)
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

    def _scan(self):
        host = self._get_selected_host()
        if not host:
            return
        if self._scan_worker is not None and self._scan_worker.isRunning():
            self._status.setText(t("hosts_already_running"))
            return

        scan_types = []
        if self._chk_yara.isChecked():
            scan_types.append("yara")
        if self._chk_ioc.isChecked():
            scan_types.append("ioc")
        if self._chk_hashes.isChecked():
            scan_types.append("hashes")

        if not scan_types:
            self._status.setText(t("hosts_no_scan_type"))
            return

        path = self._path_inp.text().strip()
        if not path:
            self._status.setText(t("hosts_no_path"))
            return

        self._btn_scan.setEnabled(False)
        self._prog.setVisible(True)
        self._tbl.setRowCount(0)

        self._scan_worker = RemoteScanWorker(
            host, scan_types, path, BUILTIN_YARA_RULES
        )
        self._scan_worker.progress.connect(self._status.setText)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.finished.connect(lambda: (
            self._btn_scan.setEnabled(True), self._prog.setVisible(False)
        ))
        self._scan_worker.start()
        ts = datetime.now().strftime("%H:%M:%S")
        update_host(host["id"], last_scan=ts)
        for i in range(self._host_list.count()):
            item = self._host_list.item(i)
            h = item.data(Qt.ItemDataRole.UserRole)
            if h["id"] == host["id"]:
                h["last_scan"] = ts
                item.setData(Qt.ItemDataRole.UserRole, h)
                break

    def _on_scan_done(self, results: list):
        colors = {"YARA": "#58a6ff", "IOC": "#d29922", "HASH": "#8b949e"}
        self._tbl.setRowCount(len(results))
        for i, r in enumerate(results):
            typ  = r.get("type", "?")
            rule = r.get("rule", "?")
            fil  = r.get("file", "?")
            col  = colors.get(typ, "#8b949e")
            ri = QTableWidgetItem(f"[{typ}] {rule}")
            si = QTableWidgetItem(r.get("severity", typ))
            fi = QTableWidgetItem(fil)
            ri.setForeground(QColor(col))
            si.setForeground(QColor(col))
            for it in (ri, si, fi):
                it.setFont(QFont("Consolas", 11))
            self._tbl.setItem(i, 0, ri)
            self._tbl.setItem(i, 1, si)
            self._tbl.setItem(i, 2, fi)
        hits = len([r for r in results if r.get("type") in ("YARA", "IOC")])
        self._status.setText(t("hosts_found", hits=hits, total=len(results)))

    def _on_scan_error(self, msg: str):
        self._status.setText(t("hosts_error", msg=msg))

    def _deploy(self):
        dlg = _DeployDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["username"]:
            QMessageBox.warning(self, t("error"), t("hosts_deploy_required"))
            return
        if self._deploy_worker is not None and self._deploy_worker.isRunning():
            self._status.setText(t("hosts_deploy_running"))
            return
        self._btn_deploy.setEnabled(False)
        self._prog.setVisible(True)
        self._status.setText(t("hosts_deploying"))
        self._deploy_worker = DeployWorker(d["ip"], d["username"], d["password"])
        self._deploy_worker.progress.connect(self._status.setText)
        self._deploy_worker.error.connect(self._on_deploy_error)
        self._deploy_worker.done.connect(lambda tok: self._on_deploy_done(d["ip"], tok))
        self._deploy_worker.finished.connect(lambda: (
            self._btn_deploy.setEnabled(True), self._prog.setVisible(False)
        ))
        self._deploy_worker.start()

    def _on_deploy_done(self, ip: str, token: str):
        self._status.setText(t("hosts_deploy_done_status", ip=ip))
        QMessageBox.information(
            self, t("hosts_deploy_done_title"),
            t("hosts_deploy_done_msg", ip=ip, tok=token),
        )

    def _on_deploy_error(self, msg: str):
        self._status.setText(t("hosts_error", msg=msg))
        QMessageBox.warning(self, t("hosts_deploy_error_title"), msg)
