============================================================
  IOC ANALYZER v2.0 — Setup & Build Guide
  Diploma Project — AITU Cybersecurity School 2025
============================================================

НОВОЕ В v2.0:
─────────────────────────────────────────────
  ✔ ИСПРАВЛЕН БАГ: результаты сохраняются в
    правильную папку (не в папку скана)
  ✔ YARA Scanner — 20 встроенных правил
  ✔ AI Assistant — помощник на Claude API
  ✔ Report Builder — экспорт HTML/TXT
  ✔ Редактор YARA правил с AI-генерацией

ТРЕБОВАНИЯ:
─────────────────────────────────────────────
  - Windows 10/11
  - Python 3.10+
  - Интернет (для VT API и AI Assistant)

УСТАНОВКА И СБОРКА:
─────────────────────────────────────────────
1. Установи Python 3.10+ (галочка "Add to PATH")

2. Запусти build.bat от администратора

3. Готово: dist\IOC_Analyzer_v2.exe

БЕЗ СБОРКИ (разработка):
─────────────────────────────────────────────
  pip install -r requirements.txt
  python main.py

YARA ДВИЖОК:
─────────────────────────────────────────────
  Приоритет 1: yara64.exe в C:\Tools\yara\
    Скачать: https://github.com/VirusTotal/yara/releases

  Приоритет 2: pip install yara-python
    (устанавливается автоматически через build.bat)

AI ASSISTANT:
─────────────────────────────────────────────
  Нужен ключ Claude API (sk-ant-...)
  Получить бесплатно: https://console.anthropic.com
  Вводится прямо в интерфейсе вкладки AI Assistant

ВСТРОЕННЫЕ YARA ПРАВИЛА (20 штук):
─────────────────────────────────────────────
  CRITICAL: Mimikatz, Meterpreter, CobaltStrike,
            WannaCry, Emotet, Ransomware_Generic

  HIGH:     AgentTesla, Njrat, Keylogger_Generic,
            ProcessInjection, WebShell_PHP,
            Credential_Harvesting, UAC_Bypass,
            Lateral_Movement

  MEDIUM:   DLL_Sideloading, Suspicious_Office_Macro,
            Network_Recon, Persistence_Registry,
            Anti_Analysis

ИСПРАВЛЕННЫЙ БАГ:
─────────────────────────────────────────────
  v1: PowerShell скрипт жёстко хардкодил папку,
      игнорируя выбор пользователя в UI.
  v2: папка передаётся как параметр -ResultDir
      в скрипт, результаты всегда идут туда,
      куда указал пользователь.
