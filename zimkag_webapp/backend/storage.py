"""SQLite-backed persistence for watcher-processed emails.

Used by the /recent dashboard. The DB lives alongside the cached PDF reports
(`reports_cache/zimkag_recent.db`) so a single folder holds everything the
dashboard needs.

Schema is migrated on import — adding columns later is easy via the
`_migrate` step.
"""
from __future__ import annotations
import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from .config import settings

log = logging.getLogger(__name__)

DB_PATH: Path = settings.REPORTS_DIR / "zimkag_recent.db"
PDF_DIR: Path = settings.REPORTS_DIR / "recent_pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS recent_emails (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),

    sender_address  TEXT,
    sender_name     TEXT,
    subject         TEXT,
    message_id      TEXT,
    thread_id       TEXT,
    received_at     TEXT,

    filename        TEXT NOT NULL,
    size_bytes      INTEGER DEFAULT 0,
    keyword_hits    INTEGER DEFAULT 0,
    matched_keywords TEXT,

    total_clauses     INTEGER DEFAULT 0,
    count_high        INTEGER DEFAULT 0,
    count_medium      INTEGER DEFAULT 0,
    count_low         INTEGER DEFAULT 0,
    count_opportunity INTEGER DEFAULT 0,
    count_neutral     INTEGER DEFAULT 0,

    results_json    TEXT,
    report_path     TEXT,

    status          TEXT NOT NULL DEFAULT 'success'
);

CREATE INDEX IF NOT EXISTS idx_recent_created ON recent_emails (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recent_sender  ON recent_emails (sender_address);
"""


_SCHEMA_READY = False


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield a connection with row factory + WAL, schema ensured."""
    _ensure_schema()
    conn = sqlite3.connect(str(DB_PATH), isolation_level=None, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
    finally:
        conn.close()


def _ensure_schema() -> None:
    """Idempotent schema creation. Cheap CREATE IF NOT EXISTS calls — safe to
    run on every connection. Also recovers if the DB file was deleted while
    the app was running."""
    global _SCHEMA_READY
    if _SCHEMA_READY and DB_PATH.exists():
        return
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), isolation_level=None, timeout=15.0)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()
    _SCHEMA_READY = True


def init_db() -> None:
    """Run on app startup."""
    _ensure_schema()
    log.info("recent_emails DB ready at %s", DB_PATH)


# ── Public API ────────────────────────────────────────────────────────────────

def insert_processed(
    *,
    email: dict[str, Any],
    attachment: dict[str, Any],
    results: list[dict[str, Any]],
    pdf_bytes: bytes,
) -> str:
    """Persist one watcher-processed email + its analysis. Returns new row id."""
    rid = uuid.uuid4().hex[:16]
    counts = _counts(results)
    pdf_path = PDF_DIR / f"recent_{rid}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    with connect() as db:
        db.execute(
            """
            INSERT INTO recent_emails (
                id, sender_address, sender_name, subject, message_id, thread_id,
                received_at, filename, size_bytes, keyword_hits, matched_keywords,
                total_clauses, count_high, count_medium, count_low,
                count_opportunity, count_neutral,
                results_json, report_path, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rid,
                email.get("sender_address"),
                email.get("sender_name"),
                email.get("subject"),
                email.get("message_id"),
                email.get("thread_id"),
                email.get("received_at"),
                attachment.get("filename") or "(unknown)",
                int(attachment.get("size_bytes") or 0),
                int(attachment.get("keyword_hits") or 0),
                json.dumps(attachment.get("matched_keywords") or []),
                len(results),
                counts["high"], counts["medium"], counts["low"],
                counts["opportunity"], counts["neutral"],
                json.dumps(results),
                str(pdf_path),
                "success",
            ),
        )
    log.info("Persisted recent email id=%s sender=%r filename=%r",
             rid, email.get("sender_address"), attachment.get("filename"))
    return rid


def list_recent(
    *,
    limit: int = 20,
    offset: int = 0,
    q: Optional[str] = None,
    risk: Optional[str] = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return (rows, total_count). Lightweight rows — no results_json."""
    where = []
    params: list[Any] = []
    if q:
        where.append("(sender_address LIKE ? OR sender_name LIKE ? OR subject LIKE ? OR filename LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like, like])
    if risk == "high":
        where.append("count_high > 0")
    elif risk == "opportunity":
        where.append("count_opportunity > 0")
    elif risk == "medium":
        where.append("count_medium > 0")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with connect() as db:
        total = db.execute(f"SELECT COUNT(*) AS c FROM recent_emails {where_sql}",
                           params).fetchone()["c"]
        rows = db.execute(
            f"""
            SELECT id, created_at, sender_address, sender_name, subject,
                   filename, size_bytes, keyword_hits,
                   total_clauses, count_high, count_medium, count_low,
                   count_opportunity, count_neutral, status
            FROM recent_emails
            {where_sql}
            ORDER BY datetime(created_at) DESC
            LIMIT ? OFFSET ?
            """,
            [*params, int(limit), int(offset)],
        ).fetchall()

    return [_row_to_dict(r) for r in rows], int(total)


def get_recent(rid: str) -> Optional[dict[str, Any]]:
    """Return one row including the full results_json + matched_keywords."""
    with connect() as db:
        row = db.execute(
            "SELECT * FROM recent_emails WHERE id = ?", (rid,)
        ).fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    try:
        d["results"] = json.loads(row["results_json"] or "[]")
    except Exception:
        d["results"] = []
    try:
        d["matched_keywords"] = json.loads(row["matched_keywords"] or "[]")
    except Exception:
        d["matched_keywords"] = []
    return d


def report_path(rid: str) -> Optional[Path]:
    """Return on-disk PDF path for one row, or None."""
    with connect() as db:
        row = db.execute("SELECT report_path FROM recent_emails WHERE id = ?",
                         (rid,)).fetchone()
    if not row or not row["report_path"]:
        return None
    p = Path(row["report_path"])
    return p if p.exists() else None


def summary_stats() -> dict[str, Any]:
    """Aggregate stats for the dashboard hero cards."""
    with connect() as db:
        row = db.execute(
            """
            SELECT
                COUNT(*)                         AS total_emails,
                COALESCE(SUM(total_clauses), 0)  AS total_clauses,
                COALESCE(SUM(count_high), 0)     AS total_high,
                COALESCE(SUM(count_medium), 0)   AS total_medium,
                COALESCE(SUM(count_low), 0)      AS total_low,
                COALESCE(SUM(count_opportunity), 0) AS total_opportunity,
                COALESCE(SUM(count_neutral), 0)  AS total_neutral,
                COUNT(CASE WHEN date(created_at) = date('now') THEN 1 END) AS today,
                COUNT(CASE WHEN date(created_at) >= date('now','-7 day') THEN 1 END) AS this_week
            FROM recent_emails
            """
        ).fetchone()
    return dict(row) if row else {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _counts(results: list[dict[str, Any]]) -> dict[str, int]:
    out = {"high": 0, "medium": 0, "low": 0, "opportunity": 0, "neutral": 0}
    for r in results:
        rl = r.get("risk_level")
        if rl in out:
            out[rl] += 1
    return out


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """sqlite3.Row → plain dict (so FastAPI can JSON-encode it)."""
    d = {k: row[k] for k in row.keys()}
    # Don't ship the giant results_json in list endpoints
    d.pop("results_json", None)
    return d
