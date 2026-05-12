import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFrame, QLabel
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor


class DashboardTab(QWidget):
    # Shared storage — другие вкладки пишут сюда статистику
    stats = {
        "hash_lookups": 0, "malicious": 0, "clean": 0,
        "ioc_runs": 0, "suspicious_procs": 0,
        "yara_scans": 0, "yara_hits": 0,
        "net_checks": 0, "high_risk_ips": 0,
        "recent": []
    }

    def __init__(self):
        super().__init__()
        self._build()
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(3000)

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(16,16,16,16)

        # Top stat cards row
        cards_row = QHBoxLayout(); cards_row.setSpacing(10)
        self._c_hash    = self._stat_card("Hash Lookups",    "0", "#58a6ff")
        self._c_mal     = self._stat_card("Malicious",       "0", "#f85149")
        self._c_yara    = self._stat_card("YARA Hits",       "0", "#d29922")
        self._c_net     = self._stat_card("Net Checks",      "0", "#3fb950")
        self._c_susp    = self._stat_card("Suspicious Procs","0", "#d29922")
        self._c_highrisk= self._stat_card("High Risk IPs",   "0", "#f85149")
        for card in [self._c_hash, self._c_mal, self._c_yara,
                     self._c_net, self._c_susp, self._c_highrisk]:
            cards_row.addWidget(card[0])
        lay.addLayout(cards_row)

        # Middle row: activity log + mini chart
        mid = QHBoxLayout(); mid.setSpacing(10)

        grp_log = QGroupBox("Последние события")
        gl = QVBoxLayout(grp_log)
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setStyleSheet(
            "background:#0a0e14;border:1px solid #21262d;border-radius:6px;"
            "font-family:Consolas,monospace;font-size:12px;padding:8px;")
        gl.addWidget(self.log)
        mid.addWidget(grp_log, 3)

        grp_sum = QGroupBox("Сводка угроз")
        gs = QVBoxLayout(grp_sum); gs.setSpacing(8)
        self._bars = {}
        for label, color in [("Critical","#f85149"),("High","#d29922"),
                               ("Medium","#58a6ff"),("Low","#3fb950")]:
            row = QHBoxLayout()
            lbl = QLabel(label); lbl.setFixedWidth(60)
            lbl.setStyleSheet(f"color:{color};font-size:12px;font-weight:bold;")
            bar = QProgressBar(); bar.setRange(0, 100); bar.setValue(0)
            bar.setFixedHeight(14)
            bar.setStyleSheet(
                f"QProgressBar{{background:#21262d;border:none;border-radius:3px;}}"
                f"QProgressBar::chunk{{background:{color};border-radius:3px;}}")
            cnt = QLabel("0"); cnt.setFixedWidth(30)
            cnt.setStyleSheet("color:#6e7681;font-size:11px;")
            row.addWidget(lbl); row.addWidget(bar); row.addWidget(cnt)
            gs.addLayout(row)
            self._bars[label] = (bar, cnt)
        gs.addStretch()
        mid.addWidget(grp_sum, 1)
        lay.addLayout(mid)

        # Recent scans table
        grp_tbl = QGroupBox("Последние сканирования")
        gt = QVBoxLayout(grp_tbl)
        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["Время", "Тип", "Цель", "Результат"])
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setMaximumHeight(180)
        gt.addWidget(self.tbl)
        lay.addWidget(grp_tbl)

        grp_remote = QGroupBox("Удалённые сканы")
        gr_rem = QVBoxLayout(grp_remote)
        self.remote_tbl = QTableWidget(0, 4)
        self.remote_tbl.setHorizontalHeaderLabels(["Время", "Хост", "Тип", "Правило / Файл"])
        self.remote_tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.remote_tbl.horizontalHeader().resizeSection(0, 70)
        self.remote_tbl.horizontalHeader().resizeSection(1, 160)
        self.remote_tbl.horizontalHeader().resizeSection(2, 80)
        self.remote_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.remote_tbl.setMaximumHeight(180)
        gr_rem.addWidget(self.remote_tbl)
        lay.addWidget(grp_remote)

    def _stat_card(self, title, value, color):
        f = QFrame()
        f.setStyleSheet("QFrame{background:#161b22;border:1px solid #21262d;border-radius:8px;}")
        fl = QVBoxLayout(f); fl.setContentsMargins(12,10,12,10); fl.setSpacing(2)
        t = QLabel(title); t.setStyleSheet("color:#6e7681;font-size:10px;font-weight:bold;letter-spacing:1px;")
        v = QLabel(value); v.setStyleSheet(f"font-size:28px;font-weight:bold;color:{color};")
        fl.addWidget(t); fl.addWidget(v)
        return f, v

    def _refresh(self):
        s = DashboardTab.stats
        self._c_hash[1].setText(str(s["hash_lookups"]))
        self._c_mal[1].setText(str(s["malicious"]))
        self._c_yara[1].setText(str(s["yara_hits"]))
        self._c_net[1].setText(str(s["net_checks"]))
        self._c_susp[1].setText(str(s["suspicious_procs"]))
        self._c_highrisk[1].setText(str(s["high_risk_ips"]))

        # Recent events
        self.log.clear()
        for evt in reversed(s["recent"][-20:]):
            ts   = evt.get("time","")
            typ  = evt.get("type","")
            msg  = evt.get("msg","")
            lvl  = evt.get("level","info")
            col  = {"critical":"#f85149","high":"#d29922",
                    "info":"#8b949e","ok":"#3fb950"}.get(lvl,"#8b949e")
            self.log.append(
                f'<span style="color:#484f58">{ts}</span> '
                f'<span style="color:{col};font-weight:bold">[{typ}]</span> '
                f'<span style="color:#c9d1d9">{msg}</span>'
            )

        # Severity bars — count from recent
        counts = {"Critical":0,"High":0,"Medium":0,"Low":0}
        for evt in s["recent"]:
            sev = evt.get("severity","")
            if sev in counts:
                counts[sev] += 1
        total = max(sum(counts.values()), 1)
        for label,(bar,cnt) in self._bars.items():
            n = counts[label]
            bar.setValue(int(n/total*100))
            cnt.setText(str(n))

        # Remote scans table
        remote_events = [e for e in s["recent"] if e.get("host")]
        self.remote_tbl.setRowCount(0)
        rem_colors = {"YARA": "#58a6ff", "IOC": "#d29922",
                      "MEMORY": "#a371f7", "HASH": "#8b949e"}
        for evt in reversed(remote_events[-20:]):
            row = self.remote_tbl.rowCount()
            self.remote_tbl.insertRow(row)
            typ = evt.get("type", "")
            col = rem_colors.get(typ, "#8b949e")
            for i, txt in enumerate([
                evt.get("time", ""), evt.get("host", ""),
                typ, evt.get("msg", ""),
            ]):
                item = QTableWidgetItem(txt)
                item.setFont(QFont("Consolas", 11))
                if i in (2, 3):
                    item.setForeground(QColor(col))
                self.remote_tbl.setItem(row, i, item)

        # Recent table
        recent_scans = [e for e in s["recent"] if e.get("scan")]
        self.tbl.setRowCount(0)
        for evt in reversed(recent_scans[-10:]):
            row = self.tbl.rowCount()
            self.tbl.insertRow(row)
            lvl = evt.get("level","info")
            col = {"critical":"#f85149","high":"#d29922",
                   "ok":"#3fb950","info":"#8b949e"}.get(lvl,"#8b949e")
            for i, txt in enumerate([evt.get("time",""), evt.get("type",""),
                                      evt.get("target",""), evt.get("msg","")]):
                item = QTableWidgetItem(txt)
                item.setFont(QFont("Consolas",11))
                if i == 3:
                    item.setForeground(QColor(col))
                self.tbl.setItem(row, i, item)

    @staticmethod
    def log_event(type_, msg, level="info", severity="", target="", scan=False, host=""):
        import datetime
        DashboardTab.stats["recent"].append({
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "type": type_, "msg": msg, "level": level,
            "severity": severity, "target": target, "scan": scan, "host": host,
        })
        if len(DashboardTab.stats["recent"]) > 200:
            DashboardTab.stats["recent"] = DashboardTab.stats["recent"][-200:]
