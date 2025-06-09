# Telegram Bot для продвижения стримов

## Установка
1. Клонировать репозиторий
2. Создать файл `.env` на основе `.env.example`
3. Установить зависимости:
```bash
pip install -r requirements.txt
```

## Запуск
```bash
python main.py
```

## Деплой на Render
1. Создать новый Worker Service
2. Подключить репозиторий
3. Добавить переменные окружения:
   - `TELEGRAM_BOT_TOKEN`
   - `CRYPTO_BOT_TOKEN`
   - `ADMIN_IDS`
4. Деploy