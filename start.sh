#!/bin/bash
# IT-News startup script
# Запускает API-сервер и обновляет данные

BASEDIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$BASEDIR/api.log"

cd "$BASEDIR"

# Запускаем обновление данных
echo "$(date -Iseconds) — Running update..." >> "$LOG"
bash "$BASEDIR/update.sh" >> "$LOG" 2>&1

# Запускаем API-сервер
echo "$(date -Iseconds) — Starting API server..." >> "$LOG"
nohup python3 "$BASEDIR/api/api.py" 8018 >> "$LOG" 2>&1 &
echo $! > "$BASEDIR/api.pid"
echo "$(date -Iseconds) — API PID: $(cat $BASEDIR/api.pid)" >> "$LOG"
echo "IT-News started. API PID: $(cat $BASEDIR/api.pid)"