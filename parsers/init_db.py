#!/usr/bin/env python3
"""DB initialization — create tables if not exists."""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'news.db')

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    title_ru    TEXT,
    url         TEXT NOT NULL,
    permalink   TEXT,
    lead        TEXT,
    score       INTEGER DEFAULT 0,
    comments    INTEGER DEFAULT 0,
    category    TEXT DEFAULT 'tech',
    subreddit   TEXT,
    hubs        TEXT,
    author      TEXT,
    author_url  TEXT,
    reading_time INTEGER DEFAULT 0,
    published_at TEXT,
    fetched_at  TEXT NOT NULL,
    day_key     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    count       INTEGER NOT NULL,
    status      TEXT DEFAULT 'ok',
    error_msg   TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_day_key ON articles(day_key);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_fetch_log_source ON fetch_log(source);
"""


def init_db(db_path=None):
    """Create tables if they don't exist."""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(CREATE_TABLES_SQL)
    conn.close()
    return path


if __name__ == '__main__':
    path = init_db()
    print(f"DB initialized: {path}")
