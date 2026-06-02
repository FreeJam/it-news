# IT News — Reddit + Habr Aggregator

IT-News — агрегатор новостей из Reddit (r/technology) и Хабра с переводом на русский язык. Включает API-сервер, Telegram Mini App (PWA) и Telegram-бота.

## Структура проекта

```
├── api/                  # API-сервер (Python, порт 8018)
│   └── api.py           # REST API: /api/articles, /api/days, /api/stats
├── parsers/             # Парсеры источников
│   ├── parse_reddit_rss.py  # Reddit RSS → SQLite + перевод
│   ├── parse_habr.py        # Хабр API → SQLite
│   └── create_tma.py        # Генерация Telegram Mini App
├── it-news-app/         # Фронтенд (PWA)
│   ├── index.html       # Главная страница приложения
│   └── bot.py           # Telegram-бот (long polling)
├── tma/                 # Telegram Mini App (генерируется автоматически)
├── icons/               # Иконки приложения
├── update.sh            # Скрипт обновления данных (Reddit + Habr)
├── start.sh             # Скрипт запуска API
├── app.js               # Клиентский JS (лендинг)
├── style.css            # Стили лендинга
└── index.html           # Лендинг
```

## Быстрый старт

### 1. Клонирование

```bash
git clone https://github.com/FreeJam/it-news.git /var/www/html/it-news
cd /var/www/html/it-news
```

### 2. Установка зависимостей

```bash
# Python 3.8+ (стандартная библиотека, внешних зависимостей нет)
python3 --version

# Для Telegram-бота:
pip3 install python-dotenv
```

### 3. Настройка

```bash
# Скопировать пример конфигурации
cp .env.example .env

# Отредактировать .env — указать токен бота
nano .env
```

### 4. Первый запуск

```bash
# Создать БД и заполнить данными
bash update.sh

# Запустить API-сервер
bash start.sh

# Проверить работу
curl http://127.0.0.1:8018/api/stats
```

### 5. Nginx

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8018;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /it-news-app/ {
    alias /var/www/html/it-news/it-news-app/;
    try_files $uri $uri/ /it-news-app/index.html;
}
```

### 6. Systemd (автозапуск API)

```bash
# Создать /etc/systemd/system/it-news.service:
cat > /etc/systemd/system/it-news.service << 'EOF'
[Unit]
Description=IT News API Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/var/www/html/it-news
ExecStart=/usr/bin/python3 /var/www/html/it-news/api/api.py 8018
Restart=always
RestartSec=5
StandardOutput=append:/var/www/html/it-news/api.log
StandardError=append:/var/www/html/it-news/api.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now it-news
```

### 7. Cron (обновление данных + watchdog)

```bash
# Обновление каждый час
0 * * * * cd /var/www/html/it-news && bash update.sh >> /var/www/html/it-news/cron.log 2>&1

# Watchdog каждые 5 минут
*/5 * * * * /root/scripts/it-news-watchdog.sh
```

### 8. Watchdog-скрипт

```bash
mkdir -p /root/scripts
cat > /root/scripts/it-news-watchdog.sh << 'WATCHEOF'
#!/bin/bash
API_URL="http://127.0.0.1:8018/api/stats"
LOG="/var/www/html/it-news/watchdog.log"
MAX_LOG_LINES=200

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$API_URL" 2>/dev/null)

if [ "$HTTP_CODE" = "200" ]; then
    exit 0
fi

echo "$(date -Iseconds) — API down (HTTP $HTTP_CODE), restarting..." >> "$LOG"
systemctl restart it-news 2>/dev/null || true
pkill -f "api/api.py" 2>/dev/null || true
sleep 2
cd /var/www/html/it-news
nohup python3 api/api.py 8018 >> api.log 2>&1 &
echo $! > api.pid
echo "$(date -Iseconds) — Restarted, new PID: $(cat api.pid 2>/dev/null)" >> "$LOG"

if [ -f "$LOG" ]; then
    LINES=$(wc -l < "$LOG")
    if [ "$LINES" -gt "$MAX_LOG_LINES" ]; then
        tail -n "$MAX_LOG_LINES" "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"
    fi
fi
WATCHEOF
chmod +x /root/scripts/it-news-watchdog.sh
```

## API Endpoints

| Endpoint | Описание |
|----------|----------|
| `GET /api/health` | Проверка работоспособности |
| `GET /api/stats` | Статистика (всего статей, по источникам) |
| `GET /api/days?source=reddit\|habr` | Список дней с новостями |
| `GET /api/articles?day=YYYY-MM-DD&source=all&category=all` | Новости с фильтрами |
| `GET /api/clear-cache` | Очистка кэша |

## Переменные окружения (.env)

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | Токен Telegram-бота (получить у @BotFather) |

## Обновление

```bash
cd /var/www/html/it-news
git pull
systemctl restart it-news
```
