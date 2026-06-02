#!/usr/bin/env python3
"""Parse Reddit JSON and save to SQLite DB."""
import json
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'news.db')
TRANSLATE_DELAY = 0.3  # delay between translations to avoid rate limiting


def translate_text(text, source='en', target='ru'):
    """Translate text using Google Translate API."""
    try:
        encoded = urllib.parse.quote(text[:4500])
        url = (
            f'https://translate.googleapis.com/translate_a/single'
            f'?client=gtx&sl={source}&tl={target}&dt=t&q={encoded}'
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8')
            data = json.loads(raw)
            parts = [item[0] for item in data[0] if item[0]]
            return ' '.join(parts)
    except Exception as e:
        print(f"  Translation error: {e}", file=sys.stderr)
        return text


def get_category_and_desc(title_lower, title_ru):
    """Determine category and generate Russian description."""
    if any(w in title_lower for w in [
        'ai', 'artificial intelligence', 'gpt', 'llm', 'gemini', 'claude',
        'anthropic', 'openai', 'machine learning', 'neural', 'deepmind',
        'siri', 'intelligence', 'amodei'
    ]):
        cat = 'ai'
    elif any(w in title_lower for w in [
        'hack', 'security', 'privacy', 'data breach', 'cyber', 'surveillance',
        'encrypt', 'spy', 'tracking', 'sued', 'lawsuit', 'password',
        'stored', 'plaintext'
    ]):
        cat = 'security'
    elif any(w in title_lower for w in [
        'ipo', 'stock', 'company', 'startup', 'funding', 'revenue', 'profit',
        'acquisition', 'merger', 'bonus', 'pay', 'bonuses', 'settlement',
        'airlines'
    ]):
        cat = 'business'
    elif any(w in title_lower for w in [
        'programming', 'developer', 'python', 'javascript', 'java', 'go ',
        'rust', 'c++', 'devops', 'linux', 'docker', 'kubernetes', 'database'
    ]):
        cat = 'dev'
    else:
        cat = 'tech'

    desc_map = {
        'ai': {
            'data center': '🏗 Строительство AI-датацентров: конфликты корпораций с местными сообществами',
            'safety': '🛡 Безопасность AI: тестирование и регулирование искусственного интеллекта',
            'siri': '🤖 Apple Siri: судебный иск из-за невыполненных обещаний по AI',
            'chrome': '🌐 Google Chrome: AI-модель установлена без ведома пользователя',
            'search': '🔍 Google Search: AI теперь использует Reddit как источник',
            'driverless': '🚗 Беспилотные авто: новые правила регулирования',
            'default': '🤖 AI-новости: последние события в мире искусственного интеллекта'
        },
        'security': {
            'password': '🔐 Уязвимость: пароли хранятся в открытом виде',
            'fcc': '⚖️ Суд отклонил правила FCC',
            'edge': '🔒 Microsoft Edge: пароли загружаются в plaintext',
            'default': '🔒 Информационная безопасность: угрозы и уязвимости'
        },
        'business': {
            'spirit': '✈️ Spirit Airlines: работники теряют зарплату при бонусах руководства',
            'apple.*siri': '💰 Apple выплатит $250M за неработающий AI Siri',
            'spacex': '🚀 SpaceX IPO: новая корпоративная структура',
            'settlement': '💵 Судебное урегулирование: компенсация пользователям',
            'default': '🏢 IT-бизнес: корпоративные новости и сделки'
        },
        'tech': {
            'default': '📰 Технологические новости'
        },
        'dev': {
            'default': '⚙️ Разработка: новости программирования и инфраструктуры'
        }
    }

    cat_descs = desc_map.get(cat, desc_map['tech'])
    for key, desc in cat_descs.items():
        if key != 'default' and key in title_lower:
            return cat, desc
    return cat, cat_descs.get('default', '📰 Новость')


def parse_reddit_json(data):
    """Parse raw Reddit JSON into article dicts."""
    posts = data.get('data', {}).get('children', [])
    results = []

    for p in posts:
        d = p.get('data', {})
        if d.get('stickied'):
            continue

        title = d.get('title', '').replace('\n', ' ').strip()
        permalink = d.get('permalink', '')
        # Use Reddit's unique 'id' field directly
        reddit_id = d.get('id', '')
        if not reddit_id:
            # Fallback: extract from permalink
            parts = permalink.strip('/').split('/')
            reddit_id = parts[3] if len(parts) >= 4 and parts[2] == 'comments' else permalink
        article_id = f"reddit:{reddit_id}"

        url = d.get('url', '')
        score = d.get('score', 0)
        comments = d.get('num_comments', 0)
        subreddit = d.get('subreddit', 'technology')
        created_utc = d.get('created_utc', 0)

        # Human-readable time
        time_str = 'недавно'
        if created_utc:
            diff_h = int((time.time() - created_utc) / 3600)
            if diff_h < 1:
                time_str = 'менее часа назад'
            elif diff_h < 24:
                time_str = f'{diff_h} ч. назад'
            else:
                time_str = f'{diff_h // 24} дн. назад'

        # Category & description
        title_lower = title.lower()
        cat, desc_ru = get_category_and_desc(title_lower, '')

        # Translate title
        print(f"  Translating: {title[:60]}...", file=sys.stderr)
        title_ru = translate_text(title)
        time.sleep(TRANSLATE_DELAY)

        # Day key = TODAY (when parser runs), not published date
        # This ensures articles appear on the day they're fetched
        day_key = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        published_at = None
        if created_utc:
            published_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
            # day_key set above to current date

        results.append({
            'id': article_id,
            'source': 'reddit',
            'title': title,
            'title_ru': title_ru,
            'desc_ru': desc_ru,
            'url': url,
            'permalink': permalink,
            'score': score,
            'comments': comments,
            'category': cat,
            'subreddit': subreddit,
            'time': time_str,
            'published_at': published_at,
            'day_key': day_key,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
        })

    return results


def main():
    if len(sys.argv) < 3:
        print("Usage: parse_reddit.py <input_json> <db_path>", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else DB_PATH

    # Ensure DB directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Read Reddit JSON
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articles = parse_reddit_json(data)
    print(f"  Parsed {len(articles)} Reddit articles", file=sys.stderr)

    # Save to SQLite
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    for a in articles:
        cur.execute("""
            INSERT OR REPLACE INTO articles
            (id, source, title, title_ru, url, permalink, lead, score, comments,
             category, subreddit, hubs, author, author_url, reading_time,
             published_at, fetched_at, day_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            a['id'], a['source'], a['title'], a['title_ru'], a['url'],
            a['permalink'], a['desc_ru'], a['score'], a['comments'],
            a['category'], a['subreddit'], None, '', '', 0,
            a['published_at'], a['fetched_at'], a['day_key'],
        ))

    # Log fetch
    cur.execute("""
        INSERT INTO fetch_log (source, fetched_at, count, status)
        VALUES (?, ?, ?, ?)
    """, ('reddit', datetime.now(timezone.utc).isoformat(), len(articles), 'ok'))

    conn.commit()
    conn.close()
    print(f"OK: {len(articles)} Reddit articles saved to {db_path}")


if __name__ == '__main__':
    main()