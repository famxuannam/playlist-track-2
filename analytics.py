"""Tính delta (so lần cập nhật trước, so đầu ngày) và tổng hợp số liệu playlist."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC = ZoneInfo("UTC")


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


def _day_end_boundaries_utc(days):
    """N mốc cuối-ngày (giờ VN, quy đổi UTC), từ (days-1) ngày trước tới hôm nay, cũ -> mới."""
    today_local = datetime.now(TZ).date()
    boundaries = []
    for offset in range(days - 1, -1, -1):
        day = today_local - timedelta(days=offset)
        day_end_local = datetime.combine(day, time.max, tzinfo=TZ)
        boundaries.append((day, day_end_local.astimezone(UTC)))
    return boundaries


def _latest_at_or_before(snapshots, boundary_utc):
    """snapshots đã sắp cũ -> mới. Trả về snapshot cuối cùng có captured_at <= boundary, hoặc None."""
    latest = None
    for snap in snapshots:
        if _parse_ts(snap["captured_at"]) <= boundary_utc:
            latest = snap
        else:
            break
    return latest


def build_daily_series(snapshots_by_video, days=7):
    """Tổng view/like theo từng ngày (cũ -> mới) trong `days` ngày gần nhất, cộng dồn các
    video đã có snapshot tính tới cuối ngày đó (video mới thêm sau ngày đó thì bỏ qua ngày
    đó, không tính là 0, để không kéo tổng xuống giả tạo)."""
    series = []
    for day, boundary_utc in _day_end_boundaries_utc(days):
        views_sum = 0
        likes_sum = 0
        for snapshots in snapshots_by_video.values():
            latest = _latest_at_or_before(snapshots, boundary_utc)
            if latest is None:
                continue
            views_sum += latest["views"]
            likes_sum += latest["likes"]
        series.append({"date": day, "views": views_sum, "likes": likes_sum})
    return series


def build_video_sparkline_points(snapshots, days=7):
    """Toạ độ SVG (viewBox 0 0 100 26, khớp mockup) cho xu hướng view của 1 video trong
    `days` ngày gần nhất. Đường phẳng ở giữa nếu không đủ dữ liệu hoặc không có biến động."""
    values = []
    for _day, boundary_utc in _day_end_boundaries_utc(days):
        latest = _latest_at_or_before(snapshots, boundary_utc)
        values.append(latest["views"] if latest else None)

    known = [v for v in values if v is not None]
    if not known:
        return [(0, 13), (100, 13)]
    fill_value = known[0]
    values = [v if v is not None else fill_value for v in values]

    lo, hi = min(values), max(values)
    span = hi - lo
    n = len(values)
    points = []
    for i, v in enumerate(values):
        x = round(i * 100 / (n - 1), 1) if n > 1 else 0
        y = 13.0 if span == 0 else round(24 - (v - lo) / span * 22, 1)
        points.append((x, y))
    return points
