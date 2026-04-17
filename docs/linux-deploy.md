# Переезд на Linux и запас по нагрузке

## Что уже подготовлено в коде

- SQLite теперь открывается с `WAL`, `busy_timeout`, `synchronous=NORMAL` и увеличенным кэшем.
- Рассылки больше не сканируют всю таблицу подписок в каждом цикле.
  Теперь у подписки хранится `next_delivery_at`, и бот выбирает только реально просроченные доставки.
- Если накопилась очередь рассылок, бот сначала дренирует её батчами и только потом уходит в длинный polling.
- У изображений карт появился дисковый кэш `IMAGE_CACHE_DIR`, чтобы после рестартов и под нагрузкой не тянуть один и тот же арт заново.

## Рекомендуемая структура на сервере

```text
/opt/tarrot-crispy
  app/
  tests/
  docs/
  deploy/
  .env
  bot_data.sqlite3
  main.py
  requirements.txt
```

## Что поставить на Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip fonts-dejavu-core
```

Если хочешь более мягкий запасной шрифт для карточек, можно добавить:

```bash
sudo apt install -y fonts-liberation2
```

## Таймзона

Рассылки идут по локальному времени сервера, поэтому таймзона должна быть выставлена заранее:

```bash
sudo timedatectl set-timezone Europe/Moscow
timedatectl
```

## Первый запуск

```bash
cd /opt/tarrot-crispy
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m unittest discover -s tests
python main.py
```

## Переменные окружения

Минимально нужны:

```env
BOT_TOKEN=...
BOT_USERNAME=...
DATABASE_PATH=bot_data.sqlite3
IMAGE_CACHE_DIR=runtime/image-cache
SUBSCRIPTION_DISPATCH_BATCH_SIZE=200
```

Если используется `/ask`, добавь:

```env
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5-mini
```

## Запуск как сервиса

1. Создай системного пользователя:

```bash
sudo useradd --system --home /opt/tarrot-crispy --shell /usr/sbin/nologin tarotbot
sudo chown -R tarotbot:tarotbot /opt/tarrot-crispy
```

2. Скопируй unit:

```bash
sudo cp deploy/systemd/tarrot-crispy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tarrot-crispy
```

3. Проверка:

```bash
sudo systemctl status tarrot-crispy
journalctl -u tarrot-crispy -n 100 --no-pager
```

## Бэкапы

Локальный архив создаётся так:

```bash
python scripts/create_backup.py
```

Для регулярного бэкапа достаточно сохранять:

- `.env`
- `bot_data.sqlite3`
- папку `backups/` или внешний каталог с архивами

## Что выдержит текущая архитектура

Сейчас бот хорошо подходит для:

- сотен зарегистрированных пользователей;
- десятков запросов в минуту;
- умеренных ежедневных рассылок;
- редких AI-запросов `/ask`.

Первый реальный потолок будет не по CPU, а по архитектуре:

- один процесс обрабатывает апдейты последовательно;
- AI-запросы блокируют обработку остальных;
- SQLite остаётся хорошим выбором для одного процесса, но не для горизонтального масштабирования;
- Telegram- и OpenAI-запросы выполняются синхронно.

## Что делать перед серьёзной нагрузкой

Когда аудитория начнёт быстро расти, следующий порядок апгрейдов будет самым выгодным:

1. Перенести базу с SQLite на PostgreSQL.
2. Вынести тяжёлые сценарии (`/ask`, генерацию карточек, массовые рассылки) в отдельную очередь задач.
3. Разделить intake и workers: один процесс принимает апдейты, отдельные воркеры выполняют тяжёлую работу.
4. Добавить метрики и алерты по задержкам, ошибкам Telegram API и росту БД.
