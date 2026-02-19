# Bybit Demo Setup (legacy filename)

Этот файл оставлен для совместимости по имени, но инструкция ниже для текущего режима проекта: `BYBIT_DEMO`.

## 1. Создать Bybit Demo API ключ

1. Открой `https://www.bybit.com/app/user/api-management`
2. Переключи аккаунт в режим `Demo Trading`
3. Создай `System-generated API Key`
4. Права: `Read-Write` и доступ к ордерам
5. Скопируй `API Key` и `Secret`

## 2. Вставить ключи в проект

Открой `local-signals-app/config.json` и укажи:

```json
{
  "exchange": "BYBIT_DEMO",
  "demo_mode": true,
  "api_key": "YOUR_BYBIT_DEMO_API_KEY",
  "api_secret": "YOUR_BYBIT_DEMO_API_SECRET"
}
```

## 3. Проверить подключение

```bash
python local-signals-app/test_bybit_api.py
```

Ожидаемый результат: вывод `OK: Bybit Demo API works`.

## 4. Запуск терминала

```bash
python local-signals-app/run.py
```

В интерфейсе должен быть статус подключения `Bybit Demo`.
