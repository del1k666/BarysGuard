import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from workers.hunt_worker import HuntWorker
from ui.dashboard_tab import DashboardTab


class HuntTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        # Mutex search
        grp_mutex = QGroupBox("Mutex Search")
        ml = QHBoxLayout(grp_mutex)
        ml.addWidget(QLabel("Имя mutex:"))
        self._mutex_inp = QLineEdit()
        self._mutex_inp.setPlaceholderText("Global\\\\MyMalwareMutex")
        ml.addWidget(self._mutex_inp)
        self._btn_mutex = QPushButton("Искать")
        self._btn_mutex.setFixedWidth(90)
        self._btn_mutex.clicked.connect(self._hunt_mutex)
        ml.addWidget(self._btn_mutex)
        lay.addWidget(grp_mutex)

        # Hash search
        grp_hash = QGroupBox("Hash Search  (SHA256 / MD5)")
        hl = QVBoxLayout(grp_hash)
        hrow1 = QHBoxLayout()
        hrow1.addWidget(QLabel("Hash:"))
        self._hash_inp = QLineEdit()
        self._hash_inp.setPlaceholderText("sha256 или md5 хэш файла...")
        hrow1.addWidget(self._hash_inp)
        hl.addLayout(hrow1)
        hrow2 = QHBoxLayout()
        hrow2.addWidget(QLabel("Путь поиска:"))
        self._hash_path = QLineEdit("C:\\")
        hrow2.addWidget(self._hash_path)
        self._btn_hash = QPushButton("Искать")
        self._btn_hash.setFixedWidth(90)
        self._btn_hash.clicked.connect(self._hunt_hash)
        hrow2.addWidget(self._btn_hash)
        hl.addLayout(hrow2)
        lay.addWidget(grp_hash)

        # Process search
        grp_proc = QGroupBox("Process Search")
        pl = QHBoxLayout(grp_proc)
        pl.addWidget(QLabel("Имя процесса:"))
        self._proc_inp = QLineEdit()
        self._proc_inp.setPlaceholderText("svchost.exe")
        pl.addWidget(self._proc_inp)
        self._btn_proc = QPushButton("Искать")
        self._btn_proc.setFixedWidth(90)
        self._btn_proc.clicked.connect(self._hunt_proc)
        pl.addWidget(self._btn_proc)
        lay.addWidget(grp_proc)

        self._status = QLabel("Введи значение и нажми Искать")
        self._status.setStyleSheet("color:#6e7681;font-size:11px;")
        lay.addWidget(self._status)

        self._tbl = QTableWidget(0, 4)
        self._tbl.setHorizontalHeaderLabels(["Хост", "Тип", "Результат", "Время"])
        self._tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tbl.horizontalHeader().resizeSection(1, 90)
        self._tbl.horizontalHeader().resizeSection(2, 280)
        self._tbl.horizontalHeader().resizeSection(3, 70)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lay.addWidget(self._tbl)

    # ── Hunt triggers ──────────────────────────────────────────────────────────

    def _hunt(self, payload: dict):
        if self._worker and self._worker.isRunning():
            return
        self._tbl.setRowCount(0)
        self._set_buttons(False)
        self._status.setText("Поиск по хостам...")
        self._worker = HuntWorker(payload)
        self._worker.result.connect(self._on_result)
        self._worker.progress.connect(self._status.setText)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _hunt_mutex(self):
        name = self._mutex_inp.text().strip()
        if not name:
            self._status.setText("Введи имя mutex")
            return
        self._hunt({"mutex": name})

    def _hunt_hash(self):
        h = self._hash_inp.text().strip()
        if not h:
            self._status.setText("Введи хэш")
            return
        path = self._hash_path.text().strip() or "C:\\"
        self._hunt({"hashes": [h], "hash_path": path})

    def _hunt_proc(self):
        name = self._proc_inp.text().strip()
        if not name:
            self._status.setText("Введи имя процесса")
            return
        self._hunt({"process_name": name})

    # ── Result handling ────────────────────────────────────────────────────────

    def _on_result(self, host: str, data: dict):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if not data.get("_online", True):
            self._add_row(host, "STATUS", "OFFLINE", now, "#484f58")
            return

        if "mutex_found" in data:
            found = data["mutex_found"]
            color = "#f85149" if found else "#3fb950"
            label = "FOUND" if found else "NOT FOUND"
            self._add_row(host, "MUTEX", f"{data.get('mutex_name', '')} — {label}", now, color)
            if found:
                DashboardTab.log_event(
                    "HUNT", f"{host}: mutex {data.get('mutex_name', '')} найден", level="high")

        if "hash_matches" in data:
            if data["hash_matches"]:
                for m in data["hash_matches"]:
                    self._add_row(host, "HASH", m["file"], now, "#f85149")
                    DashboardTab.log_event(
                        "HUNT", f"{host}: hash found at {m['file']}", level="high")
            else:
                self._add_row(host, "HASH", "NOT FOUND", now, "#3fb950")

        if "process_matches" in data:
            if data["process_matches"]:
                for p in data["process_matches"]:
                    self._add_row(
                        host, "PROCESS", f"{p['name']} (PID {p['pid']})", now, "#d29922")
                    DashboardTab.log_event(
                        "HUNT", f"{host}: process {p['name']} PID {p['pid']}", level="high")
            else:
                self._add_row(host, "PROCESS", "NOT FOUND", now, "#3fb950")

    def _add_row(self, host: str, typ: str, result: str, time: str, color: str):
        row = self._tbl.rowCount()
        self._tbl.insertRow(row)
        for i, txt in enumerate([host, typ, result, time]):
            item = QTableWidgetItem(txt)
            item.setFont(QFont("Consolas", 11))
            if i in (1, 2):
                item.setForeground(QColor(color))
            self._tbl.setItem(row, i, item)

    def _on_done(self):
        self._set_buttons(True)
        self._status.setText(f"Готово — результатов: {self._tbl.rowCount()}")

    def _set_buttons(self, enabled: bool):
        for btn in (self._btn_mutex, self._btn_hash, self._btn_proc):
            btn.setEnabled(enabled)
