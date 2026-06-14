"""SQLite cache store for hydrated videos, search runs, scores, and quota logs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY,
  title TEXT,
  channel_id TEXT,
  channel_title TEXT,
  published_at TEXT,
  description TEXT,
  tags_json TEXT,
  category_id TEXT,
  duration_seconds INTEGER,
  view_count INTEGER,
  like_count INTEGER,
  comment_count INTEGER,
  raw_json TEXT,
  last_fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS channels (
  channel_id TEXT PRIMARY KEY,
  channel_title TEXT,
  uploads_playlist_id TEXT,
  raw_json TEXT,
  last_fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS search_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic TEXT,
  query TEXT,
  published_after TEXT,
  published_before TEXT,
  region_code TEXT,
  relevance_language TEXT,
  page_count INTEGER,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS video_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT,
  topic TEXT,
  topic_score REAL,
  reason TEXT,
  matched_fields_json TEXT,
  scored_at TEXT
);
CREATE TABLE IF NOT EXISTS video_stat_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT NOT NULL,
  view_count INTEGER NOT NULL,
  like_count INTEGER NOT NULL,
  comment_count INTEGER NOT NULL,
  captured_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_video_stat_snapshots_video_time
ON video_stat_snapshots(video_id, captured_at DESC);
CREATE TABLE IF NOT EXISTS quota_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  method TEXT,
  estimated_cost INTEGER,
  endpoint TEXT,
  run_id TEXT,
  created_at TEXT
);
"""


def connect(path: str | Path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str | Path) -> None:
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_cached_video(conn, video_id: str, ttl_hours: int) -> dict | None:
    row = conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()
    if not row:
        return None
    fetched = datetime.fromisoformat(row["last_fetched_at"])
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    if fetched < datetime.now(timezone.utc) - timedelta(hours=ttl_hours):
        return None
    raw = dict(row)
    try:
        raw_json = json.loads(raw.get("raw_json") or "{}")
        tags = json.loads(raw.get("tags_json") or "[]")
    except (TypeError, ValueError):
        return None
    if isinstance(raw_json, dict) and raw_json.get("video_id"):
        return raw_json
    return {
        "video_id": raw["video_id"],
        "url": f"https://www.youtube.com/watch?v={raw['video_id']}",
        "title": raw.get("title") or "",
        "channel_id": raw.get("channel_id") or "",
        "channel_title": raw.get("channel_title") or "",
        "published_at": raw.get("published_at") or "",
        "description": raw.get("description") or "",
        "tags": tags,
        "category_id": raw.get("category_id"),
        "duration_seconds": int(raw.get("duration_seconds") or 0),
        "statistics": {
            "view_count": int(raw.get("view_count") or 0),
            "like_count": int(raw.get("like_count") or 0),
            "comment_count": int(raw.get("comment_count") or 0),
        },
        "raw_json": raw_json,
    }


def save_video(conn, video: dict) -> None:
    stats = video.get("statistics") or {}
    captured_at = _now()
    conn.execute(
        """
        INSERT OR REPLACE INTO videos
        (video_id, title, channel_id, channel_title, published_at, description, tags_json,
         category_id, duration_seconds, view_count, like_count, comment_count, raw_json, last_fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            video.get("video_id"), video.get("title"), video.get("channel_id"), video.get("channel_title"),
            video.get("published_at"), video.get("description"), json.dumps(video.get("tags") or [], ensure_ascii=False),
            video.get("category_id"), video.get("duration_seconds"), stats.get("view_count", 0),
            stats.get("like_count", 0), stats.get("comment_count", 0),
            json.dumps(video, ensure_ascii=False), captured_at,
        ),
    )
    conn.execute(
        """
        INSERT INTO video_stat_snapshots
        (video_id, view_count, like_count, comment_count, captured_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            video.get("video_id"),
            int(stats.get("view_count") or 0),
            int(stats.get("like_count") or 0),
            int(stats.get("comment_count") or 0),
            captured_at,
        ),
    )
    conn.execute(
        """
        DELETE FROM video_stat_snapshots
        WHERE video_id = ?
          AND id NOT IN (
            SELECT id
            FROM video_stat_snapshots
            WHERE video_id = ?
            ORDER BY captured_at DESC
            LIMIT 20
          )
        """,
        (video.get("video_id"), video.get("video_id")),
    )
    conn.commit()


def get_previous_statistics(conn, video_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT view_count, like_count, comment_count, captured_at
        FROM video_stat_snapshots
        WHERE video_id = ?
        ORDER BY captured_at DESC
        LIMIT 1
        """,
        (video_id,),
    ).fetchone()
    if not row:
        row = conn.execute(
            """
            SELECT view_count, like_count, comment_count, last_fetched_at AS captured_at
            FROM videos
            WHERE video_id = ?
            """,
            (video_id,),
        ).fetchone()
    return dict(row) if row else None


def log_quota(conn, method: str, estimated_cost: int, endpoint: str, run_id: str | None = None) -> None:
    conn.execute(
        "INSERT INTO quota_log (method, estimated_cost, endpoint, run_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (method, estimated_cost, endpoint, run_id, _now()),
    )
    conn.commit()
