r"""
conv_archive — Claude Code conversation archiver
~/.claude/projects/*.jsonl → SQLite (FTS5 full-text search)

Usage:
  python conv_archive.py --scan              # scan all .jsonl files
  python conv_archive.py --file <path>       # import a single file
  python conv_archive.py --search <query>    # FTS5 search (BM25 ranking)
  python conv_archive.py --search "<query> 어제"  # date filter: 오늘/어제/그제/이번주/지난주
  python conv_archive.py --session <id>      # print full session
  python conv_archive.py --export <id> [YYYY-MM-DD]  # export session to stdout
  python conv_archive.py --rebuild-fts       # rebuild FTS5 index

Path overrides (env or flag):
  CONV_ARCHIVE_DB    / --db   <path>   default: ~/.conv_archive/conv_archive.db
  CONV_ARCHIVE_ROOT  / --root <path>   default: ~/.claude/projects
"""

import json
import sqlite3
import sys
import os
import glob
from pathlib import Path
from datetime import datetime, timedelta

# ── defaults ────────────────────────────────────────────────────────────────
_DEFAULT_DB   = Path.home() / ".conv_archive" / "conv_archive.db"
_DEFAULT_ROOT = Path.home() / ".claude" / "projects"

DB_PATH    = Path(os.environ.get("CONV_ARCHIVE_DB",   str(_DEFAULT_DB)))
JSONL_ROOT = Path(os.environ.get("CONV_ARCHIVE_ROOT", str(_DEFAULT_ROOT)))


# ── db setup ─────────────────────────────────────────────────────────────────
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            project TEXT,
            created_at TEXT,
            updated_at TEXT,
            slug TEXT,
            jsonl_path TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            msg_uuid TEXT UNIQUE,
            ts TEXT,
            role TEXT,
            content TEXT
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_session_msg ON messages(session_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_ts ON messages(ts)")
    db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            content,
            session_id UNINDEXED,
            msg_id UNINDEXED,
            tokenize='unicode61'
        )
    """)
    db.commit()
    return db


# ── content extraction ───────────────────────────────────────────────────────
def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return " ".join(p for p in parts if p)
    return ""


# ── import ───────────────────────────────────────────────────────────────────
def import_jsonl(db, jsonl_path):
    if not os.path.exists(jsonl_path):
        return 0

    session_id = project = slug = created_at = updated_at = None
    imported = 0

    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            if session_id is None:
                session_id = obj.get("sessionId")
                cwd = obj.get("cwd", "")
                project = os.path.basename(cwd) if cwd else os.path.basename(os.path.dirname(jsonl_path))
                slug = obj.get("slug", "")

            ts = obj.get("timestamp", "")
            if created_at is None:
                created_at = ts
            if ts:
                updated_at = ts

            msg_type = obj.get("type")
            msg_uuid  = obj.get("uuid", "")
            msg       = obj.get("message", {})
            role      = msg.get("role", "")

            if msg_type not in ("assistant", "user") or role not in ("assistant", "user"):
                continue

            content_raw = msg.get("content", [])
            if role == "assistant":
                text = extract_text(content_raw)
            else:
                if isinstance(content_raw, list):
                    parts = [i.get("text", "") for i in content_raw
                             if isinstance(i, dict) and i.get("type") == "text"]
                    text = " ".join(p for p in parts if p)
                else:
                    text = str(content_raw)

            if not text or not text.strip():
                continue

            try:
                cur = db.execute(
                    "INSERT OR IGNORE INTO messages (session_id, msg_uuid, ts, role, content) VALUES (?,?,?,?,?)",
                    (session_id, msg_uuid, ts, role, text.strip())
                )
                if cur.lastrowid and cur.rowcount > 0:
                    db.execute(
                        "INSERT INTO messages_fts (content, session_id, msg_id) VALUES (?,?,?)",
                        (text.strip(), session_id, cur.lastrowid)
                    )
                    imported += 1
            except Exception:
                pass

    if session_id:
        db.execute("""
            INSERT INTO sessions (session_id, project, created_at, updated_at, slug, jsonl_path)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET updated_at=excluded.updated_at, jsonl_path=excluded.jsonl_path
        """, (session_id, project, created_at, updated_at, slug, jsonl_path))
        db.commit()

    return imported


# ── commands ─────────────────────────────────────────────────────────────────
def cmd_scan():
    db = get_db()
    pattern = str(JSONL_ROOT / "**" / "*.jsonl")
    files = glob.glob(pattern, recursive=True)
    total = 0
    for f in files:
        n = import_jsonl(db, f)
        if n > 0:
            print(f"[import] {os.path.basename(f)}: {n}")
            total += n
    print(f"[done] {len(files)} files, {total} messages")
    db.close()


def cmd_file(path):
    db = get_db()
    n = import_jsonl(db, path)
    print(f"[done] {n} messages")
    db.close()


# ── date-aware search ────────────────────────────────────────────────────────
DATE_KEYWORDS = {
    "오늘": 0,   "today": 0,
    "어제": -1,  "yesterday": -1,
    "그제": -2,
    "이번주": -7,  "thisweek": -7,
    "지난주": -14, "lastweek": -14,
}

def parse_query(raw):
    today = datetime.now().date()
    tokens = raw.split()
    date_from = date_to = None
    terms = []
    for tok in tokens:
        if tok in DATE_KEYWORDS:
            delta = DATE_KEYWORDS[tok]
            if tok in ("이번주", "thisweek"):
                date_from = str(today + timedelta(days=delta))
                date_to   = str(today + timedelta(days=1))
            elif tok in ("지난주", "lastweek"):
                date_from = str(today + timedelta(days=-14))
                date_to   = str(today + timedelta(days=-7))
            else:
                target    = today + timedelta(days=delta)
                date_from = str(target)
                date_to   = str(target + timedelta(days=1))
        else:
            terms.append(tok)
    fts_query = " ".join(f'"{w}"' for w in terms if w) if terms else None
    return fts_query, date_from, date_to


def cmd_search(keyword, limit=20):
    """FTS5 full-text search with optional date filter."""
    db = get_db()
    if not keyword.strip():
        print("[search] provide a keyword")
        return

    fts_query, date_from, date_to = parse_query(keyword)

    if fts_query and date_from:
        rows = db.execute("""
            SELECT m.session_id, m.ts, m.role, m.content, s.project, s.slug
            FROM messages_fts f
            JOIN messages m ON m.id = f.msg_id
            JOIN sessions s ON s.session_id = f.session_id
            WHERE messages_fts MATCH ? AND m.ts >= ? AND m.ts < ?
            ORDER BY rank LIMIT ?
        """, (fts_query, date_from, date_to, limit)).fetchall()
    elif fts_query:
        rows = db.execute("""
            SELECT m.session_id, m.ts, m.role, m.content, s.project, s.slug
            FROM messages_fts f
            JOIN messages m ON m.id = f.msg_id
            JOIN sessions s ON s.session_id = f.session_id
            WHERE messages_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
    elif date_from:
        rows = db.execute("""
            SELECT m.session_id, m.ts, m.role, m.content, s.project, s.slug
            FROM messages m
            JOIN sessions s ON s.session_id = m.session_id
            WHERE m.ts >= ? AND m.ts < ?
            ORDER BY m.ts DESC LIMIT ?
        """, (date_from, date_to, limit)).fetchall()
    else:
        print("[search] provide a keyword")
        db.close()
        return

    if not rows:
        print(f"[search] '{keyword}' — no results")
        db.close()
        return

    print(f"[search] '{keyword}' — {len(rows)} results\n")
    prev_session = None
    for session_id, ts, role, content, project, slug in rows:
        if session_id != prev_session:
            date = ts[:10] if ts else "?"
            print(f"--- [{date}] {project} / {slug or session_id[:8]} ---")
            prev_session = session_id
        prefix = "AI" if role == "assistant" else "me"
        snippet = content[:120].replace("\n", " ")
        print(f"  [{prefix}] {snippet}...")
    db.close()


