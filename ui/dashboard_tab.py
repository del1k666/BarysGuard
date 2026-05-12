import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFrame, QLabel, QTabWidget, QPushButton,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor


class DashboardTab(QWidget):
    stats = {
        "hash_lookups": 0, "malicious": 0, "clean": 0,
        "ioc_runs": 0, "suspicious_procs": 0,
        "yara_scans": 0, "yara_hits": 0,
        "net_checks": 0, "high_risk_ips": 0,
        "recent": [],
    }

    def __init__(self):
        super().__init__()
        self._build()
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(3000)

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        # ── Stat cards row ────────────────────────────────────────────
        cards = QHBoxLayout()
        cards.setSpacing(8)
        self._c_hash     = self._stat_card("Hash Lookups",     "0", "#58a6ff")
        self._c_mal      = self._stat_card("Malicious",        "0", "#f85149")
        self._c_yara     = self._stat_card("YARA Hits",        "0", "#d29922")
        self._c_net      = self._stat_card("Net Checks",       "0", "#3fb950")
        self._c_susp     = self._stat_card("Suspicious Procs", "0", "#d29922")
        self._c_highrisk = self._stat_card("High Risk IPs",    "0", "#f85149")
        for card in [self._c_hash, self._c_mal, self._c_yara,
                     self._c_net, self._c_susp, self._c_highrisk]:
            cards.addWidget(card[0])
        lay.addLayout(cards)

        # ── Sub-tabs ──────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabBar::tab{padding:8px 20px;font-size:12px;}"
            "QTabBar::tab:selected{font-weight:bold;}"
        )
        self._tabs.addTab(self._build_overview_tab(),  "📊  Обзор")
        self._tabs.addTab(self._build_events_tab(),    "📝  События")
        self._tabs.addTab(self._build_scans_tab(),     "📋  Сканирования")
        self._tabs.addTab(self._build_remote_tab(),    "🌐  Удалённые")
        lay.addWidget(self._tabs)

    # ── Tab: Overview ─────────────────────────────────────────────────────

    def _build_overview_tab(self) -> QWidget:
        w   = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(14)

        # Left — threat severity bars
        grp_sev = QGroupBox("Сводка угроз")
        gs = QVBoxLayout(grp_sev)
        gs.setSpacing(12)
        self._bars = {}
        for label, color in [
            ("Critical", "#f85149"), ("High",   "#d29922"),
            ("Medium",   "#58a6ff"), ("Low",    "#3fb950"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(65)
            lbl.setStyleSheet(
                f"color:{color};font-size:12px;font-weight:bold;")
            bar = QProgressBar()
            bar.setRange(0, 100); bar.setValue(0)
            bar.setFixedHeight(16)
            bar.setStyleSheet(
                f"QProgressBar{{background:#21262d;border:none;border-radius:4px;}}"
                f"QProgressBar::chunk{{background:{color};border-radius:4px;}}")
            cnt = QLabel("0")
            cnt.setFixedWidth(35)
            cnt.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cnt.setStyleSheet(
                "color:#6e7681;font-size:12px;font-weight:bold;")
            row.addWidget(lbl); row.addWidget(bar); row.addWidget(cnt)
            gs.addLayout(row)
            self._bars[label] = (bar, cnt)
        gs.addStretch()

        # Right — quick event preview (last 10)
        grp_quick = QGroupBox("Последние события")
        gq = QVBoxLayout(grp_quick)
        self._quick_log = QTextEdit()
        self._quick_log.setReadOnly(True)
        self._quick_log.setStyleSheet(
            "background:#0a0e14;border:1px solid #21262d;border-radius:6px;"
            "font-family:Consolas,monospace;font-size:12px;padding:8px;"
        )
        gq.addWidget(self._quick_log)

        lay.addWidget(grp_sev,   1)
        lay.addWidget(grp_quick, 2)
        return w

    # ── Tab: Events ───────────────────────────────────────────────────────

    def _build_events_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(6)

        top = QHBoxLayout()
        self._lbl_event_count = QLabel("0 событий")
        self._lbl_event_count.setStyleSheet("color:#6e7681;font-size:11px;")
        btn_clear = QPushButton("Очистить журнал")
        btn_clear.setObjectName("secondaryBtn")
        btn_clear.setFixedHeight(26)
        btn_clear.clicked.connect(self._clear_events)
        top.addWidget(self._lbl_event_count)
        top.addStretch()
        top.addWidget(btn_clear)
        lay.addLayout(top)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(
            "background:#0a0e14;border:1px solid #21262d;border-radius:6px;"
            "font-family:Consolas,monospace;font-size:12px;padding:8px;"
        )
        lay.addWidget(self.log)
        return w

    # ── Tab: Local scans ──────────────────────────────────────────────────

    def _build_scans_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(6)

        self._lbl_scans_count = QLabel("0 записей")
        self._lbl_scans_count.setStyleSheet("color:#6e7681;font-size:11px;")
        lay.addWidget(self._lbl_scans_count)

        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["Время", "Тип", "Цель", "Результат"])
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().resizeSection(0, 75)
        self.tbl.horizontalHeader().resizeSection(1, 60)
        self.tbl.horizontalHeader().resizeSection(2, 200)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setStyleSheet("QTableWidget{alternate-background-color:#0f1318;}")
        lay.addWidget(self.tbl)
        return w

    # ── Tab: Remote scans ─────────────────────────────────────────────────

    def _build_remote_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(6)

        self._lbl_remote_count = QLabel("0 записей")
        self._lbl_remote_count.setStyleSheet("color:#6e7681;font-size:11px;")
        lay.addWidget(self._lbl_remote_count)

        self.remote_tbl = QTableWidget(0, 4)
        self.remote_tbl.setHorizontalHeaderLabels(
            ["Время", "Хост", "Тип", "Правило / Файл"])
        self.remote_tbl.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        self.remote_tbl.horizontalHeader().resizeSection(0, 85)
        self.remote_tbl.horizontalHeader().resizeSection(1, 190)
        self.remote_tbl.horizontalHeader().resizeSection(2, 70)
        self.remote_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.remote_tbl.setAlternatingRowColors(True)
        self.remote_tbl.setStyleSheet(
            "QTableWidget{alternate-background-color:#0f1318;}")
        lay.addWidget(self.remote_tbl)
        return w

    # ── Stat card ─────────────────────────────────────────────────────────

    def _stat_card(self, title, value, color):
        f = QFrame()
        f.setStyleSheet(
            "QFrame{background:#161b22;border:1px solid #21262d;border-radius:8px;}")
        fl = QVBoxLayout(f)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(
            "color:#6e7681;font-size:10px;font-weight:bold;letter-spacing:1px;")
        v = QLabel(value)
        v.setStyleSheet(f"font-size:28px;font-weight:bold;color:{color};")
        fl.addWidget(t); fl.addWidget(v)
        return f, v

    # ── Refresh ───────────────────────────────────────────────────────────

    def _refresh(self):
        s      = DashboardTab.stats
        recent = s["recent"]

        # Stat cards
        self._c_hash[1].setText(str(s["hash_lookups"]))
        self._c_mal[1].setText(str(s["malicious"]))
        self._c_yara[1].setText(str(s["yara_hits"]))
        self._c_net[1].setText(str(s["net_checks"]))
        self._c_susp[1].setText(str(s["suspicious_procs"]))
        self._c_highrisk[1].setText(str(s["high_risk_ips"]))

        col_map = {"critical": "#f85149", "high": "#d29922",
                   "info": "#8b949e", "ok": "#3fb950"}

        # ── Tab 1: Overview — quick log (last 10) ─────────────────────
        self._quick_log.clear()
        for evt in reversed(recent[-10:]):
            col = col_map.get(evt.get("level", "info"), "#8b949e")
            self._quick_log.append(
                f'<span style="color:#484f58">{evt.get("time","")}</span> '
                f'<span style="color:{col};font-weight:bold">[{evt.get("type","")}]</span> '
                f'<span style="color:#c9d1d9">{evt.get("msg","")}</span>'
            )

        # Severity bars
        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for evt in recent:
            sev = evt.get("severity", "")
            if sev in counts:
                counts[sev] += 1
        total = max(sum(counts.values()), 1)
        for label, (bar, cnt) in self._bars.items():
            n = counts[label]
            bar.setValue(int(n / total * 100))
            cnt.setText(str(n))

        # ── Tab 2: Events — full log ──────────────────────────────────
        n_events = len(recent)
        self._lbl_event_count.setText(f"{n_events} событий")
        self.log.clear()
        for evt in reversed(recent[-100:]):
            col = col_map.get(evt.get("level", "info"), "#8b949e")
            self.log.append(
                f'<span style="color:#484f58">{evt.get("time","")}</span> '
                f'<span style="color:{col};font-weight:bold">[{evt.get("type","")}]</span> '
                f'<span style="color:#c9d1d9">{evt.get("msg","")}</span>'
            )

        # ── Tab 3: Local scans ────────────────────────────────────────
        scans = [e for e in recent if e.get("scan") and not e.get("host")]
        n_scans = len(scans)
        self._lbl_scans_count.setText(f"{n_scans} записей")
        self.tbl.setRowCount(0)
        for evt in reversed(scans[-50:]):
            row = self.tbl.rowCount()
            self.tbl.insertRow(row)
            col = col_map.get(evt.get("level", "info"), "#8b949e")
            for i, txt in enumerate([
                evt.get("time", ""), evt.get("type", ""),
                evt.get("target", ""), evt.get("msg", ""),
            ]):
                item = QTableWidgetItem(txt)
                item.setFont(QFont("Consolas", 11))
                if i == 3:
                    item.setForeground(QColor(col))
                self.tbl.setItem(row, i, item)

        # ── Tab 4: Remote scans ───────────────────────────────────────
        remote = [e for e in recent if e.get("host")]
        n_remote = len(remote)
        self._lbl_remote_count.setText(f"{n_remote} записей")
        self.remote_tbl.setRowCount(0)
        rem_col = {"YARA": "#58a6ff", "IOC": "#d29922",
                   "MEMORY": "#a371f7", "HASH": "#8b949e"}
        for evt in reversed(remote[-100:]):
            row = self.remote_tbl.rowCount()
            self.remote_tbl.insertRow(row)
            typ = evt.get("type", "")
            col = rem_col.get(typ, "#8b949e")
            for i, txt in enumerate([
                evt.get("time", ""), evt.get("host", ""),
                typ, evt.get("msg", ""),
            ]):
                item = QTableWidgetItem(txt)
                item.setFont(QFont("Consolas", 11))
                if i in (2, 3):
                    item.setForeground(QColor(col))
                self.remote_tbl.setItem(row, i, item)

        # Tab badges
        self._tabs.setTabText(
            1, f"📝  События ({n_events})" if n_events else "📝  События")
        self._tabs.setTabText(
            2, f"📋  Сканирования ({n_scans})" if n_scans else "📋  Сканирования")
        self._tabs.setTabText(
            3, f"🌐  Удалённые ({n_remote})" if n_remote else "🌐  Удалённые")

    def _clear_events(self):
        DashboardTab.stats["recent"] = []
        self.log.clear()
        self._quick_log.clear()
        self._lbl_event_count.setText("0 событий")
        for label, (bar, cnt) in self._bars.items():
            bar.setValue(0); cnt.setText("0")
        self._tabs.setTabText(1, "📝  События")
        self._tabs.setTabText(2, "📋  Сканирования")
        self._tabs.setTabText(3, "🌐  Удалённые")

    @staticmethod
    def log_event(type_, msg, level="info", severity="",
                  target="", scan=False, host=""):
        DashboardTab.stats["recent"].append({
            "time":     datetime.datetime.now().strftime("%H:%M:%S"),
            "type":     type_,
            "msg":      msg,
            "level":    level,
            "severity": severity,
            "target":   target,
            "scan":     scan,
            "host":     host,
        })
        if len(DashboardTab.stats["recent"]) > 500:
            DashboardTab.stats["recent"] = DashboardTab.stats["recent"][-500:]
