"""SQLite schema, connection helper, and first-run seeding."""

import sqlite3
from pathlib import Path

import seed_data

DB_PATH = Path(__file__).parent / "dsa_tracker.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'locked' CHECK(status IN ('locked','pending','active','done')),
    phase TEXT NOT NULL DEFAULT 'pen_paper' CHECK(phase IN ('pen_paper','implementation')),
    started_at TEXT,
    unlocked_weekend INTEGER NOT NULL DEFAULT 0,
    unlock_order INTEGER,
    note TEXT
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT,
    difficulty TEXT,
    round1_status TEXT NOT NULL DEFAULT 'not_started' CHECK(round1_status IN ('not_started','solved','failed')),
    round2_status TEXT NOT NULL DEFAULT 'not_started' CHECK(round2_status IN ('not_started','solved','failed')),
    current_round INTEGER NOT NULL DEFAULT 1,
    last_attempt_date TEXT,
    next_due_date TEXT,
    streak_stage INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    result TEXT NOT NULL CHECK(result IN ('solved','not_solved')),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS daily_assignment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    slot_type TEXT NOT NULL CHECK(slot_type IN ('revision','fresh')),
    round INTEGER NOT NULL,
    UNIQUE(date, question_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    is_new = not DB_PATH.exists()
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()

    row = conn.execute("SELECT COUNT(*) AS c FROM topics").fetchone()
    if row["c"] == 0:
        _seed(conn)
    if conn.execute("SELECT 1 FROM settings WHERE key='round1_complete'").fetchone() is None:
        conn.execute("INSERT INTO settings (key, value) VALUES ('round1_complete', '0')")
        conn.commit()
    conn.close()
    return is_new


def _seed(conn):
    for topic in seed_data.ACTIVE_TOPICS:
        cur = conn.execute(
            "INSERT INTO topics (name, status, phase, started_at, unlocked_weekend, unlock_order, note) "
            "VALUES (?, 'active', 'pen_paper', date('now'), 0, NULL, NULL)",
            (topic["name"],),
        )
        topic_id = cur.lastrowid
        for q in topic["questions"]:
            conn.execute(
                "INSERT INTO questions (topic_id, title, url) VALUES (?, ?, ?)",
                (topic_id, q["title"], q.get("url")),
            )

    for order, topic in enumerate(seed_data.LOCKED_TOPICS, start=1):
        cur = conn.execute(
            "INSERT INTO topics (name, status, phase, started_at, unlocked_weekend, unlock_order, note) "
            "VALUES (?, 'locked', 'pen_paper', NULL, 0, ?, ?)",
            (topic["name"], order, topic.get("note")),
        )
        topic_id = cur.lastrowid
        for q in topic["questions"]:
            conn.execute(
                "INSERT INTO questions (topic_id, title, url) VALUES (?, ?, ?)",
                (topic_id, q["title"], q.get("url")),
            )

    conn.commit()
