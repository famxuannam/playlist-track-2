"""SQLite + YouTube giả lập cho phát triển local không cần secrets."""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from youtube_api import parse_youtube_url

DB_PATH = Path(__file__).parent / ".local" / "playlist_tracker.db"


def _db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        create table if not exists playlists (id text primary key, youtube_playlist_id text unique, title text, url text, display_position integer, created_at text);
        create table if not exists videos (id text primary key, youtube_video_id text, playlist_id text, title text, position integer, created_at text);
        create table if not exists snapshots (id integer primary key autoincrement, video_id text, views integer, likes integer, captured_at text);
    """)
    columns = {row[1] for row in conn.execute("pragma table_info(playlists)")}
    if "display_position" not in columns:
        conn.execute("alter table playlists add column display_position integer")
    conn.execute("update playlists set display_position = rowid * 1000 where display_position is null")
    return conn


def _now(): return datetime.now(timezone.utc).isoformat()
def _rows(cursor): return [dict(row) for row in cursor.fetchall()]
def _number(seed, low, high): return low + int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % (high - low)


def _info(video_id, title=None, refreshes=0):
    return {
        "title": title or f"Video mẫu {video_id[-6:]}",
        "views": _number(video_id, 80_000, 1_900_000) + refreshes * _number(f"v:{video_id}", 100, 1_500),
        "likes": _number(f"l:{video_id}", 2_000, 90_000) + refreshes * _number(f"k:{video_id}", 5, 120),
    }


def list_playlists():
    with _db() as conn: return _rows(conn.execute("select * from playlists order by display_position, created_at"))


def count_videos_by_playlist():
    with _db() as conn:
        counts = {}
        for row in conn.execute("select playlist_id from videos"):
            counts[row[0]] = counts.get(row[0], 0) + 1
        return counts


def get_videos_for_playlist(playlist_id):
    with _db() as conn: return _rows(conn.execute("select * from videos where playlist_id=? order by position", (playlist_id,)))


def get_snapshots(video_id):
    with _db() as conn: return _rows(conn.execute("select * from snapshots where video_id=? order by captured_at", (video_id,)))


def get_snapshots_for_videos(video_ids): return {video_id: get_snapshots(video_id) for video_id in video_ids}


def _snapshot(conn, video_id, info):
    conn.execute("insert into snapshots (video_id, views, likes, captured_at) values (?, ?, ?, ?)", (video_id, info["views"], info["likes"], _now()))


def add_tracked_item(url):
    kind, yt_id = parse_youtube_url(url)
    external_id = yt_id if kind == "playlist" else f"video:{yt_id}"
    with _db() as conn:
        found = conn.execute("select * from playlists where youtube_playlist_id=?", (external_id,)).fetchone()
        if found: return dict(found)
        playlist_id = str(uuid.uuid4())
        title = f"Playlist mẫu {yt_id[-6:]}" if kind == "playlist" else _info(yt_id)["title"]
        row = {"id": playlist_id, "youtube_playlist_id": external_id, "title": title, "url": url, "display_position": 10_000_000, "created_at": _now()}
        conn.execute("insert into playlists values (:id,:youtube_playlist_id,:title,:url,:display_position,:created_at)", row)
        for position in range(5 if kind == "playlist" else 1):
            video_id = yt_id if kind == "video" else f"{yt_id[:5]}{position:06d}"
            local_id, video_title = str(uuid.uuid4()), title if kind == "video" else f"{title} — video {position + 1}"
            conn.execute("insert into videos values (?,?,?,?,?,?)", (local_id, video_id, playlist_id, video_title, position, _now()))
            _snapshot(conn, local_id, _info(video_id, video_title))
        return row


def refresh_playlist(playlist):
    with _db() as conn:
        for video in _rows(conn.execute("select * from videos where playlist_id=?", (playlist["id"],))):
            count = conn.execute("select count(*) from snapshots where video_id=?", (video["id"],)).fetchone()[0]
            _snapshot(conn, video["id"], _info(video["youtube_video_id"], video["title"], count))


def refresh_all():
    for playlist in list_playlists(): refresh_playlist(playlist)


def move_tracked_item(playlist_id, direction):
    items = list_playlists()
    index = next((i for i, item in enumerate(items) if item["id"] == playlist_id), None)
    target = index + direction if index is not None else -1
    if target < 0 or target >= len(items): return
    with _db() as conn:
        conn.execute("update playlists set display_position=? where id=?", (items[target]["display_position"], playlist_id))
        conn.execute("update playlists set display_position=? where id=?", (items[index]["display_position"], items[target]["id"]))


def delete_tracked_item(playlist_id):
    with _db() as conn:
        video_ids = [row[0] for row in conn.execute("select id from videos where playlist_id=?", (playlist_id,))]
        if video_ids:
            conn.executemany("delete from snapshots where video_id=?", [(video_id,) for video_id in video_ids])
        conn.execute("delete from videos where playlist_id=?", (playlist_id,))
        conn.execute("delete from playlists where id=?", (playlist_id,))
