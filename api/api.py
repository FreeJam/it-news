#!/usr/bin/env python3
"""
IT-News API Server
Serves articles from SQLite DB with caching.
Endpoints:
  GET /api/articles?day=YYYY-MM-DD&source=all&category=all
  GET /api/days[?source=reddit|habr]
  GET /api/stats
  GET /api/health

Supports CORS for Telegram Mini App usage.
Run: python3 api.py [port]
Default port: 8018
"""
import http.server
import json
import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'news.db')
CORS_ORIGINS = [
    'https://t.me',
    'http://localhost',
    'http://127.0.0.1',
    'https://freejam.online',
    'https://it-news.freejam.online',
]
# Add custom origins from env (comma-separated)
_env_origins = os.environ.get('CORS_ORIGINS', '')
if _env_origins:
    CORS_ORIGINS.extend(o.strip() for o in _env_origins.split(',') if o.strip())

# Simple in-memory cache: {key: (data, expiry_timestamp)}
_cache = {}
_cache_ttl = 60  # seconds
_cache_lock = threading.Lock()


def cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry:
            data, expiry = entry
            if time.time() < expiry:
                return data
            del _cache[key]
    return None


def cache_set(key, data):
    with _cache_lock:
        _cache[key] = (data, time.time() + _cache_ttl)


def cache_invalidate():
    with _cache_lock:
        _cache.clear()


def get_db():
    """Get a thread-local database connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_days_available(source=None):
    conn = get_db()
    cur = conn.cursor()

    if source and source in ('reddit', 'habr'):
        cur.execute("""
            SELECT day_key, COUNT(*) as cnt FROM articles
            WHERE source=? GROUP BY day_key ORDER BY day_key DESC
        """, (source,))
    else:
        cur.execute("""
            SELECT day_key, COUNT(*) as cnt FROM articles
            GROUP BY day_key ORDER BY day_key DESC
        """)

    rows = cur.fetchall()
    conn.close()

    return [
        {'day': r['day_key'], 'count': r['cnt']}
        for r in rows
    ]


def get_articles(day=None, source='all', category='all'):
    """Query articles with optional filters."""
    conn = get_db()
    cur = conn.cursor()

    conditions = []
    params = []

    if day:
        conditions.append("day_key = ?")
        params.append(day)

    if source in ('reddit', 'habr'):
        conditions.append("source = ?")
        params.append(source)

    if category and category != 'all':
        conditions.append("category = ?")
        params.append(category)

    where = ''
    if conditions:
        where = 'WHERE ' + ' AND '.join(conditions)

    sql = f"""
        SELECT id, source, title, title_ru, url, permalink, lead,
               score, comments, category, subreddit, hubs,
               author, author_url, reading_time, published_at,
               fetched_at, day_key
        FROM articles {where}
        ORDER BY score DESC
    """

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    articles = []
    for r in rows:
        article = dict(r)
        # Parse hubs JSON string back to list
        if article.get('hubs'):
            try:
                article['hubs'] = json.loads(article['hubs'])
            except Exception:
                article['hubs'] = []
        else:
            article['hubs'] = []
        articles.append(article)

    return articles


def get_stats():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as total FROM articles")
    total = cur.fetchone()['total']

    cur.execute("SELECT COUNT(DISTINCT day_key) as days FROM articles")
    days = cur.fetchone()['days']

    cur.execute("SELECT source, COUNT(*) as cnt FROM articles GROUP BY source")
    by_source = {r['source']: r['cnt'] for r in cur.fetchall()}

    cur.execute("SELECT category, COUNT(*) as cnt FROM articles GROUP BY category")
    by_category = {r['category']: r['cnt'] for r in cur.fetchall()}

    cur.execute("""
        SELECT source, day_key, COUNT(*) as cnt FROM articles
        GROUP BY source, day_key ORDER BY day_key DESC LIMIT 7
    """)
    recent_days = {}
    for r in cur.fetchall():
        key = r['day_key']
        if key not in recent_days:
            recent_days[key] = {}
        recent_days[key][r['source']] = r['cnt']

    conn.close()

    return {
        'total_articles': total,
        'days_covered': days,
        'by_source': by_source,
        'by_category': by_category,
        'recent_days': recent_days,
        'db_path': DB_PATH,
        'cache_ttl': _cache_ttl,
    }


class APIHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for IT-News API."""

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def send_cors_headers(self):
        origin = self.headers.get('Origin', '')
        if any(origin.startswith(o) for o in CORS_ORIGINS):
            self.send_header('Access-Control-Allow-Origin', origin)
        else:
            # Allow first-party
            self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # --- Health check ---
        if path == '/api/health' or path == '/health':
            self.send_json({'status': 'ok', 'time': datetime.now(timezone.utc).isoformat()})
            return

        # --- Stats ---
        if path == '/api/stats':
            cache_key = '__stats__'
            cached = cache_get(cache_key)
            if cached:
                self.send_json(cached)
                return
            stats = get_stats()
            cache_set(cache_key, stats)
            self.send_json(stats)
            return

        # --- Days list ---
        if path == '/api/days':
            source = params.get('source', [None])[0]
            cache_key = f'__days__{source}'
            cached = cache_get(cache_key)
            if cached:
                self.send_json(cached)
                return
            days = get_days_available(source=source)
            cache_set(cache_key, days)
            self.send_json({'days': days, 'count': len(days)})
            return

        # --- Articles ---
        if path == '/api/articles':
            day = params.get('day', [None])[0]
            source = params.get('source', ['all'])[0]
            category = params.get('category', ['all'])[0]

            cache_key = f'__articles__{day}__{source}__{category}'
            cached = cache_get(cache_key)
            if cached:
                self.send_json(cached)
                return

            articles = get_articles(day=day, source=source, category=category)
            result = {
                'day': day,
                'source_filter': source,
                'category_filter': category,
                'count': len(articles),
                'articles': articles,
            }
            cache_set(cache_key, result)
            self.send_json(result)
            return

        # --- Cache clear (for update.sh) ---
        if path == '/api/clear-cache':
            cache_invalidate()
            self.send_json({'status': 'cache cleared'})
            return

        # --- 404 ---
        self.send_json({'error': 'Not found', 'available': [
            '/api/articles', '/api/days', '/api/stats', '/api/health'
        ]}, 404)

    def log_message(self, format, *args):
        """Log requests to stderr."""
        sys.stderr.write(f"[{self.address_string()}] {format % args}\n")


def run(port=8018):
    server = http.server.HTTPServer(('0.0.0.0', port), APIHandler)
    print(f"IT-News API listening on http://0.0.0.0:{port}")
    print(f"  /api/articles?day=YYYY-MM-DD&source=all&category=all")
    print(f"  /api/days?source=reddit")
    print(f"  /api/stats")
    print(f"  /api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8018
    run(port)