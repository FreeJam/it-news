#!/bin/bash
# IT-News: автоматическая развёртка на новом сервере
# Запуск: bash setup.sh
set -e

REPO_URL="https://github.com/FreeJam/it-news.git"
INSTALL_DIR="${INSTALL_DIR:-/var/www/html/it-news}"
DOMAIN="${DOMAIN:-freejam.online}"

echo "=== IT-News Setup ==="
echo ""

# --- Проверка прав ---
if [ "$(id -u)" -ne 0 ]; then
    echo "Ошибка: запускайте от root (sudo bash setup.sh)"
    exit 1
fi

# --- Зависимости ---
echo "[1/7] Установка зависимостей..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip nginx curl git
pip3 install -q python-dotenv 2>/dev/null || true

# --- Клонирование ---
echo "[2/7] Клонирование репозитория..."
if [ -d "$INSTALL_DIR" ]; then
    echo "  Директория $INSTALL_DIR существует. Обновляем..."
    cd "$INSTALL_DIR"
    git pull
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# --- .env ---
echo "[3/7] Настройка окружения..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  ⚠️  Создан .env — отредактируйте токен бота:"
    echo "     nano $INSTALL_DIR/.env"
else
    echo "  .env уже существует, пропускаем."
fi

# --- Первое обновление данных ---
echo "[4/7] Первичное обновление данных (Reddit + Habr)..."
bash update.sh

# --- Systemd ---
echo "[5/7] Настройка systemd..."
cat > /etc/systemd/system/it-news.service << EOF
[Unit]
Description=IT News API Server
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/api/api.py 8018
Restart=always
RestartSec=5
StandardOutput=append:$INSTALL_DIR/api.log
StandardError=append:$INSTALL_DIR/api.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now it-news
echo "  it-news.service запущен."

# --- Watchdog ---
echo "[6/7] Установка watchdog..."
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

# --- Cron ---
echo "[7/7] Настройка cron..."
(crontab -l 2>/dev/null | grep -v "it-news"; echo "0 * * * * cd $INSTALL_DIR && bash update.sh >> $INSTALL_DIR/cron.log 2>&1"; echo "*/5 * * * * /root/scripts/it-news-watchdog.sh") | crontab -

# --- Проверка ---
echo ""
echo "=== Проверка ==="
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8018/api/health 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ API работает: http://127.0.0.1:8018/api/health"
else
    echo "⚠️  API не отвечает (HTTP $HTTP_CODE). Проверьте: systemctl status it-news"
fi

echo ""
echo "=== Готово! ==="
echo ""
echo "Что сделать вручную:"
echo "  1. Настроить Nginx (см. README.md раздел 'Nginx')"
echo "  2. Указать BOT_TOKEN в $INSTALL_DIR/.env"
echo "  3. Запустить бота: cd $INSTALL_DIR/it-news-app && python3 bot.py &"
echo ""
echo "Команды:"
echo "  Логи API:    tail -f $INSTALL_DIR/api.log"
echo "  Статус:      systemctl status it-news"
echo "  Перезапуск:  systemctl restart it-news"
echo "  Обновить:    cd $INSTALL_DIR && bash update.sh"
