import socket
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QDialog, QFormLayout,
    QDialogButtonBox, QMessageBox, QSpinBox, QTextEdit, QFrame, QSplitter,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

from core.hosts_config import load_hosts, add_host, remove_host, update_host
from workers.host_worker import PingWorker, DeployWorker, NetworkIsolationWorker
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

    def __init__(self, on_host_changed=None, on_hosts_list_changed=None):
        super().__init__()
        self._on_host_changed       = on_host_changed
        self._on_hosts_list_changed = on_hosts_list_changed
        self._selected_id: str | None = None
        self._ping_worker:   PingWorker | None = None
        self._deploy_worker: DeployWorker | None = None
        self._iso_worker:    NetworkIsolationWorker | None = None

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

        # ── LEFT: host list ───────────────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)

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
        self._btn_remove.setObjectName("dangerBtn")
        self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._remove_host)
        row_btns.addWidget(self._btn_add)
        row_btns.addWidget(self._btn_remove)
        ll.addLayout(row_btns)
        outer.addWidget(left)

        # ── RIGHT: status panel ───────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)

        self._info_label = QLabel(t("hosts_select_hint"))
        self._info_label.setStyleSheet(
            "color:#8b949e;font-size:12px;padding:6px 10px;"
            "background:#161b22;border:1px solid #21262d;border-radius:6px;")
        self._info_label.setWordWrap(True)
        rl.addWidget(self._info_label)

        self._status_panel = self._build_status_panel()
        self._status_panel.setEnabled(False)
        rl.addWidget(self._status_panel, 1)

        outer.addWidget(right)
        outer.setSizes([250, 900])
        lay.addWidget(outer)

    def _build_status_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        # ── Host info card ────────────────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet(
            "QFrame{background:#161b22;border:1px solid #21262d;border-radius:8px;}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(8)
        self._st_name = QLabel("—")
        self._st_name.setStyleSheet("font-size:18px;font-weight:bold;color:#58a6ff;")
        cl.addWidget(self._st_name)
        self._st_addr   = self._detail_row(cl, "Адрес")
        self._st_seen   = self._detail_row(cl, "Последний пинг")
        self._st_scan   = self._detail_row(cl, "Последний скан")
        self._st_status = self._detail_row(cl, "Статус")
        lay.addWidget(card)

        # ── Action buttons ────────────────────────────────────────────────────
        grp_act = QGroupBox("Действия с хостом")
        ga = QHBoxLayout(grp_act)
        ga.setSpacing(8)
        self._btn_ping = QPushButton("⟳  Пинговать")
        self._btn_ping.setObjectName("secondaryBtn")
        self._btn_ping.setFixedHeight(36)
        self._btn_ping.clicked.connect(self._ping_selected)
        self._btn_deploy = QPushButton("⚙  Развернуть агент")
        self._btn_deploy.setObjectName("secondaryBtn")
        self._btn_deploy.setFixedHeight(36)
        self._btn_deploy.clicked.connect(self._deploy)
        ga.addWidget(self._btn_ping)
        ga.addWidget(self._btn_deploy)
        ga.addStretch()
        lay.addWidget(grp_act)

        # ── Network isolation ─────────────────────────────────────────────────
        warn = QLabel(
            "⚠  Изоляция заблокирует весь трафик хоста через Windows Firewall.\n"
            "Убедитесь что ваш IP-адрес указан ниже — иначе потеряете доступ к агенту.")
        warn.setWordWrap(True)
        warn.setStyleSheet(
            "color:#d29922;font-size:11px;padding:8px 10px;"
            "background:#2d2208;border:1px solid #4d3800;border-radius:6px;")
        lay.addWidget(warn)

        self._iso_status_card = QFrame()
        self._iso_status_card.setStyleSheet(
            "QFrame{background:#161b22;border:1px solid #21262d;border-radius:8px;}")
        sc = QHBoxLayout(self._iso_status_card)
        sc.setContentsMargins(14, 10, 14, 10)
        self._iso_status_icon = QLabel("●")
        self._iso_status_icon.setStyleSheet("font-size:20px;color:#6e7681;")
        self._iso_status_text = QLabel("Статус неизвестен")
        self._iso_status_text.setStyleSheet(
            "font-size:13px;font-weight:bold;color:#8b949e;")
        sc.addWidget(self._iso_status_icon)
        sc.addWidget(self._iso_status_text)
        sc.addStretch()
        btn_check = QPushButton("⟳ Проверить")
        btn_check.setObjectName("secondaryBtn")
        btn_check.setFixedHeight(30)
        btn_check.clicked.connect(self._check_isolation_status)
        sc.addWidget(btn_check)
        lay.addWidget(self._iso_status_card)

        grp_ip = QGroupBox("Управляющий IP (будет разрешён через firewall)")
        gi = QHBoxLayout(grp_ip)
        self._iso_mgmt_ip = QLineEdit()
        self._iso_mgmt_ip.setPlaceholderText("192.168.1.X — ваш IP-адрес")
        self._iso_mgmt_ip.setText(_local_ip())
        gi.addWidget(self._iso_mgmt_ip)
        lay.addWidget(grp_ip)

        iso_btn_row = QHBoxLayout()
        iso_btn_row.setSpacing(10)
        self._btn_isolate = QPushButton("🔒  Изолировать хост")
        self._btn_isolate.setObjectName("dangerBtn")
        self._btn_isolate.setFixedHeight(38)
        self._btn_isolate.clicked.connect(self._isolate_host)
        self._btn_restore = QPushButton("🔓  Восстановить сеть")
        self._btn_restore.setObjectName("secondaryBtn")
        self._btn_restore.setFixedHeight(38)
        self._btn_restore.clicked.connect(self._restore_host)
        iso_btn_row.addWidget(self._btn_isolate)
        iso_btn_row.addWidget(self._btn_restore)
        lay.addLayout(iso_btn_row)

        # ── Action log ────────────────────────────────────────────────────────
        grp_log = QGroupBox("Журнал действий")
        gl = QVBoxLayout(grp_log)
        self._action_log = QTextEdit()
        self._action_log.setReadOnly(True)
        self._action_log.setStyleSheet(
            "background:#0a0e14;border:1px solid #21262d;border-radius:6px;"
            "font-family:Consolas,monospace;font-size:11px;color:#c9d1d9;padding:6px;")
        gl.addWidget(self._action_log)
        lay.addWidget(grp_log, 1)

        return w

    def _detail_row(self, parent_layout, label: str) -> QLabel:
        row = QHBoxLayout()
        lbl = QLabel(label + ":"); lbl.setFixedWidth(130)
        lbl.setStyleSheet("color:#6e7681;font-size:12px;")
        val = QLabel("—"); val.setStyleSheet("color:#e6edf3;font-size:12px;")
        row.addWidget(lbl); row.addWidget(val); row.addStretch()
        parent_layout.addLayout(row)
        return val

    def _log(self, msg: str, color: str = "#8b949e"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._action_log.append(
            f'<span style="color:#484f58">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>')

    # ── Host list management ──────────────────────────────────────────────────

    def _reload_hosts(self):
        self._host_list.clear()
        hosts = load_hosts()
        self._lbl_count.setText(t("hosts_count", n=len(hosts)))
        for h in hosts:
            item = QListWidgetItem(f"🖥  {h['name']}\n{h['ip']}:{h['port']}")
            item.setData(Qt.ItemDataRole.UserRole, h)
            self._host_list.addItem(item)

    def _on_host_select(self, row: int):
        if row < 0:
            self._selected_id = None
            self._btn_remove.setEnabled(False)
            self._status_panel.setEnabled(False)
            self._info_label.setText(t("hosts_select_hint"))
            return

        host = self._host_list.item(row).data(Qt.ItemDataRole.UserRole)
        self._selected_id = host["id"]
        self._btn_remove.setEnabled(True)
        self._status_panel.setEnabled(True)

        seen = host.get("last_seen") or "никогда"
        scan = host.get("last_scan") or "никогда"
        self._info_label.setText(
            f"<b style='color:#58a6ff'>{host['name']}</b>"
            f"  ·  <span style='color:#8b949e'>{host['ip']}:{host['port']}</span>"
            f"  ·  ping: {seen}  ·  скан: {scan}")
        self._update_status_card(host)
        if self._on_host_changed:
            self._on_host_changed(host)

    def _update_status_card(self, host: dict):
        self._st_name.setText(host.get("name", "—"))
        self._st_addr.setText(f"{host.get('ip','—')}:{host.get('port','—')}")
        self._st_seen.setText(host.get("last_seen") or "никогда")
        self._st_scan.setText(host.get("last_scan") or "никогда")
        self._st_status.setText("⟳ Статус неизвестен")
        self._iso_status_icon.setStyleSheet("font-size:20px;color:#6e7681;")
        self._iso_status_text.setText("Статус неизвестен")
        self._iso_status_card.setStyleSheet(
            "QFrame{background:#161b22;border:1px solid #21262d;border-radius:8px;}")

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

    def retranslate(self, _lang: str = ""):
        self._btn_add.setText(t("hosts_add_btn"))
        self._btn_remove.setText(t("hosts_remove_btn"))
        if self._info_label.text() in (t("hosts_select_hint"),
                                        "Выбери хост слева", "Select a host on the left",
                                        "Сол жақтан хостты таңдаңыз"):
            self._info_label.setText(t("hosts_select_hint"))
        self._reload_hosts()

    def _get_selected_host(self) -> dict | None:
        for i in range(self._host_list.count()):
            h = self._host_list.item(i).data(Qt.ItemDataRole.UserRole)
            if h["id"] == self._selected_id:
                return h
        return None

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
                    "<span style='color:#3fb950'>● Online</span>" if online
                    else "<span style='color:#f85149'>✗ Offline</span>")
                scan = h.get("last_scan") or "никогда"
                self._info_label.setText(
                    f"<b style='color:#58a6ff'>{h['name']}</b>"
                    f"  ·  <span style='color:#8b949e'>{h['ip']}:{h['port']}</span>"
                    f"  ·  ping: {ping_str}  ·  скан: {scan}")
            break

    # ── Deploy ────────────────────────────────────────────────────────────────

    def _deploy(self):
        dlg = _DeployDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        if not d["ip"] or not d["username"]:
            QMessageBox.warning(self, t("error"), t("hosts_deploy_required"))
            return
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
        self._iso_status_icon.setStyleSheet("font-size:20px;color:#6e7681;")
        self._iso_worker = NetworkIsolationWorker(host, "status")
        self._iso_worker.done.connect(self._on_iso_status)
        self._iso_worker.error.connect(lambda e: (
            self._iso_status_text.setText(f"✘ {e[:60]}"),
            self._log(f"✘ Ошибка проверки: {e}", "#f85149")))
        self._iso_worker.start()

    def _on_iso_status(self, data: dict):
        isolated = data.get("isolated", False)
        if isolated:
            self._iso_status_icon.setStyleSheet("font-size:20px;color:#f85149;")
            self._iso_status_text.setText(
                "<span style='color:#f85149;font-weight:bold'>🔴  ИЗОЛИРОВАН</span>")
            self._iso_status_card.setStyleSheet(
                "QFrame{background:#2d0f0f;border:1px solid #6e1212;border-radius:8px;}")
        else:
            self._iso_status_icon.setStyleSheet("font-size:20px;color:#3fb950;")
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
                "Укажите управляющий IP-адрес, иначе потеряете доступ к агенту.")
            return
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
        self._log(
            f"▶ Изоляция {host['name']} ({host['ip']}) | mgmt: {mgmt_ip}", "#d29922")
        DashboardTab.log_event("ISOLATE", f"Изоляция {host['name']} ({host['ip']})",
            level="critical", severity="Critical",
            host=f"{host['name']} ({host['ip']})")

        self._iso_worker = NetworkIsolationWorker(host, "isolate", mgmt_ip)
        self._iso_worker.done.connect(self._on_isolate_done)
        self._iso_worker.error.connect(lambda e: (
            self._log(f"✘ Ошибка изоляции: {e}", "#f85149"),
            self._btn_isolate.setEnabled(True)))
        self._iso_worker.start()

    def _on_isolate_done(self, data: dict):
        self._btn_isolate.setEnabled(True)
        if data.get("status") == "isolated":
            self._log("✓ Хост изолирован от сети", "#d29922")
            self._on_iso_status({"isolated": True})
        else:
            errs = "; ".join(data.get("errors", [str(data)]))
            self._log(f"✘ Ошибка: {errs}", "#f85149")

    def _restore_host(self):
        host = self._get_selected_host()
        if not host:
            return
        self._btn_restore.setEnabled(False)
        self._log(f"▶ Восстановление сети {host['name']} ({host['ip']})", "#58a6ff")
        DashboardTab.log_event("RESTORE", f"Восстановление сети {host['name']}",
            level="info", host=f"{host['name']} ({host['ip']})")

        self._iso_worker = NetworkIsolationWorker(host, "restore")
        self._iso_worker.done.connect(self._on_restore_done)
        self._iso_worker.error.connect(lambda e: (
            self._log(f"✘ Ошибка: {e}", "#f85149"),
            self._btn_restore.setEnabled(True)))
        self._iso_worker.start()

    def _on_restore_done(self, data: dict):
        self._btn_restore.setEnabled(True)
        if data.get("status") == "restored":
            self._log("✓ Сеть восстановлена", "#3fb950")
            self._on_iso_status({"isolated": False})
        else:
            self._log(f"✘ Ошибка: {data}", "#f85149")
