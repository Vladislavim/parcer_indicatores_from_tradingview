# Windows: Установка И Сборка `.exe`

Этот гайд для человека с Windows, чтобы:

1. Запустить проект из исходников
2. Собрать `.exe` (приложение) через PyInstaller

## 1. Что установить

- `Python 3.11` (рекомендуется)
- `Git` (если будет клонировать репозиторий)

Проверь в `cmd` или PowerShell:

```powershell
python --version
pip --version
```

Если `python` не найден:
- переустановить Python и включить галочку `Add python.exe to PATH`

## 2. Скачать проект

Вариант A: через `git`

```powershell
git clone https://github.com/Vladislavim/parcer_indicatores_from_tradingview.git
cd parcer_indicatores_from_tradingview\local-signals-app
```

Вариант B: через `Code -> Download ZIP`

- Распаковать архив
- Открыть папку `local-signals-app`

## 3. Запуск из исходников (без сборки)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install --no-compile -r requirements.txt
python run.py
```

Если PowerShell блокирует активацию:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 4. Подготовка перед сборкой `.exe`

Важно:
- не хранить реальные ключи в `config.json`, если `.exe` будет передаваться другому человеку
- ключи лучше вводить в самом приложении

## 5. Сборка `.exe` (PyInstaller)

Из папки `local-signals-app`:

```powershell
.\.venv\Scripts\Activate.ps1
pip install --no-compile pyinstaller
pyinstaller --noconfirm --windowed --name "Bybit Trading Terminal" --add-data "content;content" run.py
```

Готовый файл будет здесь:

```text
local-signals-app\dist\Bybit Trading Terminal\Bybit Trading Terminal.exe
```

## 6. Как отдать другому человеку

Лучше передавать папку целиком:

```text
dist\Bybit Trading Terminal\
```

Почему не только `.exe`:
- рядом лежат зависимости/Qt файлы
- нужны ресурсы (`content`)

## 7. Опционально: упаковать в ZIP

```powershell
Compress-Archive -Path ".\dist\Bybit Trading Terminal\*" -DestinationPath ".\Bybit-Trading-Terminal-Windows.zip" -Force
```

## 8. Типичные проблемы

### `ModuleNotFoundError`

Переустановить зависимости:

```powershell
pip install --no-compile -r requirements.txt
```

### `ccxt` / `PySide6` ставятся с ошибкой

- Обновить `pip/setuptools/wheel`
- Использовать Python 3.11

```powershell
python -m pip install --upgrade pip setuptools wheel
```

### Окно не открывается, но процесс есть

- Запустить из консоли:

```powershell
python run.py
```

- посмотреть текст ошибки в консоли

### SmartScreen предупреждает о `.exe`

Это нормально для локально собранного неподписанного приложения:
- `Подробнее` -> `Выполнить в любом случае`

## 9. Быстрая команда (всё сразу: установить и запустить)

Из `local-signals-app`:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; python -m pip install --upgrade pip setuptools wheel; pip install --no-compile -r requirements.txt; python run.py
```

## 10. Быстрая команда (сборка `.exe`)

Из `local-signals-app`:

```powershell
.\.venv\Scripts\Activate.ps1; pip install --no-compile pyinstaller; pyinstaller --noconfirm --windowed --name "Bybit Trading Terminal" --add-data "content;content" run.py
```

