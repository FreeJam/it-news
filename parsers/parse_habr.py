#!/usr/bin/env python3
"""Parse Habr top daily articles — fetch all articles for the day, sort by rating."""
import json
import sys
import urllib.request
import urllib.error
import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'news.db')


def fetch_page(page=1, per_page=20):
    """Fetch one page from Habr API (sorted by date, daily period)."""
    url = (
        f"https://habr.com/kek/v2/articles/"
        f"?sort=date&period=daily&page={page}"
        f"&per_page={per_page}&fl=ru&hl=ru"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def clean_html(html_str):
    """Remove HTML tags from string."""
    import re
    if not html_str:
        return ""
    text = re.sub(r'<[^>]+>', '', html_str)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#x27;', "'")
    return text.strip()


def get_category(hubs):
    """Determine category from hubs."""
    if not hubs:
        return "tech"
    hub_titles = " ".join(h.get("title", "").lower() for h in hubs)

    dev_keywords = [
        "программирование", "разработка", "python", "javascript",
        "c++", "go ", "rust", "java", "devops", "администрирование",
        "linux", "docker", "kubernetes", "базы данных"
    ]
    if any(w in hub_titles for w in dev_keywords):
        return "dev"

    ai_keywords = [
        "искусственный интеллект", "ai", "машинное обучение",
        "нейросет", "deep learning", "ml ", "gpt", "llm"
    ]
    if any(w in hub_titles for w in ai_keywords):
        return "ai"

    security_keywords = [
        "безопасность", "информационная безопасность",
        "криптография", "шифрование", "хакер"
    ]
    if any(w in hub_titles for w in security_keywords):
        return "security"

    business_keywords = [
        "бизнес", "стартап", "финансы", "экономика",
        "маркетинг", "управление", "карьера"
    ]
    if any(w in hub_titles for w in business_keywords):
        return "business"

    return "tech"


def main():
    db_path = DB_PATH
    max_articles = int(sys.argv[1]) if len(sys.argv) > 1 else 50

    all_articles = []
    page = 1

    print(f"Fetching Habr daily articles (target top {max_articles} by rating)...", file=sys.stderr)

    while len(all_articles) < max_articles:
        try:
            data = fetch_page(page=page, per_page=20)
        except Exception as e:
            print(f"Error fetching page {page}: {e}", file=sys.stderr)
            break

        refs = data.get("publicationRefs", {})
        if not refs:
            break

        for art_id, ref in refs.items():
            stats = ref.get("statistics", {})
            hubs = ref.get("hubs", [])
            lead = ref.get("leadData", {})
            author_info = ref.get("author", {})

            score = stats.get("score", 0)
            comments = stats.get("commentsCount", 0)
            reading_count = stats.get("readingCount", 0)
            reading_time = ref.get("readingTime", 0)
            title = ref.get("titleHtml", "")
            # Published time — ISO format from Habr
            published_iso = ref.get("timePublished", "")
            article_url = f"https://habr.com/ru/articles/{art_id}/"
            author_name = author_info.get("fullname", "") or author_info.get("alias", "")
            author_alias = author_info.get("alias", "")

            # Clean lead text
            lead_text = clean_html(lead.get("textHtml", "")) if lead else ""
            if len(lead_text) > 300:
                lead_text = lead_text[:297] + "..."

            # Tags from hubs
            tags = [h.get("title", "") for h in hubs[:5]]
            category = get_category(hubs)

            # Day key = TODAY (when parser runs), not published date
            # This ensures articles appear on the day they're fetched
            day_key = datetime.now(timezone.utc).strftime('%Y-%m-%d')

            all_articles.append({
                "id": art_id,
                "source": "habr",
                "title": title,
                "url": article_url,
                "permalink": article_url,
                "lead": lead_text,
                "score": score,
                "comments": comments,
                "reading_time": reading_time,
                "author": author_name,
                "author_url": f"https://habr.com/ru/users/{author_alias}/" if author_alias else "",
                "hubs": tags,
                "category": category,
                "reading_count": reading_count,
                "published_at": published_iso,
                "day_key": day_key,
            })

        print(f"  Page {page}: {len(all_articles)} articles collected so far", file=sys.stderr)

        total_pages = data.get("pagesCount", 1)
        if page >= total_pages:
            break
        page += 1

    # Sort by score descending
    all_articles.sort(key=lambda x: x["score"], reverse=True)
    if len(all_articles) > max_articles:
        all_articles = all_articles[:max_articles]

    # Save to output JSON (for backward compatibility)
    output_json = os.path.join(os.path.dirname(db_path), "habr-data.json")
    output = {
        "source": "habr",
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "count": len(all_articles),
        "articles": all_articles,
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Save to SQLite
    if len(all_articles) > 0:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        fetched_at = datetime.now(timezone.utc).isoformat()
        for a in all_articles:
            cur.execute("""
                INSERT OR REPLACE INTO articles
                (id, source, title, title_ru, url, permalink, lead, score, comments,
                 category, subreddit, hubs, author, author_url, reading_time,
                 published_at, fetched_at, day_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"habr:{a['id']}",
                "habr",
                a["title"],
                a["title"],  # title_ru = title (Habr already in Russian)
                a["url"],
                a["permalink"],
                a["lead"],
                a["score"],
                a["comments"],
                a["category"],
                "",
                json.dumps(a.get("hubs", [])),
                a.get("author", ""),
                a.get("author_url", ""),
                a.get("reading_time", 0),
                a.get("published_at", ""),
                fetched_at,
                a.get("day_key", datetime.now(timezone.utc).strftime('%Y-%m-%d')),
            ))

        cur.execute("""
            INSERT INTO fetch_log (source, fetched_at, count, status)
            VALUES (?, ?, ?, ?)
        """, ("habr", fetched_at, len(all_articles), "ok"))

        conn.commit()
        conn.close()
        print(f"OK: {len(all_articles)} Habr articles saved to DB and {output_json}")
    else:
        print("No articles fetched.")


if __name__ == "__main__":
    main()