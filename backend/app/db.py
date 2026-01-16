from __future__ import annotations
import json, logging, sqlite3, time
from pathlib import Path
from typing import Any, Dict, Tuple
from app.settings import settings

logger = logging.getLogger("sevasetu")

def connect() -> sqlite3.Connection:
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    # M1 / local-dev friendly SQLite pragmas (better concurrency, fewer "database is locked" issues)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        logger.exception("Failed to set SQLite pragmas")
    logger.info("DB connected path=%s", db_path)
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
    logger.info("DB initialized")


# --- Scheme loading utilities ---

def _schemes_json_path() -> Path:
    """Return schemes.json path.

    Project layout (current): backend/app/db.py and backend/app/data/schemes.json OR backend/app/data may not exist.
    In your repo, the file is at: backend/app/data/schemes.json OR app/data/schemes.json depending on where you run from.
    We support both, preferring the repo-local `app/data/schemes.json` (same folder level as `app/`).
    """
    here = Path(__file__).resolve()
    # 1) Preferred: sibling `data/schemes.json` next to this file (backend/app/data/schemes.json)
    p1 = here.parent / "data" / "schemes.json"
    # 2) Fallback: `app/data/schemes.json` relative to backend root (when running inside backend/)
    # Example: backend/app/db.py -> backend/app/data/schemes.json already covered by p1
    # but if structure differs, try: backend/../app/data/schemes.json
    p2 = here.parents[1] / "app" / "data" / "schemes.json"
    return p1 if p1.exists() else p2


def ensure_schemes_loaded(conn: sqlite3.Connection) -> None:
    """Loads schemes from app/data/schemes.json into SQLite once (idempotent)."""
    cur = conn.cursor()
    row = cur.execute("SELECT COUNT(1) FROM schemes WHERE scheme_id IS NOT NULL AND scheme_id != ''").fetchone()
    existing = int(row[0] if row and row[0] is not None else 0)
    if existing > 0:
        return

    path = _schemes_json_path()
    print(f"[db] Loading schemes from: {path}")
    if not path.exists():
        raise FileNotFoundError(f"schemes.json not found at {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("schemes.json must be a JSON array")

    for scheme in data:
        if isinstance(scheme, dict):
            save_scheme(conn, scheme)

    # Final commit safety (save_scheme already commits, but keep this harmless)
    conn.commit()

def get_or_create_session(conn: sqlite3.Connection, session_id: str, language: str):
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    if row:
        logger.debug("Session loaded session_id=%s", session_id)
        return json.loads(row["profile_json"]), json.loads(row["pending_json"]), json.loads(row["state_json"])
    profile = {"session_id": session_id, "name": None, "age": None, "gender": None, "state": None, "income_annual": None, "occupation": None}
    pending = {}
    state = {"last_candidates": [], "last_eligibility": {}, "tool_trace": []}
    save_session(conn, session_id, language, profile, pending, state)
    logger.info("Session created session_id=%s", session_id)
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
    logger.debug("Session saved session_id=%s", session_id)

def add_message(conn: sqlite3.Connection, session_id: str, role: str, text: str) -> None:
    cur = conn.cursor()
    cur.execute("INSERT INTO messages(session_id, role, text, ts) VALUES(?,?,?,?)", (session_id, role, text, time.time()))
    conn.commit()
    logger.debug("Message saved session_id=%s role=%s chars=%d", session_id, role, len(text or ""))

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
    logger.debug("Scheme saved scheme_id=%s", scheme_id)

def get_scheme_by_id(conn: sqlite3.Connection, scheme_id: str):
    if not scheme_id:
        return None
    cur = conn.cursor()
    cur.execute("SELECT scheme_json FROM schemes WHERE scheme_id = ?", (scheme_id,))
    row = cur.fetchone()
    if not row:
        logger.debug("Scheme not found scheme_id=%s", scheme_id)
        return None
    logger.debug("Scheme loaded scheme_id=%s", scheme_id)
    return json.loads(row[0])
