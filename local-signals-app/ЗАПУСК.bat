@echo off
chcp 65001 >nul
cls
echo.
echo ╔════════════════════════════════════════════════╗
echo ║   Local Signals Pro - Binance Demo Trading    ║
echo ╚════════════════════════════════════════════════╝
echo.
echo 🚀 Запуск приложения...
echo.
python run.py
if errorlevel 1 (
    echo.
    echo ❌ Ошибка запуска!
    echo.
    echo Возможные причины:
    echo  - Не установлены зависимости
    echo  - Запустите: install_and_run.bat
    echo.
    pause
)
