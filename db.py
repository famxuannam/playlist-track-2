"""Supabase production hoặc SQLite mock khi phát triển local."""
import os
from datetime import datetime, timezone

import streamlit as st
import local_mock
from supabase import create_client

from youtube_api import (
    fetch_playlist_title,
    fetch_playlist_video_ids,
    fetch_video_stats,
    fetch_single_video,
    parse_youtube_url,
)

try:
    has_secrets = all(st.secrets.get(key) for key in ("SUPABASE_URL", "SUPABASE_KEY", "YOUTUBE_API_KEY"))
except FileNotFoundError:
    has_secrets = False
USE_MOCK = os.getenv("PLAYLIST_TRACKER_MODE", "").lower() == "mock" or not has_secrets


@st.cache_resource
def get_client():
    if USE_MOCK: return None
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def get_api_key():
    if USE_MOCK: return None
    return st.secrets["YOUTUBE_API_KEY"]


def list_playlists():
    """Tất cả mục đang theo dõi theo thứ tự người dùng đã sắp xếp."""
    if USE_MOCK: return local_mock.list_playlists()
    client = get_client()
    res = client.table("playlists").select("*").order("display_position").execute()
    return res.data or []


def count_videos_by_playlist():
    """Số video của từng playlist -> dict playlist_id -> count. 1 query duy nhất (chỉ lấy
    cột playlist_id), đếm ở Python để tránh N+1 query khi vẽ chip cho từng playlist."""
    if USE_MOCK: return local_mock.count_videos_by_playlist()
    client = get_client()
    res = client.table("videos").select("playlist_id").execute()
    counts = {}
    for row in res.data or []:
        pid = row["playlist_id"]
        counts[pid] = counts.get(pid, 0) + 1
    return counts


def get_videos_for_playlist(playlist_id):
    if USE_MOCK: return local_mock.get_videos_for_playlist(playlist_id)
    client = get_client()
    res = (
        client.table("videos")
        .select("*")
        .eq("playlist_id", playlist_id)
        .order("position", desc=False)
        .execute()
    )
    return res.data or []


def get_snapshots(video_id):
    """Snapshot của 1 video, cũ -> mới."""
    if USE_MOCK: return local_mock.get_snapshots(video_id)
    client = get_client()
    res = (
        client.table("snapshots")
        .select("*")
        .eq("video_id", video_id)
        .order("captured_at", desc=False)
        .execute()
    )
    return res.data or []


def get_snapshots_for_videos(video_ids):
    """Snapshot của nhiều video cùng lúc, gộp theo video_id -> list snapshot (cũ -> mới)."""
    if USE_MOCK: return local_mock.get_snapshots_for_videos(video_ids)
    if not video_ids:
        return {}
    client = get_client()
    res = (
        client.table("snapshots")
        .select("*")
        .in_("video_id", video_ids)
        .order("captured_at", desc=False)
        .execute()
    )
    grouped = {vid: [] for vid in video_ids}
    for row in res.data or []:
        grouped.setdefault(row["video_id"], []).append(row)
    return grouped


