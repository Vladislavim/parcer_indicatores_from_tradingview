@echo off
chcp 65001 >nul
cls
echo ================================================
echo   Local Signals Pro - Установка и запуск
echo ================================================
echo.

echo [1/3] Проверка Python...
python --version
if errorlevel 1 (
    echo.
    echo ❌ Python не найден!
    echo Установите Python с https://www.python.org/
    pause
    exit /b 1
)
echo ✅ Python найден
echo.

echo [2/3] Установка зависимостей...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ❌ Ошибка установки зависимостей
    pause
    exit /b 1
)
echo ✅ Зависимости установлены
echo.

echo [3/3] Запуск приложения...
echo.
python run.py

if errorlevel 1 (
    echo.
    echo ❌ Ошибка запуска
    pause
)
