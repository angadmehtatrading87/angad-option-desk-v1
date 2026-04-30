import os
import sqlite3
from datetime import datetime, timezone
import feedparser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")

RSS_FEEDS = [
    ("Reuters Markets", "https://feeds.reuters.com/reuters/businessNews"),
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
    ("CNBC World", "https://www.cnbc.com/id/100727362/device/rss/rss.html"),
    ("MarketWatch Top", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
]

RISK_OFF_KEYWORDS = [
    "war", "attack", "missile", "sanction", "tariff", "recession", "crisis",
    "bank failure", "default", "inflation shock", "hawkish", "rate hike",
    "selloff", "volatility", "geopolitical", "conflict", "oil spike", "panic"
]

RISK_ON_KEYWORDS = [
    "rally", "cooling inflation", "rate cut", "soft landing", "deal",
    "ceasefire", "stimulus", "growth", "beat estimates", "upgrade",
    "risk appetite", "bullish", "recovery"
]

def init_news_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS news_headlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT,
            published TEXT,
            fetched_at TEXT NOT NULL,
            UNIQUE(source, title)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS news_macro_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at TEXT NOT NULL,
            headline_count INTEGER NOT NULL,
            risk_on_score INTEGER NOT NULL,
            risk_off_score INTEGER NOT NULL,
            macro_regime TEXT NOT NULL,
            summary TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

def fetch_latest_headlines(limit_per_feed=10):
    init_news_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    headlines = []

    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            entries = feed.entries[:limit_per_feed]

            for e in entries:
                title = (getattr(e, "title", "") or "").strip()
                link = getattr(e, "link", None)
                published = getattr(e, "published", None)

                if not title:
                    continue

                cur.execute("""
                    INSERT OR IGNORE INTO news_headlines (
                        source, title, link, published, fetched_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    source_name,
                    title,
                    link,
                    published,
                    datetime.now(timezone.utc).isoformat()
                ))

                headlines.append({
                    "source": source_name,
                    "title": title,
                    "link": link,
                    "published": published
                })
        except Exception:
            continue

    conn.commit()
    conn.close()

    return headlines

def score_macro_from_headlines(headlines):
    risk_on = 0
    risk_off = 0

    for h in headlines:
        title = (h.get("title") or "").lower()

        for kw in RISK_OFF_KEYWORDS:
            if kw in title:
                risk_off += 1

        for kw in RISK_ON_KEYWORDS:
            if kw in title:
                risk_on += 1

    if risk_off >= risk_on + 3:
        regime = "RISK_OFF"
        summary = "Headline flow is skewing defensive / risk-off."
    elif risk_on >= risk_off + 3:
        regime = "RISK_ON"
        summary = "Headline flow is skewing constructive / risk-on."
    else:
        regime = "NEUTRAL"
        summary = "Headline flow is mixed / neutral."

    return {
        "headline_count": len(headlines),
        "risk_on_score": risk_on,
        "risk_off_score": risk_off,
        "macro_regime": regime,
        "summary": summary
    }

def refresh_news_macro():
    init_news_db()
    headlines = fetch_latest_headlines()
    scored = score_macro_from_headlines(headlines)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO news_macro_snapshot (
            fetched_at, headline_count, risk_on_score, risk_off_score, macro_regime, summary
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        scored["headline_count"],
        scored["risk_on_score"],
        scored["risk_off_score"],
        scored["macro_regime"],
        scored["summary"]
    ))
    conn.commit()
    conn.close()

    return {
        "snapshot": scored,
        "headlines": headlines[:20]
    }

def latest_news_macro():
    init_news_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM news_macro_snapshot
        ORDER BY id DESC
        LIMIT 1
    """)
    snap = cur.fetchone()

    cur.execute("""
        SELECT source, title, link, published, fetched_at
        FROM news_headlines
        ORDER BY id DESC
        LIMIT 20
    """)
    headlines = [dict(r) for r in cur.fetchall()]

    conn.close()

    return {
        "snapshot": dict(snap) if snap else None,
        "headlines": headlines
    }