def insert_snapshot(video_id, views, likes):
    if USE_MOCK: return
    client = get_client()
    client.table("snapshots").insert({
        "video_id": video_id,
        "views": views,
        "likes": likes,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def insert_snapshots_bulk(rows):
    """rows: list[{video_id, views, likes}] -- insert 1 lần cho nhiều video."""
    if USE_MOCK or not rows:
        return
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()
    payload = [{**row, "captured_at": now} for row in rows]
    client.table("snapshots").insert(payload).execute()


def add_tracked_item(url):
    """Nhận URL playlist hoặc video, tạo mới playlist/videos + snapshot đầu tiên.
    Trả về dict playlist đã tạo (hoặc đã tồn tại)."""
    if USE_MOCK: return local_mock.add_tracked_item(url)
    client = get_client()
    api_key = get_api_key()
    kind, yt_id = parse_youtube_url(url)

    if kind == "playlist":
        existing = (
            client.table("playlists").select("*").eq("youtube_playlist_id", yt_id).execute()
        )
        if existing.data:
            return existing.data[0]

        title = fetch_playlist_title(yt_id, api_key)
        next_position = (max((item.get("display_position") or 0 for item in list_playlists()), default=0) + 1000)
        playlist_row = (
            client.table("playlists")
            .insert({"youtube_playlist_id": yt_id, "title": title, "url": url, "display_position": next_position})
            .execute()
        ).data[0]

        items = fetch_playlist_video_ids(yt_id, api_key)
        stats = fetch_video_stats([item["video_id"] for item in items], api_key)

        video_rows = []
        for item in items:
            info = stats.get(item["video_id"])
            if not info:
                continue
            video_rows.append({
                "youtube_video_id": item["video_id"],
                "playlist_id": playlist_row["id"],
                "title": info["title"] or item["title"],
                "position": item["position"],
            })
        if video_rows:
            inserted_videos = client.table("videos").insert(video_rows).execute().data
            snapshot_rows = []
            for video in inserted_videos:
                info = stats[video["youtube_video_id"]]
                snapshot_rows.append({
                    "video_id": video["id"],
                    "views": info["views"],
                    "likes": info["likes"],
                })
            insert_snapshots_bulk(snapshot_rows)
        return playlist_row

    # kind == "video": theo dõi 1 video đơn lẻ, không thuộc playlist nào
    existing_video = (
        client.table("videos").select("*").eq("youtube_video_id", yt_id).is_("playlist_id", "null").execute()
    )
    existing_playlist = (
        client.table("playlists")
        .select("*")
        .eq("youtube_playlist_id", f"video:{yt_id}")
        .execute()
    )
    if existing_playlist.data:
        return existing_playlist.data[0]

    info = fetch_single_video(yt_id, api_key)
    next_position = max((item.get("display_position") or 0 for item in list_playlists()), default=0) + 1000
    playlist_row = (
        client.table("playlists")
        .insert({"youtube_playlist_id": f"video:{yt_id}", "title": info["title"], "url": url, "display_position": next_position})
        .execute()
    ).data[0]
    video_row = (
        client.table("videos")
        .insert({
            "youtube_video_id": yt_id,
            "playlist_id": playlist_row["id"],
            "title": info["title"],
            "position": 0,
        })
        .execute()
    ).data[0]
    insert_snapshots_bulk([{"video_id": video_row["id"], "views": info["views"], "likes": info["likes"]}])
    return playlist_row


def refresh_playlist(playlist_row):
    """Gọi YouTube API lấy số liệu mới nhất cho toàn bộ video của 1 playlist đã theo dõi,
    insert snapshot mới cho mỗi video."""
    if USE_MOCK: return local_mock.refresh_playlist(playlist_row)
    api_key = get_api_key()
    if not playlist_row["youtube_playlist_id"].startswith("video:"):
        source_items = fetch_playlist_video_ids(playlist_row["youtube_playlist_id"], api_key)
        source_by_id = {item["video_id"]: item for item in source_items}
        existing = {video["youtube_video_id"]: video for video in get_videos_for_playlist(playlist_row["id"])}
        for video_id, video in existing.items():
            if video_id not in source_by_id:
                client = get_client()
                client.table("videos").delete().eq("id", video["id"]).execute()
        missing = [item for video_id, item in source_by_id.items() if video_id not in existing]
        if missing:
            stats_for_missing = fetch_video_stats([item["video_id"] for item in missing], api_key)
            rows = [{"youtube_video_id": item["video_id"], "playlist_id": playlist_row["id"], "title": stats_for_missing[item["video_id"]]["title"] or item["title"], "position": item["position"]} for item in missing if item["video_id"] in stats_for_missing]
            if rows: get_client().table("videos").insert(rows).execute()
        for video_id, video in existing.items():
            if video_id in source_by_id:
                item = source_by_id[video_id]
                get_client().table("videos").update({"position": item["position"], "title": item["title"]}).eq("id", video["id"]).execute()
    videos = get_videos_for_playlist(playlist_row["id"])
    if not videos:
        return
    video_ids = [v["youtube_video_id"] for v in videos]
    stats = fetch_video_stats(video_ids, api_key)

    snapshot_rows = []
    for video in videos:
        info = stats.get(video["youtube_video_id"])
        if not info:
            continue
        snapshot_rows.append({"video_id": video["id"], "views": info["views"], "likes": info["likes"]})
    insert_snapshots_bulk(snapshot_rows)


def refresh_all():
    if USE_MOCK: return local_mock.refresh_all()
    for playlist_row in list_playlists():
        refresh_playlist(playlist_row)


def move_tracked_item(playlist_id, direction):
    if USE_MOCK: return local_mock.move_tracked_item(playlist_id, direction)
    items = list_playlists()
    index = next((i for i, item in enumerate(items) if item["id"] == playlist_id), None)
    target = index + direction if index is not None else -1
    if target < 0 or target >= len(items): return
    client = get_client()
    client.table("playlists").update({"display_position": items[target]["display_position"]}).eq("id", playlist_id).execute()
    client.table("playlists").update({"display_position": items[index]["display_position"]}).eq("id", items[target]["id"]).execute()


def delete_tracked_item(playlist_id):
    if USE_MOCK: return local_mock.delete_tracked_item(playlist_id)
    get_client().table("playlists").delete().eq("id", playlist_id).execute()