def cmd_session(session_id):
    db = get_db()
    rows = db.execute(
        "SELECT ts, role, content FROM messages WHERE session_id=? ORDER BY ts",
        (session_id,)
    ).fetchall()
    for ts, role, content in rows:
        prefix = "AI" if role == "assistant" else "me"
        print(f"[{ts[:19]}] {prefix}: {content[:300]}")
    db.close()


def cmd_export(session_id, date_filter=None):
    """Export full session to stdout (pipe to file as needed)."""
    db = get_db()
    if date_filter:
        rows = db.execute(
            "SELECT ts, role, content FROM messages WHERE session_id=? AND ts LIKE ? ORDER BY ts",
            (session_id, date_filter + "%")
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT ts, role, content FROM messages WHERE session_id=? ORDER BY ts",
            (session_id,)
        ).fetchall()
    db.close()
    for ts, role, content in rows:
        prefix = "me" if role == "user" else "AI"
        print(f"[{ts[:19]}] {prefix}:")
        print(content)
        print()


def cmd_rebuild_fts():
    db = get_db()
    db.execute("DELETE FROM messages_fts")
    rows = db.execute("SELECT id, session_id, content FROM messages").fetchall()
    for msg_id, session_id, content in rows:
        if content:
            db.execute(
                "INSERT INTO messages_fts (content, session_id, msg_id) VALUES (?,?,?)",
                (content, session_id, msg_id)
            )
    db.commit()
    print(f"[done] FTS5 rebuilt: {len(rows)} messages")
    db.close()


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Claude Code conversation archiver")
    parser.add_argument("--db",   help=f"SQLite DB path (default: {_DEFAULT_DB})")
    parser.add_argument("--root", help=f"Projects root (default: {_DEFAULT_ROOT})")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--scan",        action="store_true", help="Scan all .jsonl files")
    group.add_argument("--file",        metavar="PATH",      help="Import a single .jsonl file")
    group.add_argument("--search",      metavar="QUERY",     help="FTS5 search")
    group.add_argument("--session",     metavar="ID",        help="Print session messages")
    group.add_argument("--export",      metavar="ID",        help="Export session to stdout")
    group.add_argument("--rebuild-fts", action="store_true", help="Rebuild FTS5 index")

    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Date filter for --export")
    parser.add_argument("--limit", type=int, default=20, help="Max results for --search")

    args = parser.parse_args()

    if args.db:
        DB_PATH = Path(args.db)
    if args.root:
        JSONL_ROOT = Path(args.root)

    if args.scan or not any([args.file, args.search, args.session, args.export, args.rebuild_fts]):
        cmd_scan()
    elif args.file:
        cmd_file(args.file)
    elif args.search:
        cmd_search(args.search, limit=args.limit)
    elif args.session:
        cmd_session(args.session)
    elif args.export:
        cmd_export(args.export, date_filter=args.date)
    elif args.rebuild_fts:
        cmd_rebuild_fts()
