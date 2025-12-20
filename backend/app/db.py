from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
from typing import Any, Dict, Tuple
from app.settings import settings

def connect() -> sqlite3.Connection:
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions(
      session_id TEXT PRIMARY KEY,
      language TEXT NOT NULL,
      profile_json TEXT NOT NULL,
      pending_json TEXT NOT NULL,
      state_json TEXT NOT NULL,
      updated_at REAL NOT NULL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL,
      role TEXT NOT NULL,
      text TEXT NOT NULL,
      ts REAL NOT NULL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS schemes(
      scheme_id TEXT PRIMARY KEY,
      scheme_json TEXT NOT NULL,
      updated_at REAL NOT NULL
    )""")
    conn.commit()

def get_or_create_session(conn: sqlite3.Connection, session_id: str, language: str):
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    if row:
        return json.loads(row["profile_json"]), json.loads(row["pending_json"]), json.loads(row["state_json"])
    profile = {"session_id": session_id, "name": None, "age": None, "gender": None, "state": None, "income_annual": None, "occupation": None}
    pending = {}
    state = {"last_candidates": [], "last_eligibility": {}, "tool_trace": []}
    save_session(conn, session_id, language, profile, pending, state)
    return profile, pending, state

def save_session(conn: sqlite3.Connection, session_id: str, language: str, profile: Dict[str, Any], pending: Dict[str, Any], state: Dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
      """INSERT INTO sessions(session_id, language, profile_json, pending_json, state_json, updated_at)
         VALUES(?,?,?,?,?,?)
         ON CONFLICT(session_id) DO UPDATE SET
           language=excluded.language,
           profile_json=excluded.profile_json,
           pending_json=excluded.pending_json,
           state_json=excluded.state_json,
           updated_at=excluded.updated_at
      """,
      (session_id, language,
       json.dumps(profile, ensure_ascii=False),
       json.dumps(pending, ensure_ascii=False),
       json.dumps(state, ensure_ascii=False),
       time.time())
    )
    conn.commit()

def add_message(conn: sqlite3.Connection, session_id: str, role: str, text: str) -> None:
    cur = conn.cursor()
    cur.execute("INSERT INTO messages(session_id, role, text, ts) VALUES(?,?,?,?)", (session_id, role, text, time.time()))
    conn.commit()

def save_scheme(conn: sqlite3.Connection, scheme: Dict[str, Any]) -> None:
    scheme_id = (scheme or {}).get("scheme_id")
    if not scheme_id:
        return
    cur = conn.cursor()
    cur.execute(
      """INSERT INTO schemes(scheme_id, scheme_json, updated_at)
         VALUES(?,?,?)
         ON CONFLICT(scheme_id) DO UPDATE SET
           scheme_json=excluded.scheme_json,
           updated_at=excluded.updated_at
      """,
      (scheme_id, json.dumps(scheme, ensure_ascii=False), time.time())
    )
    conn.commit()

def get_scheme_by_id(conn: sqlite3.Connection, scheme_id: str):
    if not scheme_id:
        return None
    cur = conn.cursor()
    cur.execute("SELECT scheme_json FROM schemes WHERE scheme_id = ?", (scheme_id,))
    row = cur.fetchone()
    if not row:
        return None
    return json.loads(row[0])
