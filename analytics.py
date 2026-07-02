"""Tính delta (so lần cập nhật trước, so đầu ngày) và tổng hợp số liệu playlist."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _parse_ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _today_start_utc():
    now_local = datetime.now(TZ)
    start_local = datetime.combine(now_local.date(), time.min, tzinfo=TZ)
    return start_local.astimezone(ZoneInfo("UTC"))


def compute_video_metrics(video, snapshots):
    """snapshots: list cũ -> mới cho 1 video. Trả về dict metrics cho video đó."""
    if not snapshots:
        return {
            "video_id": video["id"],
            "title": video["title"],
            "views": 0,
            "likes": 0,
            "delta_update_views": 0,
            "delta_update_likes": 0,
            "delta_today_views": 0,
            "delta_today_likes": 0,
        }

    latest = snapshots[-1]
    previous = snapshots[-2] if len(snapshots) >= 2 else None

    today_start = _today_start_utc()
    baseline_today = None
    for snap in snapshots:
        if _parse_ts(snap["captured_at"]) < today_start:
            baseline_today = snap
        else:
            break
    if baseline_today is None:
        # Video mới thêm trong ngày: dùng snapshot đầu tiên trong ngày làm mốc.
        baseline_today = snapshots[0]

    return {
        "video_id": video["id"],
        "title": video["title"],
        "views": latest["views"],
        "likes": latest["likes"],
        "delta_update_views": latest["views"] - previous["views"] if previous else 0,
        "delta_update_likes": latest["likes"] - previous["likes"] if previous else 0,
        "delta_today_views": latest["views"] - baseline_today["views"],
        "delta_today_likes": latest["likes"] - baseline_today["likes"],
    }


def compute_playlist_metrics(videos, snapshots_by_video):
    """videos: list video row; snapshots_by_video: dict video_id -> snapshots (cũ->mới).
    Trả về (per_video_metrics: list, totals: dict)."""
    per_video = [compute_video_metrics(v, snapshots_by_video.get(v["id"], [])) for v in videos]

    totals = {
        "views": sum(m["views"] for m in per_video),
        "likes": sum(m["likes"] for m in per_video),
        "delta_update_views": sum(m["delta_update_views"] for m in per_video),
        "delta_update_likes": sum(m["delta_update_likes"] for m in per_video),
        "delta_today_views": sum(m["delta_today_views"] for m in per_video),
        "delta_today_likes": sum(m["delta_today_likes"] for m in per_video),
    }
    return per_video, totals
