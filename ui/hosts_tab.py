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
from datetime import datetime


class _AddHostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить хост")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        self._name  = QLineEdit(); self._name.setPlaceholderText("WS-FINANCE01")
        self._ip    = QLineEdit(); self._ip.setPlaceholderText("192.168.1.10")
        self._port  = QSpinBox();  self._port.setRange(1, 65535); self._port.setValue(5555)
        self._token = QLineEdit(); self._token.setPlaceholderText("из agent/token.txt")
        layout.addRow("Имя:",    self._name)
        layout.addRow("IP:",     self._ip)
        layout.addRow("Порт:",   self._port)
        layout.addRow("Токен:",  self._token)
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
        self.setWindowTitle("Deploy агента (WinRM)")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        self._ip   = QLineEdit(); self._ip.setPlaceholderText("192.168.1.10")
        self._user = QLineEdit(); self._user.setPlaceholderText("DOMAIN\\admin или admin")
        self._pwd  = QLineEdit(); self._pwd.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("IP хоста:", self._ip)
        layout.addRow("Пользователь:", self._user)
        layout.addRow("Пароль:", self._pwd)
        note = QLabel("Требует WinRM (порт 5985) на целевом хосте.")
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
    def __init__(self, on_host_changed=None):
        super().__init__()
        self._on_host_changed = on_host_changed
        self._selected_id: str | None = None
        self._ping_worker: PingWorker | None = None
        self._scan_worker: RemoteScanWorker | None = None
        self._deploy_worker: DeployWorker | None = None
        self._build()
        self._reload_hosts()
        self._start_ping_timer()

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

        self._lbl_count = QLabel("Хосты (0)")
        self._lbl_count.setStyleSheet("color:#8b949e;font-size:11px;")
        ll.addWidget(self._lbl_count)

        self._host_list = QListWidget()
        self._host_list.currentRowChanged.connect(self._on_host_select)
        ll.addWidget(self._host_list)

        row_btns = QHBoxLayout()
        btn_add = QPushButton("+ Добавить")
        btn_add.setObjectName("secondaryBtn")
        btn_add.clicked.connect(self._add_host)
        self._btn_remove = QPushButton("Удалить")
        self._btn_remove.setObjectName("secondaryBtn")
        self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._remove_host)
        row_btns.addWidget(btn_add)
        row_btns.addWidget(self._btn_remove)
        ll.addLayout(row_btns)

        splitter.addWidget(left)

        # Right panel — detail and scan
        right = QWidget()
        rl    = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        self._info_label = QLabel("Выбери хост слева")
        self._info_label.setStyleSheet("color:#8b949e;font-size:12px;padding:8px;")
        rl.addWidget(self._info_label)

        act_row = QHBoxLayout()
        self._btn_deploy = QPushButton("📦 Deploy агента")
        self._btn_deploy.setObjectName("secondaryBtn")
        self._btn_deploy.setEnabled(False)
        self._btn_deploy.clicked.connect(self._deploy)
        self._btn_ping = QPushButton("⟳ Ping")
        self._btn_ping.setObjectName("secondaryBtn")
        self._btn_ping.setEnabled(False)
        self._btn_ping.clicked.connect(self._ping_selected)
        self._btn_scan = QPushButton("▶ Сканировать")
        self._btn_scan.setFixedHeight(34)
        self._btn_scan.setEnabled(False)
        self._btn_scan.clicked.connect(self._scan)
        act_row.addWidget(self._btn_deploy)
        act_row.addWidget(self._btn_ping)
        act_row.addStretch()
        act_row.addWidget(self._btn_scan)
        rl.addLayout(act_row)

        grp_opt = QGroupBox("Что сканировать")
        opt_lay = QHBoxLayout(grp_opt)
        self._chk_yara   = QCheckBox("YARA")
        self._chk_yara.setChecked(True)
        self._chk_ioc    = QCheckBox("IOC")
        self._chk_ioc.setChecked(True)
        self._chk_hashes = QCheckBox("Хэши файлов")
        self._path_inp   = QLineEdit()
        self._path_inp.setPlaceholderText(r"C:\Users")
        self._path_inp.setText(r"C:\Users")
        opt_lay.addWidget(self._chk_yara)
        opt_lay.addWidget(self._chk_ioc)
        opt_lay.addWidget(self._chk_hashes)
        opt_lay.addWidget(QLabel("Путь:"))
        opt_lay.addWidget(self._path_inp)
        rl.addWidget(grp_opt)

        self._prog = QProgressBar()
        self._prog.setRange(0, 0)
        self._prog.setFixedHeight(5)
        self._prog.setVisible(False)
        self._status = QLabel("Готов")
        self._status.setStyleSheet("color:#8b949e;font-size:11px;")
        rl.addWidget(self._prog)
        rl.addWidget(self._status)

        grp_res = QGroupBox("Результаты")
        res_lay = QVBoxLayout(grp_res)
        self._tbl = QTableWidget(0, 3)
        self._tbl.setHorizontalHeaderLabels(["Тип / Правило", "Severity", "Файл / Детали"])
        self._tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tbl.horizontalHeader().resizeSection(0, 180)
        self._tbl.horizontalHeader().resizeSection(1, 70)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        res_lay.addWidget(self._tbl)
        rl.addWidget(grp_res)

        splitter.addWidget(right)
        splitter.setSizes([220, 560])
        lay.addWidget(splitter)

    def _reload_hosts(self):
        self._host_list.clear()
        hosts = load_hosts()
        self._lbl_count.setText(f"Хосты ({len(hosts)})")
        for h in hosts:
            item = QListWidgetItem(f"🖥 {h['name']}\n{h['ip']}:{h['port']}")
            item.setData(Qt.ItemDataRole.UserRole, h)
            self._host_list.addItem(item)

    def _on_host_select(self, row: int):
        if row < 0:
            self._selected_id = None
            self._btn_remove.setEnabled(False)
            self._btn_deploy.setEnabled(False)
            self._btn_ping.setEnabled(False)
            self._btn_scan.setEnabled(False)
            self._info_label.setText("Выбери хост слева")
            return
        host = self._host_list.item(row).data(Qt.ItemDataRole.UserRole)
        self._selected_id = host["id"]
        self._btn_remove.setEnabled(True)
        self._btn_deploy.setEnabled(True)
        self._btn_ping.setEnabled(True)
        self._btn_scan.setEnabled(True)
        seen = host.get("last_seen") or "никогда"
        scan = host.get("last_scan") or "никогда"
        self._info_label.setText(
            f"<b>{host['name']}</b>  ·  {host['ip']}:{host['port']}"
            f"  ·  последний ping: {seen}  ·  последний скан: {scan}"
        )
        if self._on_host_changed:
            self._on_host_changed(host)

    def _add_host(self):
        dlg = _AddHostDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["name"]:
            QMessageBox.warning(self, "Ошибка", "IP и Имя обязательны")
            return
        add_host(d["name"], d["ip"], d["port"], d["token"])
        self._reload_hosts()

    def _remove_host(self):
        if not self._selected_id:
            return
        if QMessageBox.question(
            self, "Удалить хост?", "Удалить этот хост из списка?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        remove_host(self._selected_id)
        self._selected_id = None
        if self._on_host_changed:
            self._on_host_changed(None)
        self._reload_hosts()

    def _start_ping_timer(self):
        self._ping_timer = QTimer(self)
        self._ping_timer.timeout.connect(self._ping_all)
        self._ping_timer.start(30_000)

    def _ping_all(self):
        hosts = load_hosts()
        if not hosts:
            return
        self._ping_worker = PingWorker(hosts)
        self._ping_worker.result.connect(self._on_ping_result)
        self._ping_worker.start()

    def _ping_selected(self):
        if not self._selected_id:
            return
        hosts = [h for h in load_hosts() if h["id"] == self._selected_id]
        if hosts:
            self._ping_worker = PingWorker(hosts)
            self._ping_worker.result.connect(self._on_ping_result)
            self._ping_worker.start()

    def _on_ping_result(self, host_id: str, online: bool, info: dict):
        ts = datetime.now().strftime("%H:%M:%S")
        update_host(host_id, last_seen=ts if online else None)
        for i in range(self._host_list.count()):
            item = self._host_list.item(i)
            h    = item.data(Qt.ItemDataRole.UserRole)
            if h["id"] == host_id:
                h["last_seen"] = ts if online else None
                item.setData(Qt.ItemDataRole.UserRole, h)
                status = "● online" if online else "● offline"
                color  = QColor("#3fb950") if online else QColor("#f85149")
                item.setForeground(color)
                item.setText(f"🖥 {h['name']}\n{h['ip']}:{h['port']}  {status}")
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

        scan_types = []
        if self._chk_yara.isChecked():
            scan_types.append("yara")
        if self._chk_ioc.isChecked():
            scan_types.append("ioc")
        if self._chk_hashes.isChecked():
            scan_types.append("hashes")

        if not scan_types:
            self._status.setText("Выбери хотя бы один тип скана")
            return

        self._btn_scan.setEnabled(False)
        self._prog.setVisible(True)
        self._tbl.setRowCount(0)

        self._scan_worker = RemoteScanWorker(
            host, scan_types, self._path_inp.text().strip(), BUILTIN_YARA_RULES
        )
        self._scan_worker.progress.connect(self._status.setText)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.finished.connect(lambda: (
            self._btn_scan.setEnabled(True), self._prog.setVisible(False)
        ))
        self._scan_worker.start()
        update_host(host["id"], last_scan=datetime.now().strftime("%H:%M:%S"))
        self._reload_hosts()

    def _on_scan_done(self, results: list):
        colors = {"YARA": "#58a6ff", "IOC": "#d29922", "HASH": "#8b949e"}
        self._tbl.setRowCount(len(results))
        for i, r in enumerate(results):
            typ  = r.get("type", "?")
            rule = r.get("rule", "?")
            fil  = r.get("file", "?")
            col  = colors.get(typ, "#8b949e")
            ri = QTableWidgetItem(f"[{typ}] {rule}")
            si = QTableWidgetItem(typ)
            fi = QTableWidgetItem(fil)
            ri.setForeground(QColor(col))
            si.setForeground(QColor(col))
            for it in (ri, si, fi):
                it.setFont(QFont("Consolas", 11))
            self._tbl.setItem(i, 0, ri)
            self._tbl.setItem(i, 1, si)
            self._tbl.setItem(i, 2, fi)
        hits = len([r for r in results if r.get("type") in ("YARA", "IOC")])
        self._status.setText(f"Найдено: {hits} | Всего записей: {len(results)}")

    def _on_scan_error(self, msg: str):
        self._status.setText(f"✘ Ошибка: {msg}")

    def _deploy(self):
        dlg = _DeployDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["username"]:
            QMessageBox.warning(self, "Ошибка", "IP и пользователь обязательны")
            return
        self._btn_deploy.setEnabled(False)
        self._prog.setVisible(True)
        self._status.setText("Деплой агента...")
        self._deploy_worker = DeployWorker(d["ip"], d["username"], d["password"])
        self._deploy_worker.progress.connect(self._status.setText)
        self._deploy_worker.error.connect(self._on_deploy_error)
        self._deploy_worker.done.connect(lambda tok: self._on_deploy_done(d["ip"], tok))
        self._deploy_worker.finished.connect(lambda: (
            self._btn_deploy.setEnabled(True), self._prog.setVisible(False)
        ))
        self._deploy_worker.start()

    def _on_deploy_done(self, ip: str, token: str):
        self._status.setText(f"✔ Агент задеплоен на {ip}. Токен получен.")
        QMessageBox.information(
            self, "Деплой завершён",
            f"Агент установлен на {ip}\n\nТокен:\n{token}\n\n"
            "Нажми '+ Добавить' и введи этот токен для добавления хоста.",
        )

    def _on_deploy_error(self, msg: str):
        self._status.setText(f"✘ Деплой: {msg}")
        QMessageBox.warning(self, "Ошибка деплоя", msg)
