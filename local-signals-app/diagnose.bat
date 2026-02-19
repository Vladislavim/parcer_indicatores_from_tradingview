@echo off
chcp 65001 >nul
cls
echo ================================================
echo   Диагностика Local Signals Pro
echo ================================================
echo.

echo [Проверка Python]
python --version 2>nul
if errorlevel 1 (
    echo ❌ Python не найден
    echo Установите Python: https://www.python.org/
) else (
    echo ✅ Python установлен
)
echo.

echo [Проверка pip]
python -m pip --version 2>nul
if errorlevel 1 (
    echo ❌ pip не найден
) else (
    echo ✅ pip установлен
)
echo.

echo [Проверка зависимостей]
python -c "import PySide6; print('✅ PySide6:', PySide6.__version__)" 2>nul || echo ❌ PySide6 не установлен
python -c "import ccxt; print('✅ CCXT:', ccxt.__version__)" 2>nul || echo ❌ CCXT не установлен
python -c "import requests; print('✅ Requests:', requests.__version__)" 2>nul || echo ❌ Requests не установлен
echo.

echo [Проверка config.json]
if exist config.json (
    echo ✅ config.json найден
    python -c "import json; c=json.load(open('config.json')); print('   Exchange:', c.get('exchange')); print('   API Key:', c.get('api_key')[:20]+'...' if c.get('api_key') else 'НЕ ЗАДАН')" 2>nul
) else (
    echo ❌ config.json не найден
)
echo.

echo [Проверка файлов]
if exist run.py (echo ✅ run.py) else (echo ❌ run.py не найден)
if exist main.py (echo ✅ main.py) else (echo ❌ main.py не найден)
if exist ui\modern_app.py (echo ✅ ui\modern_app.py) else (echo ❌ ui\modern_app.py не найден)
echo.

echo ================================================
echo   Рекомендации:
echo ================================================
echo.
echo 1. Если Python не найден - установите Python 3.10+
echo 2. Если зависимости не установлены - запустите:
echo    install_and_run.bat
echo.
echo 3. Если всё установлено но не запускается:
echo    - Проверьте антивирус
echo    - Запустите от имени администратора
echo    - Проверьте логи в папке
echo.

pause
