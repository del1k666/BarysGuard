import os
import re
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QFrame, QListWidget, QListWidgetItem,
    QCheckBox, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from config import Config, RESULTS_DIR
from constants import BUILTIN_YARA_RULES
from core.yara_engine import YARA_PYTHON_AVAILABLE
from workers.yara_worker import YARAWorker
from ui.dashboard_tab import DashboardTab


class YARATab(QWidget):
    def __init__(self):
        super().__init__(); self._build(); self._custom_rules={}

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(16,16,16,16)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: rule selector
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(6)

        grp_r = QGroupBox("Встроенные правила")
        gr    = QVBoxLayout(grp_r)
        self.rule_list = QListWidget(); self.rule_list.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection)
        for name in BUILTIN_YARA_RULES:
            item = QListWidgetItem(name)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.rule_list.addItem(item)
        self.chk_all = QCheckBox("Выбрать все"); self.chk_all.clicked.connect(self._toggle_all)
        gr.addWidget(self.chk_all)
        gr.addWidget(self.rule_list)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Загрузить .yar")
        self.btn_add.setObjectName("secondaryBtn"); self.btn_add.clicked.connect(self._load_yar)
        btn_row.addWidget(self.btn_add)
        gr.addLayout(btn_row); ll.addWidget(grp_r)

        splitter.addWidget(left)

        # Right: scan target + results
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)

        grp_t = QGroupBox("Цель сканирования")
        gt    = QVBoxLayout(grp_t)

        tr = QHBoxLayout()
        self.target_inp = QLineEdit(); self.target_inp.setPlaceholderText("Выберите файл или папку для сканирования...")
        tr.addWidget(self.target_inp)
        btn_tf = QPushButton("Файл"); btn_tf.setObjectName("secondaryBtn"); btn_tf.setFixedWidth(60)
        btn_tf.clicked.connect(self._browse_file); tr.addWidget(btn_tf)
        btn_td = QPushButton("Папка"); btn_td.setObjectName("secondaryBtn"); btn_td.setFixedWidth(60)
        btn_td.clicked.connect(self._browse_dir); tr.addWidget(btn_td)
        gt.addLayout(tr)
        rl.addWidget(grp_t)

        scan_row = QHBoxLayout()
        self.btn_scan = QPushButton("Сканировать YARA"); self.btn_scan.setFixedHeight(36)
        self.btn_scan.clicked.connect(self._scan); scan_row.addWidget(self.btn_scan)
        self.btn_edit = QPushButton("Редактор правил"); self.btn_edit.setObjectName("accentBtn")
        self.btn_edit.setFixedWidth(150); self.btn_edit.clicked.connect(self._open_editor)
        scan_row.addWidget(self.btn_edit)
        rl.addLayout(scan_row)

        self.prog = QProgressBar(); self.prog.setRange(0,0); self.prog.setVisible(False)
        self.prog.setFixedHeight(5); rl.addWidget(self.prog)

        # Results table
        grp_res = QGroupBox("Результаты")
        gr2     = QVBoxLayout(grp_res)
        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["Правило", "Severity", "Файл"])
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().resizeSection(0, 180)
        self.tbl.horizontalHeader().resizeSection(1, 80)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        gr2.addWidget(self.tbl)

        self.scan_status = QLabel("Готов к сканированию")
        self.scan_status.setStyleSheet("color:#8b949e;font-size:11px;")
        gr2.addWidget(self.scan_status)
        rl.addWidget(grp_res)

        splitter.addWidget(right)
        splitter.setSizes([220, 500])
        lay.addWidget(splitter)

        # Editor widget (hidden by default)
        self.editor_frame = QFrame()
        self.editor_frame.setVisible(False)
        ef = QVBoxLayout(self.editor_frame)
        ef.addWidget(QLabel("Редактор YARA правил:"))
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            'rule MyRule {\n    meta:\n        description = "..."\n    strings:\n        $s1 = "evil" ascii\n    condition:\n        $s1\n}')
        ef.addWidget(self.editor)
        er = QHBoxLayout()
        btn_s = QPushButton("Сохранить правило"); btn_s.clicked.connect(self._save_rule)
        btn_c = QPushButton("Закрыть"); btn_c.setObjectName("secondaryBtn")
        btn_c.clicked.connect(lambda: self.editor_frame.setVisible(False))
        er.addWidget(btn_s); er.addWidget(btn_c)
        ef.addLayout(er)
        lay.addWidget(self.editor_frame)

    def _toggle_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.rule_list.count()):
            self.rule_list.item(i).setCheckState(state)

    def _load_yar(self):
        paths, _ = QFileDialog.getOpenFileNames(self,"Загрузить .yar правила","","YARA (*.yar *.yara);;All (*)")
        for p in paths:
            name = Path(p).stem
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            self._custom_rules[name] = content
            item = QListWidgetItem(f"📄 {name} [custom]")
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, content)
            self.rule_list.addItem(item)

    def _browse_file(self):
        p, _ = QFileDialog.getOpenFileName(self,"Выбери файл")
        if p: self.target_inp.setText(p)

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self,"Выбери папку")
        if d: self.target_inp.setText(d)

    def _get_selected_rules(self):
        """Возвращает dict {name: rule_text} для выбранных правил."""
        selected = {}
        for i in range(self.rule_list.count()):
            item = self.rule_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                raw_name   = item.text().replace("📄 ", "").split(" [custom]")[0].strip()
                custom_data = item.data(Qt.ItemDataRole.UserRole)
                if custom_data:
                    selected[raw_name] = custom_data
                elif raw_name in BUILTIN_YARA_RULES:
                    selected[raw_name] = BUILTIN_YARA_RULES[raw_name]
        return selected

    def _scan(self):
        target = self.target_inp.text().strip()
        if not target:
            self.scan_status.setText("⚠ Укажи путь к файлу или папке"); return
        if not os.path.exists(target):
            self.scan_status.setText("⚠ Путь не существует"); return
        rules = self._get_selected_rules()
        if not rules:
            self.scan_status.setText("Выбери хотя бы одно правило"); return

        self.btn_scan.setEnabled(False)
        self.prog.setVisible(True)
        self.tbl.setRowCount(0)
        self.scan_status.setText("Сканирование...")

        self._w = YARAWorker(rules, target, str(RESULTS_DIR))
        self.scan_status.setText(f"Сканирование... правил: {len(rules)}, движок: {'yara-python' if YARA_PYTHON_AVAILABLE else 'yara64.exe'}")
        self._w.done.connect(self._on_scan_done)
        self._w.error.connect(self._on_scan_error)
        self._w.finished.connect(lambda: (self.btn_scan.setEnabled(True), self.prog.setVisible(False)))
        self._w.start()

    def _on_scan_done(self, matches):
        # Строим severity_map из встроенных правил
        severity_map = {}
        for rule_text in BUILTIN_YARA_RULES.values():
            m = re.search(r'severity\s*=\s*"(\w+)"', rule_text)
            rn = re.search(r'rule\s+(\w+)', rule_text)
            if m and rn:
                severity_map[rn.group(1)] = m.group(1)

        colors = {
            "critical": "#f85149", "high": "#d29922",
            "medium": "#58a6ff",   "low":  "#3fb950",
            "info":   "#8b949e",   "ERROR":"#f85149",
            "COMPILE_ERR":"#d29922", "WARN":"#d29922",
            "TIMEOUT":"#8b949e",   "INFO": "#8b949e",
            "DEBUG":  "#484f58",
        }

        self.tbl.setRowCount(len(matches))
        real_hits = []
        for i, match in enumerate(matches):
            rule  = match.get("rule", "?")
            fpath = match.get("file", "?")
            sev   = severity_map.get(rule, rule.lower() if rule in colors else "info")
            col   = colors.get(sev, colors.get(rule, "#8b949e"))

            ri = QTableWidgetItem(rule)
            si = QTableWidgetItem(sev.upper() if sev not in colors else sev)
            fi = QTableWidgetItem(fpath)
            si.setForeground(QColor(col))
            ri.setForeground(QColor(col))
            for itm in (ri, si, fi):
                itm.setFont(QFont("Consolas", 11))
            self.tbl.setItem(i, 0, ri)
            self.tbl.setItem(i, 1, si)
            self.tbl.setItem(i, 2, fi)

            if rule not in ("ERROR","TIMEOUT","INFO","COMPILE_ERR","WARN","DEBUG"):
                real_hits.append(match)

        if not matches:
            self.scan_status.setText("Чисто — совпадений не найдено")
        elif real_hits:
            self.scan_status.setText(f"Найдено совпадений: {len(real_hits)}")
            DashboardTab.stats["yara_scans"] += 1
            DashboardTab.stats["yara_hits"] += len(real_hits)
            for h in real_hits:
                sev_val = severity_map.get(h.get("rule",""), "Medium")
                lvl = {"critical":"critical","high":"high","medium":"info"}.get(sev_val.lower(),"info")
                DashboardTab.log_event("YARA", f"{h.get('rule','?')} → {Path(h.get('file','?')).name}",
                    level=lvl, severity=sev_val.capitalize(),
                    scan=True, target=h.get("file","?"))
        else:
            # Только ошибки/инфо
            first = matches[0]
            if first["rule"] == "INFO":
                self.scan_status.setText(first["file"].split("\n")[0])
            elif first["rule"] == "COMPILE_ERR":
                self.scan_status.setText(f"Ошибка компиляции: {first['file'][:80]}")
            else:
                self.scan_status.setText("Чисто — совпадений не найдено")

    def _on_scan_error(self, msg):
        self.scan_status.setText(f"✘ Ошибка: {msg}")

    def _open_editor(self):
        self.editor_frame.setVisible(not self.editor_frame.isVisible())

    def _save_rule(self):
        text = self.editor.toPlainText().strip()
        if not text: return
        m = re.search(r'rule\s+(\w+)', text)
        name = m.group(1) if m else f"CustomRule_{len(self._custom_rules)+1}"
        self._custom_rules[name] = text
        item = QListWidgetItem(f"📄 {name} [custom]")
        item.setCheckState(Qt.CheckState.Checked)
        item.setData(Qt.ItemDataRole.UserRole, text)
        self.rule_list.addItem(item)
        self.editor_frame.setVisible(False)
        self.editor.clear()
