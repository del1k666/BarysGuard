from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QProgressBar, QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat
from config import Config
from constants import AI_SYSTEM, QUICK_PROMPTS
from workers.ai_worker import AIWorker


class AITab(QWidget):
    def __init__(self):
        super().__init__()
        self._history = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(16,16,16,16)

        # Provider + API key row
        cfg_grp = QGroupBox("Настройка AI")
        cfg_lay = QVBoxLayout(cfg_grp); cfg_lay.setSpacing(8)

        prov_row = QHBoxLayout()
        prov_row.addWidget(QLabel("Провайдер:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Groq  (бесплатно, быстро)", "groq")
        self.provider_combo.addItem("Claude API (платно)", "claude")
        # Восстанавливаем сохранённый провайдер
        saved_provider = Config.get("ai_provider", "groq")
        idx = 0 if saved_provider == "groq" else 1
        self.provider_combo.setCurrentIndex(idx)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_change)
        prov_row.addWidget(self.provider_combo)
        prov_row.addStretch()
        cfg_lay.addLayout(prov_row)

        key_row = QHBoxLayout()
        self.key_label = QLabel("Groq API Key:" if saved_provider == "groq" else "Claude API Key:")
        key_row.addWidget(self.key_label)
        self.key_inp = QLineEdit()
        self.key_inp.setEchoMode(QLineEdit.EchoMode.Password)
        # Подгружаем сохранённый ключ
        if saved_provider == "groq":
            self.key_inp.setText(Config.get("groq_key", ""))
            self.key_inp.setPlaceholderText("gsk_...   Получи бесплатно: console.groq.com")
        else:
            self.key_inp.setText(Config.get("claude_key", ""))
            self.key_inp.setPlaceholderText("sk-ant-...   console.anthropic.com")
        key_row.addWidget(self.key_inp)
        # Кнопка показать/скрыть
        self.btn_show = QPushButton("👁"); self.btn_show.setObjectName("secondaryBtn")
        self.btn_show.setFixedWidth(36); self.btn_show.setCheckable(True)
        self.btn_show.clicked.connect(lambda checked: self.key_inp.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password))
        key_row.addWidget(self.btn_show)
        # Кнопка сохранить
        self.btn_save_key = QPushButton("Сохранить"); self.btn_save_key.setFixedWidth(100)
        self.btn_save_key.clicked.connect(self._save_key)
        key_row.addWidget(self.btn_save_key)
        cfg_lay.addLayout(key_row)

        hint = QLabel("Groq: регистрация на console.groq.com → API Keys → Create. Бесплатно, без карты.")
        hint.setStyleSheet("color:#6e7681;font-size:11px;")
        hint.setWordWrap(True)
        self.groq_hint = hint
        hint.setVisible(saved_provider == "groq")
        cfg_lay.addWidget(hint)
        lay.addWidget(cfg_grp)

        # Quick prompts + file upload row
        top_row = QHBoxLayout()

        grp_q = QGroupBox("Быстрые запросы")
        gq    = QHBoxLayout(grp_q); gq.setSpacing(6)
        self.combo = QComboBox()
        for p in QUICK_PROMPTS: self.combo.addItem(p)
        gq.addWidget(self.combo)
        btn_q = QPushButton("Отправить")
        btn_q.setFixedWidth(100)
        btn_q.clicked.connect(self._send_quick); gq.addWidget(btn_q)
        top_row.addWidget(grp_q, 3)

        grp_f = QGroupBox("Загрузить отчёт")
        gf    = QVBoxLayout(grp_f); gf.setSpacing(4)
        self.file_label = QLabel("Файл не выбран")
        self.file_label.setStyleSheet("color:#6e7681;font-size:11px;")
        self.file_label.setWordWrap(True)
        gf.addWidget(self.file_label)
        btn_file = QPushButton("Выбрать файл")
        btn_file.setObjectName("secondaryBtn")
        btn_file.clicked.connect(self._load_report)
        gf.addWidget(btn_file)
        top_row.addWidget(grp_f, 1)
        lay.addLayout(top_row)

        # Chat window
        self.chat = QTextEdit(); self.chat.setReadOnly(True)
        self.chat.setStyleSheet(
            "background:#0a0e14;border:1px solid #21262d;border-radius:8px;"
            "font-family:Segoe UI,sans-serif;font-size:13px;padding:12px;line-height:1.6;")
        self.chat.setMinimumHeight(260)
        lay.addWidget(self.chat)

        # Input row
        inp_row = QHBoxLayout()
        self.msg_inp = QTextEdit(); self.msg_inp.setMaximumHeight(72)
        self.msg_inp.setPlaceholderText("Введите запрос...  Ctrl+Enter — отправить")
        self.msg_inp.setStyleSheet(
            "background:#161b22;border:1px solid #30363d;border-radius:6px;"
            "font-family:Segoe UI,sans-serif;font-size:13px;padding:8px;")
        inp_row.addWidget(self.msg_inp)

        col = QVBoxLayout(); col.setSpacing(6)
        self.btn_send = QPushButton("Отправить")
        self.btn_send.setFixedWidth(110); self.btn_send.setFixedHeight(32)
        self.btn_send.clicked.connect(self._send); col.addWidget(self.btn_send)
        btn_clr = QPushButton("Очистить"); btn_clr.setObjectName("secondaryBtn")
        btn_clr.setFixedWidth(110); btn_clr.setFixedHeight(32)
        btn_clr.clicked.connect(self._clear); col.addWidget(btn_clr)
        inp_row.addLayout(col)
        lay.addLayout(inp_row)

        self.prog = QProgressBar(); self.prog.setRange(0,0); self.prog.setVisible(False)
        self.prog.setFixedHeight(3); lay.addWidget(self.prog)

        self._report_content = ""
        self._append_chat("assistant",
            "Добро пожаловать. Я аналитик по кибербезопасности.\n\n"
            "Могу помочь:\n"
            "  — написать или разобрать YARA правило\n"
            "  — проанализировать IoC и артефакты\n"
            "  — разобрать загруженный отчёт (CSV, TXT, HTML)\n"
            "  — объяснить технику атаки MITRE ATT&CK\n\n"
            "Для анализа отчёта — загрузи файл через кнопку справа.")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Return and e.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._send()
        super().keyPressEvent(e)

    def _append_chat(self, role, text):
        cursor = self.chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt_name = QTextCharFormat()
        fmt_text = QTextCharFormat()
        fmt_text.setFont(QFont("Consolas", 12))

        if role == "user":
            fmt_name.setForeground(QColor("#58a6ff"))
            fmt_name.setFontWeight(700)
            cursor.insertText("\n\n[ВЫ]\n", fmt_name)
        else:
            fmt_name.setForeground(QColor("#3fb950"))
            fmt_name.setFontWeight(700)
            cursor.insertText("\n\n[AI ASSISTANT]\n", fmt_name)

        fmt_text.setForeground(QColor("#e6edf3"))
        cursor.insertText(text, fmt_text)
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()

    def _on_provider_change(self, idx):
        provider = self.provider_combo.currentData()
        Config.set("ai_provider", provider)
        if provider == "groq":
            self.key_label.setText("Groq API Key:")
            self.key_inp.setPlaceholderText("gsk_...   Получи бесплатно: console.groq.com")
            self.key_inp.setText(Config.get("groq_key", ""))
            self.groq_hint.setVisible(True)
        else:
            self.key_label.setText("Claude API Key:")
            self.key_inp.setPlaceholderText("sk-ant-...   console.anthropic.com")
            self.key_inp.setText(Config.get("claude_key", ""))
            self.groq_hint.setVisible(False)

    def _save_key(self):
        provider = self.provider_combo.currentData()
        key = self.key_inp.text().strip()
        if provider == "groq":
            Config.set("groq_key", key)
        else:
            Config.set("claude_key", key)
        # Краткая визуальная индикация
        orig = self.btn_save_key.text()
        self.btn_save_key.setText("✓ Сохранено")
        QTimer.singleShot(1500, lambda: self.btn_save_key.setText(orig))

    def _load_report(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать отчёт", "",
            "Текстовые файлы (*.txt *.csv *.log *.html *.json);;Все файлы (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            # Обрезаем до 8000 символов чтобы не превысить контекст
            if len(content) > 8000:
                content = content[:8000] + "\n\n[... файл обрезан до 8000 символов ...]"
            self._report_content = content
            name = Path(path).name
            self.file_label.setText(name)
            self.file_label.setStyleSheet("color:#3fb950;font-size:11px;")
            self._append_chat("assistant",
                f"Файл загружен: {name}\n"
                f"Размер: {len(content)} символов\n\n"
                "Задай вопрос по содержимому — например:\n"
                "  — Что подозрительного в этом отчёте?\n"
                "  — Какие процессы выглядят опасно?\n"
                "  — Сделай краткое резюме находок."
            )
        except Exception as e:
            self.file_label.setText(f"Ошибка: {e}")
            self.file_label.setStyleSheet("color:#f85149;font-size:11px;")

    def _send_quick(self):
        self.msg_inp.setPlainText(self.combo.currentText())
        self._send()

    def _send(self):
        key = self.key_inp.text().strip()
        if not key:
            provider = self.provider_combo.currentData()
            if provider == "groq":
                self._append_chat("assistant",
                    "Введи Groq API ключ выше.\n"
                    "Получить бесплатно: console.groq.com → API Keys → Create Key"
                )
            else:
                self._append_chat("assistant", "Введи Claude API ключ выше.")
            return

        text = self.msg_inp.toPlainText().strip()
        if not text:
            return

        # Если загружен отчёт — добавляем его в контекст первого сообщения
        full_text = text
        if self._report_content and not any(
            "СОДЕРЖИМОЕ ФАЙЛА" in m.get("content","") for m in self._history
        ):
            full_text = (
                f"СОДЕРЖИМОЕ ФАЙЛА (отчёт для анализа):\n"
                f"{'='*50}\n{self._report_content}\n{'='*50}\n\n"
                f"Вопрос: {text}"
            )

        self._history.append({"role":"user","content":full_text})
        self._append_chat("user", text)
        self.msg_inp.clear()
        self.btn_send.setEnabled(False)
        self.prog.setVisible(True)

        provider = self.provider_combo.currentData()
        self._w = AIWorker(list(self._history), AI_SYSTEM, api_key=key, provider=provider)
        self._w.chunk.connect(self._on_chunk)
        self._w.done.connect(self._on_done)
        self._w.error.connect(self._on_error)
        self._w.start()

    def _on_chunk(self, text):
        self._last_response = text
        self._append_chat("assistant", text)
        self._history.append({"role":"assistant","content":text})

    def _on_done(self):
        self.btn_send.setEnabled(True)
        self.prog.setVisible(False)

    def _on_error(self, msg):
        self._append_chat("assistant", f"⚠ Ошибка: {msg}")
        self.btn_send.setEnabled(True)
        self.prog.setVisible(False)

    def _clear(self):
        self.chat.clear(); self._history = []
