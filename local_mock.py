"""Dữ liệu demo cục bộ cho giao diện tracker, không dùng secrets hay API mạng."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


DB_PATH = Path(__file__).parent / ".local" / "playlist_tracker.db"


def _connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table if not exists playlists (
            id text primary key, title text not null, created_at text not null
        );
        create table if not exists videos (
            id text primary key, playlist_id text not null, title text not null, position integer not null,
            youtube_video_id text
        );
        create table if not exists snapshots (
            video_id text not null, views integer not null, likes integer not null, captured_at text not null
        );
        """
    )
    columns = {row[1] for row in conn.execute("pragma table_info(videos)")}
    if "youtube_video_id" not in columns:
        conn.execute("alter table videos add column youtube_video_id text")
    conn.execute(
        """update videos set youtube_video_id = case id
            when 'focus-1' then 'dQw4w9WgXcQ' when 'focus-2' then 'aqz-KE-bpKQ'
            when 'design-1' then '3JZ_D3ELwOQ' when 'design-2' then 'kJQP7kiw5Fk'
            when 'learn-1' then '9bZkp7q19f0' else id end
            where youtube_video_id is null or youtube_video_id = id"""
    )
    conn.executemany(
        "update playlists set title = ? where id = ?",
        [("Tập trung & làm việc sâu", "mock-focus"), ("Cảm hứng thiết kế", "mock-design"), ("Hàng chờ học tập", "mock-learn")],
    )
    conn.executemany(
        "update videos set title = ? where id = ?",
        [
            ("Một giờ làm việc sâu trong yên tĩnh", "focus-1"),
            ("Cách tôi lên kế hoạch cho một tuần tập trung", "focus-2"),
            ("Những giao diện đáng để học hỏi", "design-1"),
            ("Kiểu chữ trong thiết kế sản phẩm", "design-2"),
            ("Bài học ngắn về kể chuyện bằng dữ liệu", "learn-1"),
        ],
    )
    return conn


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    if conn.execute("select 1 from playlists limit 1").fetchone():
        return

    now = datetime.now(timezone.utc)
    previous = (now - timedelta(hours=8)).isoformat()
    latest = (now - timedelta(minutes=12)).isoformat()
    playlists = [
        ("mock-focus", "Tập trung & làm việc sâu", (now - timedelta(days=3)).isoformat()),
        ("mock-design", "Cảm hứng thiết kế", (now - timedelta(days=2)).isoformat()),
        ("mock-learn", "Hàng chờ học tập", (now - timedelta(days=1)).isoformat()),
    ]
    videos = [
        ("focus-1", "mock-focus", "Một giờ làm việc sâu trong yên tĩnh", 0, "dQw4w9WgXcQ", 182_400, 6_820, 1_730, 68),
        ("focus-2", "mock-focus", "Cách tôi lên kế hoạch cho một tuần tập trung", 1, "aqz-KE-bpKQ", 94_300, 3_910, 860, 42),
        ("design-1", "mock-design", "Những giao diện đáng để học hỏi", 0, "3JZ_D3ELwOQ", 241_800, 11_240, 2_410, 103),
        ("design-2", "mock-design", "Kiểu chữ trong thiết kế sản phẩm", 1, "kJQP7kiw5Fk", 128_500, 5_640, 980, 51),
        ("learn-1", "mock-learn", "Bài học ngắn về kể chuyện bằng dữ liệu", 0, "9bZkp7q19f0", 76_200, 2_980, 620, 24),
    ]
    conn.executemany("insert into playlists values (?, ?, ?)", playlists)
    conn.executemany(
        "insert into videos values (?, ?, ?, ?, ?)",
        [(video_id, playlist_id, title, position, youtube_id) for video_id, playlist_id, title, position, youtube_id, *_ in videos],
    )
    for video_id, *_prefix, views, likes, view_growth, like_growth in videos:
        conn.executemany(
            "insert into snapshots values (?, ?, ?, ?)",
            [
                (video_id, views - view_growth, likes - like_growth, previous),
                (video_id, views, likes, latest),
            ],
        )


