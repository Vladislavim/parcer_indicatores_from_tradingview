<div align="center">

# ⚡ Local Signals Pro

### Умный мониторинг криптосигналов с автоторговлей

<img src="local-signals-app/content/ui git.jpg" alt="Local Signals Pro" width="700">

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-Qt-green?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey)](../../releases)

</div>

---

## 📥 Установка

<table>
<tr>
<td width="50%">

### 🪟 Windows

1. Скачай **`LocalSignalsPro.exe`** из [Releases](../../releases)
2. Запусти — готово!

</td>
<td width="50%">

### 🍎 macOS

1. Скачай **`LocalSignalsPro.app.zip`** из [Releases](../../releases)
2. Распакуй и перемести в **Applications**
3. ПКМ → Открыть (первый запуск)

</td>
</tr>
</table>

<details>
<summary>🐍 Из исходников (все платформы)</summary>

```bash
cd local-signals-app
pip install -r requirements.txt
python run.py
```

</details>

---

## ✨ Возможности

<table>
<tr>
<td width="33%" align="center">

### 📊 Мониторинг
**10 монет** в реальном времени  
BTC • ETH • SOL • XRP • DOGE  
ADA • AVAX • LINK • SUI • WIF

</td>
<td width="33%" align="center">

### 🎯 Конфлюенс
**3 индикатора** для точности  
EMA Market Structure  
Smart Money Breakout  
Trend Targets

</td>
<td width="33%" align="center">

### 🤖 Автоторговля
**Bybit Terminal** встроен  
Автооткрытие позиций  
Автозакрытие по сигналу  
HTF фильтрация

</td>
</tr>
</table>

---

## 🔥 Как работает

```
┌─────────────────────────────────────────────────────────────┐
│  📈 Индикатор 1: EMA Market Structure    →  🟢 BULL        │
│  📈 Индикатор 2: Smart Money Breakout    →  🟢 BULL        │
│  📈 Индикатор 3: Trend Targets           →  🔴 BEAR        │
├─────────────────────────────────────────────────────────────┤
│  🎯 Конфлюенс: 2/3 BULL                  →  ✅ СИГНАЛ ЛОНГ │
│  📊 HTF фильтр: 4h тренд BULL            →  ✅ ПОДТВЕРЖДЁН │
└─────────────────────────────────────────────────────────────┘
                           ↓
              📱 Telegram уведомление
              🤖 Автооткрытие позиции
```

| Сила сигнала | Индикаторы | Действие |
|:------------:|:----------:|:--------:|
| 🔥 Сильный | 3/3 | Торгуем |
| ✅ Хороший | 2/3 | Торгуем |
| ❌ Слабый | 1/3 | Пропуск |

---

## 📱 Telegram алерты

Мгновенные уведомления с полной информацией:

```
🔥 BTCUSDT — ЛОНГ 📈

⚡ Сильный [███████████]
🟢 HTF (4h): бычий

🟢 EMA: Bull breakout  
🟢 SM: Smart money buy  
🔴 Trend: Consolidation

⏰ 14:32:15 | ТФ: 1h
```

---

## 🛠 Сборка

<details>
<summary>Windows (.exe)</summary>

```bash
pip install pyinstaller
pyinstaller LocalSignalsPro.spec
# → dist/LocalSignalsPro.exe
```

</details>

<details>
<summary>macOS (.app)</summary>

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name LocalSignalsPro run.py
# → dist/LocalSignalsPro.app
```

</details>

---

## 📋 Требования

- **Готовые сборки**: Windows 10+ / macOS 11+
- **Из исходников**: Python 3.10+, PySide6, ccxt

---

<div align="center">

**[⬇️ Скачать](../../releases)** · **[🐛 Баги](../../issues)** · **[💡 Идеи](../../discussions)**

</div>
