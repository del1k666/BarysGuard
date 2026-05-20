# Host Status Live Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Расширить вкладку «Статус» живой информационной панелью: CPU, RAM, Disk, Uptime, OS, активные пользователи — с авто-обновлением каждые 30 секунд.

**Architecture:** Новый `RemoteInfoWorker` (QThread) вызывает `AgentClient.get_info()` и передаёт данные в UI через сигнал `done(dict)`. В `HostsTab` добавляется `QTimer` на 30 с; запускается только пока хост выбран и активна вкладка «Статус». Агент уже имеет эндпоинт `/info`, добавим к нему поле `"os"`.

**Tech Stack:** Python 3.13, PyQt6, psutil (уже в агенте), requests (уже в клиенте)

---

## Затронутые файлы

| Файл | Изменение |
|------|-----------|
| `agent/agent.py` | + поле `"os"` в `/info` (1 строка) |
| `workers/host_worker.py` | + класс `RemoteInfoWorker` |
| `core/i18n.py` | + 9 ключей в трёх языковых блоках |
| `ui/hosts_tab.py` | + метрик-карточка, таймер, 5 новых методов, обновления retranslate / _on_tab_changed / _on_host_select |
| `tests/test_agent_client.py` | + 1 тест для `get_info()` |
| `tests/test_host_worker.py` | новый файл — тест `RemoteInfoWorker` |

---

## Task 1: Добавить OS в `/info` агента

**Files:**
- Modify: `agent/agent.py:121-136`

- [ ] **Step 1: Открыть `agent/agent.py`, найти маршрут `/info` (около строки 121)**

Текущий код:
```python
@app.route("/info")
@_auth
def info():
    mem  = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    return jsonify({
        "cpu_percent":  psutil.cpu_percent(interval=0.5),
        "ram_total":    mem.total,
        "ram_used":     mem.used,
        "ram_percent":  mem.percent,
        "disk_total":   disk.total,
        "disk_used":    disk.used,
        "disk_percent": disk.percent,
        "boot_time":    psutil.boot_time(),
        "users":        [u.name for u in psutil.users()],
    })
```

- [ ] **Step 2: Добавить поле `"os"` в ответ**

Заменить строку `"users": [u.name for u in psutil.users()],` на:
```python
        "disk_percent": disk.percent,
        "boot_time":    psutil.boot_time(),
        "os":           platform.platform(),
        "users":        [u.name for u in psutil.users()],
```

(Импорт `platform` уже есть в строке ~18 файла.)

- [ ] **Step 3: Commit**

```bash
git add agent/agent.py
git commit -m "feat(agent): expose os field in /info endpoint"
```

---

## Task 2: Добавить `RemoteInfoWorker`

**Files:**
- Modify: `workers/host_worker.py` (append after line 392)
- Create: `tests/test_host_worker.py`

- [ ] **Step 1: Написать тест (новый файл `tests/test_host_worker.py`)**

```python
from unittest.mock import patch, MagicMock
import pytest
from workers.host_worker import RemoteInfoWorker


INFO_PAYLOAD = {
    "cpu_percent": 42.5,
    "ram_total":   8 * 1024**3,
    "ram_used":    4 * 1024**3,
    "ram_percent": 50.0,
    "disk_total":  100 * 1024**3,
    "disk_used":   60 * 1024**3,
    "disk_percent": 60.0,
    "boot_time":   1_700_000_000.0,
    "os":          "Windows-10-10.0.19041",
    "users":       ["DOMAIN\\alice"],
}


def test_remote_info_worker_emits_done(qtbot):
    host = {"ip": "192.168.1.1", "port": 5555, "token": "tok"}
    worker = RemoteInfoWorker(host)

    received = []
    worker.done.connect(received.append)

    mock_resp = MagicMock()
    mock_resp.json.return_value = INFO_PAYLOAD
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        with qtbot.waitSignal(worker.done, timeout=3000):
            worker.start()

    assert len(received) == 1
    assert received[0]["cpu_percent"] == 42.5
    assert received[0]["os"] == "Windows-10-10.0.19041"


def test_remote_info_worker_emits_error_on_failure(qtbot):
    host = {"ip": "192.168.1.1", "port": 5555, "token": "tok"}
    worker = RemoteInfoWorker(host)

    errors = []
    worker.error.connect(errors.append)

    import requests as req
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req.HTTPError("403")

    with patch("requests.get", return_value=mock_resp):
        with qtbot.waitSignal(worker.error, timeout=3000):
            worker.start()

    assert len(errors) == 1
```

