"""Gọi YouTube Data API v3 (qua requests trực tiếp) để lấy thông tin playlist/video."""
import re
from urllib.parse import urlparse, parse_qs

import requests

API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeAPIError(Exception):
    pass


def parse_youtube_url(url):
    """Phân loại URL người dùng nhập: trả về ("playlist", playlist_id) hoặc ("video", video_id).
    Ném YouTubeAPIError nếu không nhận diện được."""
    url = url.strip()
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    if "list" in qs:
        return "playlist", qs["list"][0]

    if parsed.hostname in ("youtu.be",):
        video_id = parsed.path.lstrip("/")
        if video_id:
            return "video", video_id

    if "v" in qs:
        return "video", qs["v"][0]

    match = re.search(r"(?:shorts|embed)/([A-Za-z0-9_-]{11})", parsed.path)
    if match:
        return "video", match.group(1)

    raise YouTubeAPIError(f"Không nhận diện được URL YouTube hợp lệ: {url}")


def _get(path, params, api_key):
    params = {**params, "key": api_key}
    resp = requests.get(f"{API_BASE}/{path}", params=params, timeout=15)
    if not resp.ok:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            pass
        raise YouTubeAPIError(f"YouTube API lỗi ({resp.status_code}): {detail or resp.text}")
    return resp.json()


def fetch_playlist_title(playlist_id, api_key):
    data = _get("playlists", {"part": "snippet", "id": playlist_id}, api_key)
    items = data.get("items", [])
    if not items:
        raise YouTubeAPIError(f"Không tìm thấy playlist với id {playlist_id}")
    return items[0]["snippet"]["title"]


def fetch_playlist_video_ids(playlist_id, api_key):
    """Trả về list dict {video_id, title, position}, đã phân trang toàn bộ playlist."""
    videos = []
    page_token = None
    while True:
        params = {"part": "snippet", "playlistId": playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        data = _get("playlistItems", params, api_key)
        for item in data.get("items", []):
            snippet = item["snippet"]
            resource = snippet.get("resourceId", {})
            if resource.get("kind") != "youtube#video":
                continue
            videos.append({
                "video_id": resource["videoId"],
                "title": snippet.get("title", ""),
                "position": snippet.get("position"),
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return videos


def fetch_video_stats(video_ids, api_key):
    """Trả về dict video_id -> {title, views, likes}. Gộp tối đa 50 id/request."""
    stats = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        data = _get("videos", {"part": "snippet,statistics", "id": ",".join(chunk)}, api_key)
        for item in data.get("items", []):
            statistics = item.get("statistics", {})
            stats[item["id"]] = {
                "title": item["snippet"].get("title", ""),
                "views": int(statistics.get("viewCount", 0)),
                "likes": int(statistics.get("likeCount", 0)),
            }
    return stats


def fetch_single_video(video_id, api_key):
    stats = fetch_video_stats([video_id], api_key)
    if video_id not in stats:
        raise YouTubeAPIError(f"Không tìm thấy video với id {video_id}")
    return stats[video_id]
