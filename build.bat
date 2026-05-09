@echo off
echo ============================================
echo   IOC Analyzer v2.0 -- Build Script
echo ============================================
echo.

cd /d "%~dp0"
echo [INFO] Папка: %CD%
echo.

echo [1] Установка зависимостей...
python -m pip install PyQt6 requests pyinstaller --quiet

echo [2] Сборка .exe...
python -m PyInstaller --onefile --windowed --name "IOC_Analyzer_v2" main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Сборка не удалась.
    echo ВАЖНО: Запусти build.bat БЕЗ прав администратора!
    pause & exit /b 1
)

echo.
echo ============================================
echo  ГОТОВО: dist\IOC_Analyzer_v2.exe
echo ============================================
pause