- [ ] **Step 2: Запустить тест — убедиться, что он падает (класс не существует)**

```bash
pytest tests/test_host_worker.py -v
```

Ожидаемый результат: `ImportError: cannot import name 'RemoteInfoWorker'`

- [ ] **Step 3: Добавить класс в `workers/host_worker.py`** (в конец файла, после `NetworkIsolationWorker`)

```python


class RemoteInfoWorker(QThread):
    """Fetches live system metrics from remote agent via /info."""
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, host: dict):
        super().__init__()
        self._host = host

    def run(self):
        client = AgentClient(self._host["ip"], self._host["port"],
                             self._host["token"], timeout=15)
        try:
            self.done.emit(client.get_info())
        except Exception as e:
            self.error.emit(str(e))
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

```bash
pytest tests/test_host_worker.py -v
```

Ожидаемый результат: `2 passed`

- [ ] **Step 5: Добавить тест для `get_info()` в `tests/test_agent_client.py`**

Добавить в конец файла:
```python
def test_get_info_returns_metrics(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "cpu_percent": 23.0, "ram_percent": 55.0,
        "disk_percent": 40.0, "os": "Windows-10",
        "boot_time": 1_700_000_000.0, "users": [],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as m:
        result = client.get_info()
        m.assert_called_once_with(
            "https://192.168.1.1:5555/info",
            headers={"X-Api-Token": "testtoken", "Content-Type": "application/json"},
            verify=False,
            timeout=10,
        )
    assert result["cpu_percent"] == 23.0
    assert result["os"] == "Windows-10"
```

- [ ] **Step 6: Запустить все тесты**

```bash
pytest tests/ -v
```

Ожидаемый результат: все тесты проходят.

- [ ] **Step 7: Commit**

```bash
git add workers/host_worker.py tests/test_host_worker.py tests/test_agent_client.py
git commit -m "feat(workers): add RemoteInfoWorker for live host metrics"
```

---

## Task 3: Добавить i18n ключи

**Files:**
- Modify: `core/i18n.py`

- [ ] **Step 1: Найти блок `"eng"` — строку `"hosts_go_iso_btn": "🔒  Network isolation",`**

После этой строки (около строки 250) вставить:
```python
        "hosts_met_card_title":  "Host Metrics",
        "hosts_met_cpu":         "CPU",
        "hosts_met_ram":         "RAM",
        "hosts_met_disk":        "Disk C:\\",
        "hosts_met_os":          "Operating System",
        "hosts_met_uptime":      "Uptime",
        "hosts_met_users":       "Active users",
        "hosts_met_updated":     "Updated",
        "hosts_met_refresh":     "Refresh",
```

- [ ] **Step 2: Найти блок `"rus"` — строку `"hosts_go_iso_btn": "🔒  Изоляция сети",`**

После неё (около строки 543) вставить:
```python
        "hosts_met_card_title":  "Метрики хоста",
        "hosts_met_cpu":         "CPU",
        "hosts_met_ram":         "Оперативная память",
        "hosts_met_disk":        "Диск C:\\",
        "hosts_met_os":          "Операционная система",
        "hosts_met_uptime":      "Время работы",
        "hosts_met_users":       "Активные пользователи",
        "hosts_met_updated":     "Обновлено",
        "hosts_met_refresh":     "Обновить",
```

- [ ] **Step 3: Найти блок `"kaz"` — строку `"hosts_go_iso_btn": "🔒  Желі оқшаулауы",`**

После неё (около строки 836) вставить:
```python
        "hosts_met_card_title":  "Хост метрикалары",
        "hosts_met_cpu":         "CPU",
        "hosts_met_ram":         "Жедел жады",
        "hosts_met_disk":        "Диск C:\\",
        "hosts_met_os":          "Операциялық жүйе",
        "hosts_met_uptime":      "Жұмыс уақыты",
        "hosts_met_users":       "Белсенді пайдаланушылар",
        "hosts_met_updated":     "Жаңартылды",
        "hosts_met_refresh":     "Жаңарту",
```

- [ ] **Step 4: Commit**

```bash
git add core/i18n.py
git commit -m "feat(i18n): add host metrics keys for RU/EN/KZ"
```

---

## Task 4: Построить карточку метрик в UI

**Files:**
- Modify: `ui/hosts_tab.py`

- [ ] **Step 1: Добавить `RemoteInfoWorker` в импорт** (строка 18-22)

Заменить:
```python
from workers.host_worker import (
    PingWorker, RemoteScanWorker, DeployWorker,
    RemoteProcessListWorker, RemoteMemScanWorker,
    NetworkIsolationWorker, RemoteHashVTWorker,
)
```
На:
```python
from workers.host_worker import (
    PingWorker, RemoteScanWorker, DeployWorker,
    RemoteProcessListWorker, RemoteMemScanWorker,
    NetworkIsolationWorker, RemoteHashVTWorker,
    RemoteInfoWorker,
)
```

- [ ] **Step 2: Добавить атрибут `_info_worker` в `__init__`** (после строки `self._vt_worker: RemoteHashVTWorker | None = None`)

```python
        self._info_worker:   RemoteInfoWorker | None = None
```

- [ ] **Step 3: Добавить вспомогательный метод `_set_bar_color`** (вставить перед `_build_status_tab` или рядом с `_detail_row`)

```python
    def _set_bar_color(self, bar: QProgressBar, pct: float):
        if pct <= 60:
            color = "#3fb950"
        elif pct <= 85:
            color = "#d29922"
        else:
            color = "#f85149"
        bar.setStyleSheet(
            f"QProgressBar{{border:1px solid #30363d;border-radius:4px;"
            f"background:#0d1117;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:3px;}}"
        )
```

- [ ] **Step 4: Добавить карточку метрик в `_build_status_tab()`**

Найти строку `lay.addWidget(card)` (после `cl.insertWidget(0, self._st_name)`). Вставить **после** неё следующий блок (перед `# Action buttons`):

```python
        # ── Metrics card ─────────────────────────────────────────────────
        self._grp_metrics = QGroupBox(t("hosts_met_card_title"))
        gm = QVBoxLayout(self._grp_metrics)
        gm.setSpacing(8)

        def _bar_row(label_key: str):
            row = QHBoxLayout()
            lbl = QLabel(t(label_key) + ":")
            lbl.setMinimumWidth(170)
            lbl.setStyleSheet("color:#6e7681;font-size:12px;")
            bar = QProgressBar()
            bar.setRange(0, 100); bar.setValue(0)
            bar.setFixedHeight(14); bar.setTextVisible(False)
            bar.setStyleSheet(
                "QProgressBar{border:1px solid #30363d;border-radius:4px;background:#0d1117;}"
                "QProgressBar::chunk{background:#3fb950;border-radius:3px;}"
            )
            val = QLabel("—")
            val.setMinimumWidth(120)
            val.setStyleSheet("color:#e6edf3;font-size:12px;")
            row.addWidget(lbl); row.addWidget(bar, 1); row.addWidget(val)
            return row, lbl, bar, val

        cpu_row,  self._met_cpu_lbl,  self._met_cpu_bar,  self._met_cpu_val  = _bar_row("hosts_met_cpu")
        ram_row,  self._met_ram_lbl,  self._met_ram_bar,  self._met_ram_val  = _bar_row("hosts_met_ram")
        disk_row, self._met_disk_lbl, self._met_disk_bar, self._met_disk_val = _bar_row("hosts_met_disk")
        gm.addLayout(cpu_row)
        gm.addLayout(ram_row)
        gm.addLayout(disk_row)

        self._met_os_lbl,     self._met_os     = self._detail_row(gm, t("hosts_met_os"))
        self._met_uptime_lbl, self._met_uptime = self._detail_row(gm, t("hosts_met_uptime"))
        self._met_users_lbl,  self._met_users  = self._detail_row(gm, t("hosts_met_users"))

        upd_row = QHBoxLayout()
        self._met_updated_lbl = QLabel(t("hosts_met_updated") + ": —")
        self._met_updated_lbl.setStyleSheet("color:#6e7681;font-size:11px;")
        self._btn_met_refresh = QPushButton(t("hosts_met_refresh"))
        self._btn_met_refresh.setObjectName("secondaryBtn")
        self._btn_met_refresh.setFixedHeight(28)
        self._btn_met_refresh.clicked.connect(self._fetch_info)
        upd_row.addWidget(self._met_updated_lbl)
        upd_row.addStretch()
        upd_row.addWidget(self._btn_met_refresh)
        gm.addLayout(upd_row)

        lay.addWidget(self._grp_metrics)
        # ─────────────────────────────────────────────────────────────────
```

Также сохраним ссылки на label-ключи для `retranslate()`. Для строк с прогресс-барами label создаётся внутри `_bar_row` — нам нужно их сохранить. Изменить код `_bar_row` вызовов:

```python
        cpu_row, self._met_cpu_bar, self._met_cpu_val   = _bar_row("hosts_met_cpu")
        self._met_cpu_lbl = cpu_row.itemAt(0).widget()
        ram_row, self._met_ram_bar, self._met_ram_val   = _bar_row("hosts_met_ram")
        self._met_ram_lbl = ram_row.itemAt(0).widget()
        disk_row, self._met_disk_bar, self._met_disk_val = _bar_row("hosts_met_disk")
        self._met_disk_lbl = disk_row.itemAt(0).widget()
```

- [ ] **Step 5: Commit**

```bash
git add ui/hosts_tab.py
git commit -m "feat(ui): add host metrics card to Status tab"
```

---

## Task 5: Логика таймера и воркера

**Files:**
- Modify: `ui/hosts_tab.py`

- [ ] **Step 1: Добавить методы таймера и воркера** (вставить после `_start_ping_timer` / рядом с блоком Ping, около строки 1074)

```python
    # ── Info (live metrics) ────────────────────────────────────────────────

    def _start_info_timer(self):
        if not hasattr(self, "_info_timer"):
            self._info_timer = QTimer(self)
            self._info_timer.timeout.connect(self._fetch_info)
        self._fetch_info()
        self._info_timer.start(30_000)

    def _stop_info_timer(self):
        if hasattr(self, "_info_timer"):
            self._info_timer.stop()

    def _fetch_info(self):
        if not self._selected_id:
            return
        if self._info_worker and self._info_worker.isRunning():
            return
        hosts = [h for h in load_hosts() if h["id"] == self._selected_id]
        if not hosts:
            return
        self._info_worker = RemoteInfoWorker(hosts[0])
        self._info_worker.done.connect(self._on_info_done)
        self._info_worker.error.connect(self._on_info_error)
        self._info_worker.start()

    def _on_info_done(self, data: dict):
        import time
        from datetime import timedelta

        cpu      = data.get("cpu_percent", 0)
        ram_pct  = data.get("ram_percent", 0)
        ram_used = data.get("ram_used",  0) / 1024**3
        ram_tot  = data.get("ram_total", 1) / 1024**3
        dsk_pct  = data.get("disk_percent", 0)
        dsk_used = data.get("disk_used",  0) / 1024**3
        dsk_tot  = data.get("disk_total", 1) / 1024**3
        boot     = data.get("boot_time", 0)
        os_str   = data.get("os", "—")
        users    = data.get("users", [])

        self._met_cpu_bar.setValue(int(cpu))
        self._met_cpu_val.setText(f"{cpu:.1f} %")
        self._set_bar_color(self._met_cpu_bar, cpu)

        self._met_ram_bar.setValue(int(ram_pct))
        self._met_ram_val.setText(f"{ram_used:.1f} / {ram_tot:.1f} GB")
        self._set_bar_color(self._met_ram_bar, ram_pct)

        self._met_disk_bar.setValue(int(dsk_pct))
        self._met_disk_val.setText(f"{dsk_used:.1f} / {dsk_tot:.1f} GB")
        self._set_bar_color(self._met_disk_bar, dsk_pct)

        self._met_os.setText(os_str)

        if boot:
            td   = timedelta(seconds=time.time() - boot)
            h, r = divmod(td.seconds, 3600)
            m    = r // 60
            self._met_uptime.setText(f"{td.days}d {h:02d}:{m:02d}")
        else:
            self._met_uptime.setText("—")

        self._met_users.setText(", ".join(users) if users else "—")
        self._met_updated_lbl.setText(
            f"{t('hosts_met_updated')}: {datetime.now().strftime('%H:%M:%S')}")

    def _on_info_error(self, _msg: str):
        for bar in (self._met_cpu_bar, self._met_ram_bar, self._met_disk_bar):
            bar.setValue(0)
            self._set_bar_color(bar, 0)
        for lbl in (self._met_cpu_val, self._met_ram_val, self._met_disk_val,
                    self._met_os, self._met_uptime, self._met_users):
            lbl.setText("—")
        self._met_updated_lbl.setText(t("hosts_met_updated") + ": ✗")
```

- [ ] **Step 2: Обновить `_on_tab_changed()`**

Найти (строка ~990):
```python
    def _on_tab_changed(self, idx: int):
        if idx == self._TAB_ISOLATE:
            self._check_isolation_status()
```

Заменить на:
```python
    def _on_tab_changed(self, idx: int):
        if idx == self._TAB_STATUS and self._selected_id:
            self._start_info_timer()
        else:
            self._stop_info_timer()
        if idx == self._TAB_ISOLATE:
            self._check_isolation_status()
```

- [ ] **Step 3: Обновить `_on_host_select()`**

Найти блок `if row < 0:` (~строка 959):
```python
        if row < 0:
            self._selected_id = None
            self._btn_remove.setEnabled(False)
            self._sub_tabs.setEnabled(False)
            self._showing_hint = True
            self._info_label.setText(t("hosts_select_hint"))
            return
```

Добавить `self._stop_info_timer()` перед `return`:
```python
        if row < 0:
            self._selected_id = None
            self._btn_remove.setEnabled(False)
            self._sub_tabs.setEnabled(False)
            self._showing_hint = True
            self._info_label.setText(t("hosts_select_hint"))
            self._stop_info_timer()
            return
```

Найти строку `self._update_status_tab(host)` (~строка 979). Добавить после неё:
```python
        self._update_status_tab(host)
        if self._sub_tabs.currentIndex() == self._TAB_STATUS:
            self._start_info_timer()
        if self._on_host_changed:
```

- [ ] **Step 4: Commit**

```bash
git add ui/hosts_tab.py
git commit -m "feat(ui): wire RemoteInfoWorker timer and display logic to Status tab"
```

---

## Task 6: Обновить `retranslate()`

**Files:**
- Modify: `ui/hosts_tab.py`

- [ ] **Step 1: Найти `retranslate()` секцию `# Status tab`** (~строка 890)

После строки:
```python
        self._st_status_lbl.setText(t("hosts_status_lbl") + ":")
```

Добавить:
```python
        # Metrics card
        self._grp_metrics.setTitle(t("hosts_met_card_title"))
        self._met_cpu_lbl.setText(t("hosts_met_cpu") + ":")
        self._met_ram_lbl.setText(t("hosts_met_ram") + ":")
        self._met_disk_lbl.setText(t("hosts_met_disk") + ":")
        self._met_os_lbl.setText(t("hosts_met_os") + ":")
        self._met_uptime_lbl.setText(t("hosts_met_uptime") + ":")
        self._met_users_lbl.setText(t("hosts_met_users") + ":")
        self._btn_met_refresh.setText(t("hosts_met_refresh"))
```

- [ ] **Step 2: Запустить приложение и проверить вручную**

```bash
python main.py
```

Проверить:
1. Выбрать хост — карточка метрик появляется, данные загружаются
2. Переключиться на другую вкладку — таймер останавливается (нет запросов в логе агента)
3. Вернуться на «Статус» — данные обновляются автоматически
4. Кнопка «Обновить» принудительно запрашивает данные
5. Переключить язык — все подписи меняются
6. Если хост оффлайн — поля показывают «—», прогресс-бары обнулены

- [ ] **Step 3: Commit**

```bash
git add ui/hosts_tab.py
git commit -m "feat(i18n): retranslate metrics card labels on language switch"
```

---

## Task 7: Финальный прогон тестов

- [ ] **Step 1: Запустить все тесты**

```bash
pytest tests/ -v
```

Ожидаемый результат: все тесты проходят.

- [ ] **Step 2: Финальный commit (если есть незакоммиченные изменения)**

```bash
git add -A
git commit -m "test: add RemoteInfoWorker and get_info tests"
```
