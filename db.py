"""Kết nối Supabase, hoặc SQLite demo khi phát triển cục bộ không có secrets."""
import os
from datetime import datetime, timezone

import streamlit as st
from supabase import create_client

import local_mock

from youtube_api import (
    YouTubeAPIError,
    fetch_playlist_title,
    fetch_playlist_video_ids,
    fetch_video_stats,
    fetch_single_video,
    parse_youtube_url,
)


def _has_live_secrets():
    try:
        return all(st.secrets.get(key) for key in ("SUPABASE_URL", "SUPABASE_KEY", "YOUTUBE_API_KEY"))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return False


_mode = os.getenv("PLAYLIST_TRACKER_MODE", "").lower()
USE_MOCK = _mode == "mock" or (_mode != "live" and not _has_live_secrets())


@st.cache_resource
def get_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def get_api_key():
    return st.secrets["YOUTUBE_API_KEY"]


def list_playlists():
    """Tất cả mục đang theo dõi (playlist hoặc video đơn lẻ), mới nhất trước."""
    if USE_MOCK:
        return local_mock.list_playlists()
    client = get_client()
    res = client.table("playlists").select("*").order("created_at", desc=True).execute()
    return res.data or []


def get_videos_for_playlist(playlist_id):
    if USE_MOCK:
        return local_mock.get_videos_for_playlist(playlist_id)
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
    if USE_MOCK:
        return local_mock.get_snapshots_for_videos(video_ids)
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


def count_tracked_videos():
    """Số video đang được theo dõi, tính cả bản sao ở các playlist khác nhau."""
    if USE_MOCK:
        return local_mock.count_tracked_videos()
    res = get_client().table("videos").select("id").execute()
    return len(res.data or [])


def insert_snapshot(video_id, views, likes):
    client = get_client()
    client.table("snapshots").insert({
        "video_id": video_id,
        "views": views,
        "likes": likes,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def insert_snapshots_bulk(rows):
    """rows: list[{video_id, views, likes}] -- insert 1 lần cho nhiều video."""
    if not rows:
        return
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()
    payload = [{**row, "captured_at": now} for row in rows]
    client.table("snapshots").insert(payload).execute()


def add_tracked_item(url):
    """Nhận URL playlist hoặc video, tạo mới playlist/videos + snapshot đầu tiên.
    Trả về dict playlist đã tạo (hoặc đã tồn tại)."""
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
        playlist_row = (
            client.table("playlists")
            .insert({"youtube_playlist_id": yt_id, "title": title, "url": url})
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
    playlist_row = (
        client.table("playlists")
        .insert({"youtube_playlist_id": f"video:{yt_id}", "title": info["title"], "url": url})
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


def import_youtube_playlist(url):
    """Import one YouTube playlist as an independently tracked app playlist."""
    kind, playlist_id = parse_youtube_url(url)
    if kind != "playlist":
        raise YouTubeAPIError("Hãy nhập URL playlist YouTube.")
    if USE_MOCK:
        return local_mock.import_youtube_playlist(url)
    client, api_key = get_client(), get_api_key()
    title = fetch_playlist_title(playlist_id, api_key)
    playlist = client.table("playlists").insert({"youtube_playlist_id": playlist_id, "title": title, "url": url}).execute().data[0]
    items = fetch_playlist_video_ids(playlist_id, api_key)
    stats = fetch_video_stats([item["video_id"] for item in items], api_key)
    rows = [{"youtube_video_id": item["video_id"], "playlist_id": playlist["id"], "title": stats[item["video_id"]]["title"] or item["title"], "position": item["position"]} for item in items if item["video_id"] in stats]
    if rows:
        inserted = client.table("videos").insert(rows).execute().data
        insert_snapshots_bulk([{ "video_id": row["id"], "views": stats[row["youtube_video_id"]]["views"], "likes": stats[row["youtube_video_id"]]["likes"]} for row in inserted])
    return playlist


def create_local_playlist(title):
    if USE_MOCK:
        return local_mock.create_local_playlist(title)
    return get_client().table("playlists").insert({"title": title, "url": "local://manual"}).execute().data[0]


def add_video_to_playlist(playlist_id, url):
    kind, video_id = parse_youtube_url(url)
    if kind != "video":
        raise YouTubeAPIError("Hãy nhập URL một video YouTube.")
    if USE_MOCK:
        return local_mock.add_video_to_playlist(playlist_id, video_id)
    info = fetch_single_video(video_id, get_api_key())
    position = len(get_videos_for_playlist(playlist_id))
    video = get_client().table("videos").insert({"youtube_video_id": video_id, "playlist_id": playlist_id, "title": info["title"], "position": position}).execute().data[0]
    insert_snapshots_bulk([{ "video_id": video["id"], "views": info["views"], "likes": info["likes"]}])
    return video


def delete_playlist(playlist_id):
    if USE_MOCK:
        return local_mock.delete_playlist(playlist_id)
    get_client().table("playlists").delete().eq("id", playlist_id).execute()


def delete_video(video_id):
    if USE_MOCK:
        return local_mock.delete_video(video_id)
    get_client().table("videos").delete().eq("id", video_id).execute()


def refresh_playlist(playlist_row):
    """Gọi YouTube API lấy số liệu mới nhất cho toàn bộ video của 1 playlist đã theo dõi,
    insert snapshot mới cho mỗi video."""
    api_key = get_api_key()
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
    if USE_MOCK:
        return local_mock.refresh_all()
    refreshed = 0
    for playlist_row in list_playlists():
        refreshed += len(get_videos_for_playlist(playlist_row["id"]))
        refresh_playlist(playlist_row)
    return refreshed
