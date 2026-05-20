# Host Status Live Monitor — Design Spec

**Date:** 2026-05-20  
**Feature:** Расширение вкладки «Статус» в HostsTab живой информационной картой хоста

---

## 1. Цель

Заменить статичный блок «онлайн/оффлайн» на живую информационную панель, которая показывает:
- Загрузку CPU (%)
- Использование RAM (использовано / всего, прогресс-бар)
- Использование диска C:\ (использовано / всего, прогресс-бар)
- Версию ОС (из `/ping`)
- Uptime хоста (рассчитывается из `boot_time`)
- Список активных пользователей сессии

Данные обновляются автоматически каждые 30 секунд пока хост выбран и вкладка «Статус» активна.

---

## 2. Изменения на стороне агента

**Никаких.** Эндпоинт `/info` уже реализован и возвращает:

```json
{
  "cpu_percent":  float,
  "ram_total":    int (bytes),
  "ram_used":     int (bytes),
  "ram_percent":  float,
  "disk_total":   int (bytes),
  "disk_used":    int (bytes),
  "disk_percent": float,
  "boot_time":    float (unix timestamp),
  "users":        ["DOMAIN\\user1", ...]
}
```

`AgentClient.get_info()` уже реализован в `core/agent_client.py`.

---

## 3. Новый воркер: `RemoteInfoWorker`

**Файл:** `workers/host_worker.py`

```python
class RemoteInfoWorker(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, host: dict): ...
    def run(self): client.get_info() → emit done(data) or error(str)
```

Паттерн идентичен остальным воркерам (`RemoteProcessListWorker`, `NetworkIsolationWorker`).

---

## 4. UI: новая карточка метрик в `_build_status_tab()`

### Расположение

Вставляется между карточкой деталей хоста (`card`) и кнопками действий (`_grp_act`).

### Содержимое карточки

| Виджет | Данные |
|--------|--------|
| CPU | `QProgressBar` (0–100) + QLabel "XX %" |
| RAM | `QProgressBar` (0–100) + QLabel "X.X / Y.Y GB" |
| Disk C:\ | `QProgressBar` (0–100) + QLabel "X.X / Y.Y GB" |
| ОС | `QLabel` — из `info["os"]` (сохраняется при пинге) |
| Uptime | `QLabel` — вычисляется из `boot_time`: `"N дней HH:MM"` |
| Пользователи | `QLabel` — `", ".join(users)` или `"—"` если список пуст |
| Последнее обновление | `QLabel` с временной меткой + кнопка `🔄 Обновить` |

Прогресс-бары: зелёный ≤ 60%, жёлтый 61–85%, красный > 85% (через `setStyleSheet`).

Виджеты хранятся в атрибутах `_met_*` чтобы не конфликтовать с существующими `_st_*`.

---

## 5. Логика таймера и воркера

- `_info_timer: QTimer` — 30 000 мс, `singleShot=False`
- Запускается при: выборе хоста И нахождении на вкладке Status (index == 0)
- Останавливается при: снятии выбора хоста ИЛИ переключении на другую вкладку
- При переключении обратно на Status — немедленный запуск + перезапуск таймера
- Защита от двойного запуска: новый воркер не создаётся пока предыдущий ещё работает

```
_on_tab_changed(idx):
    if idx == _TAB_STATUS and host selected → _start_info_timer()
    else → _stop_info_timer()

_on_host_select():
    ... existing logic ...
    → _start_info_timer() (if on STATUS tab)

_fetch_info():
    if _info_worker and _info_worker.isRunning(): return
    _info_worker = RemoteInfoWorker(host)
    _info_worker.done.connect(_on_info_done)
    _info_worker.error.connect(_on_info_error)
    _info_worker.start()

_on_info_done(data):
    обновляет все виджеты _met_*
    устанавливает цвета прогресс-баров
```

---

## 6. i18n

Новые ключи добавляются в `core/i18n.py` для RU/EN/KZ:

| Ключ | RU | EN |
|------|----|----|
| `hosts_met_cpu` | CPU | CPU |
| `hosts_met_ram` | Оперативная память | RAM |
| `hosts_met_disk` | Диск C:\ | Disk C:\ |
| `hosts_met_os` | Операционная система | OS |
| `hosts_met_uptime` | Время работы | Uptime |
| `hosts_met_users` | Активные пользователи | Active users |
| `hosts_met_updated` | Обновлено | Updated |
| `hosts_met_refresh` | Обновить | Refresh |
| `hosts_met_card_title` | Метрики хоста | Host Metrics |

---

## 7. Обработка ошибок

- Если хост оффлайн или `/info` вернул ошибку — прогресс-бары скрываются, показывается метка `"Нет данных"` в карточке метрик
- Таймер продолжает работать (повторит попытку через 30 с)
- Ошибка не показывается как диалог — только в самой карточке

---

## 8. Затронутые файлы

| Файл | Изменение |
|------|-----------|
| `workers/host_worker.py` | + `RemoteInfoWorker` |
| `ui/hosts_tab.py` | + карточка метрик, таймер, `_fetch_info`, `_on_info_done` |
| `core/i18n.py` | + 9 новых ключей (RU/EN/KZ) |
