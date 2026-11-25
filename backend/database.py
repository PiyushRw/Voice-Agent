import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import DATA

def now():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def db():
    con = sqlite3.connect(DATA / "sales.db", timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        with con:
            yield con
    finally:
        con.close()

def init():
    with db() as con:
        con.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS calls(
            id TEXT PRIMARY KEY, started TEXT,
            ended TEXT, mode TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY, call_id TEXT REFERENCES calls(id), role TEXT, content TEXT,
            language TEXT, timestamp TEXT, interrupted INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS leads(
            call_id TEXT PRIMARY KEY REFERENCES calls(id), details TEXT, score INTEGER, status TEXT);
        CREATE TABLE IF NOT EXISTS call_analysis(
            call_id TEXT PRIMARY KEY REFERENCES calls(id), summary TEXT, sentiment TEXT,
            objections TEXT, outcome TEXT, next_action TEXT);
        CREATE INDEX IF NOT EXISTS messages_call ON messages(call_id,id);
        """)

def add_message(call_id, role, content, language="en", interrupted=False):
    with db() as con:
        con.execute("INSERT INTO messages(call_id,role,content,language,timestamp,interrupted) VALUES(?,?,?,?,?,?)",
                    (call_id, role, content, language, now(), int(interrupted)))

def history(call_id):
    with db() as con:
        return [dict(row) for row in con.execute(
            "SELECT role,content,language,timestamp,interrupted FROM messages WHERE call_id=? ORDER BY id",
            (call_id,))]