def _rows(cursor: sqlite3.Cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


def list_playlists() -> list[dict]:
    with _connection() as conn:
        _seed_if_empty(conn)
        return _rows(conn.execute("select * from playlists order by created_at desc"))


def get_videos_for_playlist(playlist_id: str) -> list[dict]:
    with _connection() as conn:
        _seed_if_empty(conn)
        return _rows(conn.execute("select * from videos where playlist_id = ? order by position", (playlist_id,)))


def get_snapshots_for_videos(video_ids: list[str]) -> dict[str, list[dict]]:
    if not video_ids:
        return {}
    placeholders = ",".join("?" for _ in video_ids)
    with _connection() as conn:
        _seed_if_empty(conn)
        rows = _rows(
            conn.execute(
                f"select * from snapshots where video_id in ({placeholders}) order by captured_at",
                video_ids,
            )
        )
    grouped = {video_id: [] for video_id in video_ids}
    for row in rows:
        grouped[row["video_id"]].append(row)
    return grouped


def count_tracked_videos() -> int:
    with _connection() as conn:
        _seed_if_empty(conn)
        return conn.execute("select count(*) from videos").fetchone()[0]


def _mock_stats(seed: str):
    value = sum(ord(char) for char in seed)
    return 40_000 + value * 107, 1_600 + value * 11


def create_local_playlist(title: str) -> dict:
    row = {"id": str(uuid.uuid4()), "title": title.strip(), "created_at": datetime.now(timezone.utc).isoformat()}
    with _connection() as conn:
        _seed_if_empty(conn)
        conn.execute("insert into playlists values (:id, :title, :created_at)", row)
    return row


def add_video_to_playlist(playlist_id: str, youtube_video_id: str) -> dict:
    row = {"id": str(uuid.uuid4()), "playlist_id": playlist_id, "title": f"Video mẫu {youtube_video_id[-6:]}", "position": len(get_videos_for_playlist(playlist_id)), "youtube_video_id": youtube_video_id}
    views, likes = _mock_stats(youtube_video_id)
    with _connection() as conn:
        conn.execute("insert into videos values (:id, :playlist_id, :title, :position, :youtube_video_id)", row)
        conn.execute("insert into snapshots values (?, ?, ?, ?)", (row["id"], views, likes, datetime.now(timezone.utc).isoformat()))
    return row


def import_youtube_playlist(url: str) -> dict:
    playlist = create_local_playlist(f"Playlist mẫu {url[-6:]}")
    for video_id in ("dQw4w9WgXcQ", "aqz-KE-bpKQ", "3JZ_D3ELwOQ"):
        add_video_to_playlist(playlist["id"], video_id)
    return playlist


def delete_playlist(playlist_id: str) -> None:
    with _connection() as conn:
        ids = [row[0] for row in conn.execute("select id from videos where playlist_id = ?", (playlist_id,))]
        conn.executemany("delete from snapshots where video_id = ?", [(video_id,) for video_id in ids])
        conn.execute("delete from videos where playlist_id = ?", (playlist_id,))
        conn.execute("delete from playlists where id = ?", (playlist_id,))


def delete_video(video_id: str) -> None:
    with _connection() as conn:
        conn.execute("delete from snapshots where video_id = ?", (video_id,))
        conn.execute("delete from videos where id = ?", (video_id,))


def refresh_all() -> int:
    """Thêm snapshot demo mới cho mọi video đã theo dõi."""
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        _seed_if_empty(conn)
        videos = _rows(conn.execute("select id, youtube_video_id from videos order by id"))
        for index, video in enumerate(videos, start=1):
            latest = conn.execute(
                "select views, likes from snapshots where video_id = ? order by captured_at desc limit 1",
                (video["id"],),
            ).fetchone()
            view_growth = 40 + (sum(map(ord, video["youtube_video_id"] or video["id"])) % 260) + index
            like_growth = max(1, view_growth // 18)
            conn.execute(
                "insert into snapshots values (?, ?, ?, ?)",
                (video["id"], latest["views"] + view_growth, latest["likes"] + like_growth, now),
            )
    return len(videos)
