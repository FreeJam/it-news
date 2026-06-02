#!/bin/bash
# IT-News — Fetch Reddit (RSS) + Habr, save to SQLite, invalidate API cache
set -e

BASEDIR="/var/www/freejam.online/html/it-news"

# Random delay 0-300 seconds (0-5 min) to avoid rate limiting
SLEEP_SEC=$((RANDOM % 301))
echo "[$(date -Iseconds)] Sleeping ${SLEEP_SEC}s before update..."
sleep "$SLEEP_SEC"

echo "[$(date -Iseconds)] === IT-News Update ==="

# --- Reddit (RSS fallback — JSON API is blocked) ---
echo "Fetching Reddit /r/technology via RSS..."
RSS_FILE=$(mktemp)
HTTP_CODE=$(curl -s -o "$RSS_FILE" -w "%{http_code}" \
  -H "User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0" \
  -H "Accept: application/rss+xml, application/xml, text/xml" \
  "https://www.reddit.com/r/technology/.rss?limit=30")

if [ "$HTTP_CODE" = "200" ]; then
  python3 "$BASEDIR/parsers/parse_reddit_rss.py" "$BASEDIR/db/news.db"
  echo "  Reddit done."
else
  echo "  WARNING: Reddit RSS HTTP $HTTP_CODE"
fi
rm -f "$RSS_FILE"

# --- Habr ---
echo "Fetching Habr daily top..."
python3 "$BASEDIR/parsers/parse_habr.py" 50

# --- Invalidate API cache ---
if curl -s "http://127.0.0.1:8018/api/clear-cache" | grep -q "ok"; then
  echo "  API cache cleared."
else
  echo "  (API not running or cache clear skipped)"
fi

echo "[$(date -Iseconds)] Done."
