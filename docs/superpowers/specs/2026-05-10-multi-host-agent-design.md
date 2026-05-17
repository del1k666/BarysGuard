# Multi-Host Agent Architecture

## Обзор

Система из двух частей: **агент** на каждом хосте + **вкладка Hosts** в главном приложении. Администратор добавляет хосты по IP, деплоит агент кнопкой из UI, запускает сканирование удалённо.

## Компоненты

### agent/agent.py — автономный агент (~300 строк)
- Flask HTTP-сервер на порту 5555 с HTTPS (self-signed cert)
- При первом запуске генерирует `cert.pem` / `key.pem` и `token.txt` в папке агента
- Устанавливается как Windows Service: `agent.exe --install` / `--uninstall`
- Собирается в один .exe через PyInstaller

**Эндпоинты (все требуют заголовок `X-Api-Token`):**
- `GET /ping` → `{status, hostname, os, agent_version}`
- `GET /info` → `{cpu, ram, disk, uptime, users}`
- `POST /scan/yara` body: `{rules: {...}, path: "C:\\..."}` → `{matches: [...]}`
- `POST /scan/ioc` → `{processes: [...], connections: [...], autoruns: [...]}`
- `POST /scan/memory` body: `{pid: 1234}` → `{matches: [...]}`
- `POST /scan/hashes` body: `{path: "C:\\..."}` → `{hashes: [...]}`

### core/agent_client.py — HTTP-клиент агента (~80 строк)
- Обёртка над `requests` с verify=False (self-signed), таймаут, retry
- Хранит URL и токен для каждого хоста
- Методы: `ping()`, `get_info()`, `scan_yara()`, `scan_ioc()`, `scan_memory()`, `scan_hashes()`

### core/hosts_config.py — хранение хостов (~40 строк)
- JSON-файл `hosts.json` рядом с `config.py`
- Поля хоста: `id`, `name`, `ip`, `port`, `token`, `last_seen`, `last_scan`

### workers/host_worker.py — фоновые задачи (~60 строк)
- `PingWorker(QThread)` — пингует все хосты, обновляет статусы
- `RemoteScanWorker(QThread)` — запускает выбранные типы сканов на хосте

### ui/hosts_tab.py — вкладка (~350 строк)
- Левая панель: список хостов, кнопка "+ Добавить хост" → диалог
- Правая панель: инфо о хосте, чекбоксы типов сканов, путь, кнопки Deploy/Scan
- Таблица результатов: Тип | Правило | Severity | Путь

### Изменения в main_window.py
- Добавить host-selector dropdown в шапке (Local / удалённые хосты)
- `current_host` — синглтон, все вкладки читают его при запуске операций

## Деплой агента

1. Главное приложение подключается по WinRM (`pywinrm`) с учётными данными
2. Копирует `agent.exe` в `C:\Program Files\IOCAgent\`
3. Запускает `agent.exe --install` на удалённом хосте
4. Читает сгенерированный токен через WinRM, сохраняет в `hosts.json`

## Зависимости

- Агент: `flask`, `pywin32`, `psutil`, `yara-python` (или yara64.exe рядом)
- Главное приложение: `requests`, `pywinrm` (только для деплоя), `urllib3`

## Безопасность

- HTTPS: self-signed cert, `verify=False` на клиенте (внутренняя сеть)
- API-токен генерируется случайно при первой установке (`secrets.token_hex(32)`)
- Токен передаётся в заголовке `X-Api-Token`
- Агент принимает соединения только с токеном — без него 403
