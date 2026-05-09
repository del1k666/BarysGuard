import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QFileDialog, QScrollArea, QMessageBox, QCheckBox
)
from PyQt6.QtCore import QTimer
from config import Config


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build()
        self._load()

    def _build(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        container = QWidget()
        lay = QVBoxLayout(container); lay.setSpacing(14); lay.setContentsMargins(20,16,20,16)

        # API ключи
        grp_api = QGroupBox("API ключи")
        ga = QVBoxLayout(grp_api); ga.setSpacing(10)

        self.vt_inp = self._key_field(ga, "VirusTotal API Key", "vt_api_key",
            "Получи бесплатно: virustotal.com/gui/my-apikey  (4 запроса/мин)")
        self.abuse_inp = self._key_field(ga, "AbuseIPDB API Key", "abuseipdb_key",
            "Получи: abuseipdb.com/api  (1000 запросов/день бесплатно)")
        self.groq_inp = self._key_field(ga, "Groq API Key", "groq_key",
            "Бесплатно: console.groq.com  (без карты)")
        self.claude_inp = self._key_field(ga, "Claude API Key", "claude_key",
            "Платно: console.anthropic.com")
        lay.addWidget(grp_api)

        # Папки
        grp_dir = QGroupBox("Папки по умолчанию")
        gd = QVBoxLayout(grp_dir); gd.setSpacing(8)
        self.results_inp = self._dir_field(gd, "Папка результатов IOC сбора", "results_dir")
        self.quar_inp    = self._dir_field(gd, "Папка карантина",            "quarantine_dir")
        lay.addWidget(grp_dir)

        # Прочее
        grp_misc = QGroupBox("Параметры работы")
        gm = QVBoxLayout(grp_misc); gm.setSpacing(8)

        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("Задержка между VT запросами (сек):"))
        self.rate_inp = QLineEdit()
        self.rate_inp.setFixedWidth(80)
        rate_row.addWidget(self.rate_inp)
        rate_hint = QLabel("Бесплатный VT — 4/мин (15 сек). Платный — можно меньше.")
        rate_hint.setStyleSheet("color:#6e7681;font-size:11px;")
        rate_row.addWidget(rate_hint); rate_row.addStretch()
        gm.addLayout(rate_row)

        self.chk_autosave = QCheckBox("Автоматически сохранять отчёты после каждого сканирования")
        gm.addWidget(self.chk_autosave)
        lay.addWidget(grp_misc)

        # Buttons
        btn_row = QHBoxLayout()
        btn_save = QPushButton("Сохранить все настройки")
        btn_save.setFixedHeight(38); btn_save.clicked.connect(self._save_all)
        btn_row.addWidget(btn_save)

        btn_reset = QPushButton("Сбросить к умолчаниям")
        btn_reset.setObjectName("dangerBtn"); btn_reset.setFixedWidth(180); btn_reset.setFixedHeight(38)
        btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(btn_reset)

        btn_open = QPushButton("Открыть config.json")
        btn_open.setObjectName("secondaryBtn"); btn_open.setFixedWidth(160); btn_open.setFixedHeight(38)
        btn_open.clicked.connect(self._open_config)
        btn_row.addWidget(btn_open)
        lay.addLayout(btn_row)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#3fb950;font-size:12px;font-weight:bold;")
        lay.addWidget(self.status)

        # Info section
        info = QLabel(
            "Настройки сохраняются в config.json рядом с приложением.\n"
            "Файл создаётся автоматически при первом сохранении.\n"
            "API ключи хранятся в открытом виде — не делись config.json публично."
        )
        info.setStyleSheet(
            "color:#8b949e;font-size:11px;background:#161b22;"
            "border:1px solid #21262d;border-radius:6px;padding:12px;"
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        lay.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.addWidget(scroll)

    def _key_field(self, parent_layout, label, config_key, hint=""):
        row = QHBoxLayout(); row.setSpacing(6)
        lbl = QLabel(label + ":"); lbl.setFixedWidth(160); lbl.setStyleSheet("color:#c9d1d9;font-size:12px;")
        row.addWidget(lbl)
        inp = QLineEdit()
        inp.setEchoMode(QLineEdit.EchoMode.Password)
        inp.setProperty("config_key", config_key)
        row.addWidget(inp)
        btn_show = QPushButton("👁"); btn_show.setObjectName("secondaryBtn")
        btn_show.setFixedWidth(36); btn_show.setCheckable(True)
        btn_show.clicked.connect(lambda checked, i=inp: i.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password))
        row.addWidget(btn_show)
        parent_layout.addLayout(row)
        if hint:
            h = QLabel(hint)
            h.setStyleSheet("color:#6e7681;font-size:10px;margin-left:166px;")
            parent_layout.addWidget(h)
        return inp

    def _dir_field(self, parent_layout, label, config_key):
        row = QHBoxLayout()
        lbl = QLabel(label + ":"); lbl.setFixedWidth(220); lbl.setStyleSheet("color:#c9d1d9;font-size:12px;")
        row.addWidget(lbl)
        inp = QLineEdit()
        inp.setProperty("config_key", config_key)
        row.addWidget(inp)
        btn = QPushButton("Обзор"); btn.setObjectName("secondaryBtn"); btn.setFixedWidth(80)
        btn.clicked.connect(lambda _, i=inp: self._browse_dir(i))
        row.addWidget(btn)
        parent_layout.addLayout(row)
        return inp

    def _browse_dir(self, inp):
        d = QFileDialog.getExistingDirectory(self, "Выбери папку")
        if d: inp.setText(d)

    def _load(self):
        self.vt_inp.setText(Config.get("vt_api_key", ""))
        self.abuse_inp.setText(Config.get("abuseipdb_key", ""))
        self.groq_inp.setText(Config.get("groq_key", ""))
        self.claude_inp.setText(Config.get("claude_key", ""))
        self.results_inp.setText(Config.get("results_dir", ""))
        self.quar_inp.setText(Config.get("quarantine_dir", ""))
        self.rate_inp.setText(str(Config.get("vt_rate_limit_sec", 15)))
        self.chk_autosave.setChecked(Config.get("auto_save_reports", False))

    def _save_all(self):
        try:
            Config.set("vt_api_key",        self.vt_inp.text().strip())
            Config.set("abuseipdb_key",     self.abuse_inp.text().strip())
            Config.set("groq_key",          self.groq_inp.text().strip())
            Config.set("claude_key",        self.claude_inp.text().strip())
            Config.set("results_dir",       self.results_inp.text().strip())
            Config.set("quarantine_dir",    self.quar_inp.text().strip())
            try:
                Config.set("vt_rate_limit_sec", int(self.rate_inp.text().strip() or 15))
            except ValueError:
                Config.set("vt_rate_limit_sec", 15)
            Config.set("auto_save_reports", self.chk_autosave.isChecked())

            self.status.setText("✓ Настройки сохранены — некоторые изменения применятся после перезапуска")
            self.status.setStyleSheet("color:#3fb950;font-size:12px;font-weight:bold;")
            QTimer.singleShot(4000, lambda: self.status.setText(""))
        except Exception as e:
            self.status.setText(f"Ошибка: {e}")
            self.status.setStyleSheet("color:#f85149;font-size:12px;font-weight:bold;")

    def _reset(self):
        msg = QMessageBox.question(
            self, "Сброс настроек",
            "Сбросить все настройки к умолчаниям?\n(Ключи будут стёрты)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if msg == QMessageBox.StandardButton.Yes:
            Config.reset()
            self._load()
            self.status.setText("Сброшено к умолчаниям")
            self.status.setStyleSheet("color:#d29922;font-size:12px;font-weight:bold;")

    def _open_config(self):
        if Config._path and os.path.exists(Config._path):
            os.startfile(Config._path)
        else:
            Config.save()
            if Config._path:
                os.startfile(Config._path)
