"""Database module for favorites tracking using SQLite."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Database file path
DB_PATH = Path(__file__).resolve().parent.parent / "favorites.db"

# Tracking expires after 2 weeks
TRACKING_EXPIRY_DAYS = 14


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Favorites table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            video_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            channel_id TEXT,
            channel_title TEXT,
            thumbnail_url TEXT,
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    # View history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS view_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            view_count INTEGER NOT NULL,
            like_count INTEGER,
            comment_count INTEGER,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY (video_id) REFERENCES favorites(video_id)
        )
    """)
    
    # Index for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_view_history_video_id 
        ON view_history(video_id)
    """)
    
    conn.commit()
    conn.close()


def add_favorite(
    video_id: str,
    title: str,
    channel_id: str = "",
    channel_title: str = "",
    thumbnail_url: str = ""
) -> Dict:
    """Add a video to favorites."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        cursor.execute("""
            INSERT INTO favorites (video_id, title, channel_id, channel_title, thumbnail_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (video_id, title, channel_id, channel_title, thumbnail_url, now))
        conn.commit()
        return {"success": True, "video_id": video_id}
    except sqlite3.IntegrityError:
        # Already exists, reactivate if inactive
        cursor.execute("""
            UPDATE favorites SET is_active = 1, created_at = ? WHERE video_id = ?
        """, (now, video_id))
        conn.commit()
        return {"success": True, "video_id": video_id, "reactivated": True}
    finally:
        conn.close()


def remove_favorite(video_id: str) -> Dict:
    """Remove a video from favorites (soft delete)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE favorites SET is_active = 0 WHERE video_id = ?
    """, (video_id,))
    
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return {"success": affected > 0, "video_id": video_id}


def get_favorites(include_inactive: bool = False) -> List[Dict]:
    """Get all favorites."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if include_inactive:
        cursor.execute("SELECT * FROM favorites ORDER BY created_at DESC")
    else:
        cursor.execute("SELECT * FROM favorites WHERE is_active = 1 ORDER BY created_at DESC")
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_active_favorites_for_tracking() -> List[Dict]:
    """Get favorites that are active and within tracking period (2 weeks)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cutoff = (datetime.now(timezone.utc) - timedelta(days=TRACKING_EXPIRY_DAYS)).isoformat()
    
    cursor.execute("""
        SELECT * FROM favorites 
        WHERE is_active = 1 AND created_at >= ?
        ORDER BY created_at DESC
    """, (cutoff,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def record_view_count(
    video_id: str,
    view_count: int,
    like_count: Optional[int] = None,
    comment_count: Optional[int] = None
) -> Dict:
    """Record a view count snapshot for a video."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        INSERT INTO view_history (video_id, view_count, like_count, comment_count, recorded_at)
        VALUES (?, ?, ?, ?, ?)
    """, (video_id, view_count, like_count, comment_count, now))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "video_id": video_id, "recorded_at": now}


def get_view_history(video_id: str, limit: int = 100) -> List[Dict]:
    """Get view count history for a video."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM view_history 
        WHERE video_id = ?
        ORDER BY recorded_at DESC
        LIMIT ?
    """, (video_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_favorite_with_latest_stats(video_id: str) -> Optional[Dict]:
    """Get a favorite with its latest stats."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT f.*, vh.view_count, vh.like_count, vh.comment_count, vh.recorded_at as last_updated
        FROM favorites f
        LEFT JOIN (
            SELECT video_id, view_count, like_count, comment_count, recorded_at,
                   ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY recorded_at DESC) as rn
            FROM view_history
        ) vh ON f.video_id = vh.video_id AND vh.rn = 1
        WHERE f.video_id = ?
    """, (video_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


# Initialize database on module import
init_db()
