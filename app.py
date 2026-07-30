"""Threads-inspired, read-only tracker with Home → Playlist → Video navigation."""
from datetime import datetime, time
from html import escape
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

import streamlit as st

from analytics import compute_playlist_metrics, compute_video_metrics
from db import add_video_to_playlist, count_tracked_videos, create_local_playlist, delete_playlist, delete_video, get_snapshots_for_videos, get_videos_for_playlist, import_youtube_playlist, list_playlists, refresh_all


st.set_page_config(page_title="Tracker", layout="wide")
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

THREADS_CSS = """
<style>
:root { --ink:#101010; --muted:#777; --line:#e8e8e8; --soft:#f4f4f4; --positive:#16833a; }
html, body, [class*="css"], .stApp { font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); }
.stApp { background:#fff; } #MainMenu, footer, header { visibility:hidden; }
.material-symbols-rounded { font-family:"Material Symbols Rounded"; font-weight:normal; font-style:normal; font-size:22px; line-height:1; display:inline-block; white-space:nowrap; direction:ltr; -webkit-font-smoothing:antialiased; font-variation-settings:"FILL" 0, "wght" 450, "GRAD" 0, "opsz" 24; }
.block-container { max-width:1180px !important; padding:24px 24px 48px !important; }
.threads-shell { max-width:820px; margin:0 auto; }
.threads-nav { position:sticky; top:24px; height:fit-content; }.wordmark { display:flex; align-items:center; gap:6px; font-size:27px; font-weight:800; letter-spacing:-1.6px; margin:0 0 38px; }.wordmark .material-symbols-rounded { font-size:27px; }
.nav-item { display:flex; align-items:center; gap:13px; padding:10px 11px; margin:2px 0; border-radius:10px; font-size:15px; }.nav-item.active { background:var(--soft); font-weight:700; }.nav-icon { display:grid; place-items:center; width:20px; }.nav-icon .material-symbols-rounded { font-size:22px; }.nav-muted { color:#a0a0a0; margin-top:26px; font-size:12px; padding:0 11px; }
.feed-title { font-size:20px; font-weight:750; letter-spacing:-.5px; margin:6px 0 16px; }.feed-box { border:1px solid var(--line); border-radius:22px; overflow:hidden; background:#fff; }.intro { padding:20px 24px; border-bottom:1px solid var(--line); }.intro-title { font-size:15px; font-weight:700; margin-bottom:5px; }.intro-copy { color:var(--muted); font-size:14px; line-height:1.4; }
.track-link, .video-link { display:block; color:inherit; text-decoration:none; }.track-link:hover, .video-link:hover { background:#fafafa; }.track-card { display:grid; grid-template-columns:48px 1fr; gap:12px; padding:20px 24px; border-bottom:1px solid var(--line); }.track-card:last-child { border-bottom:0; }.track-avatar, .video-thumb { overflow:hidden; background:#151515; }.track-avatar { width:42px; height:42px; border-radius:50%; color:#fff; display:grid; place-items:center; font-size:17px; font-weight:700; }.track-avatar img, .video-thumb img { height:100%; width:100%; object-fit:cover; }.track-meta { display:flex; align-items:baseline; gap:7px; min-width:0; }.track-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:15px; font-weight:750; }.track-count { color:var(--muted); font-size:13px; white-space:nowrap; }.track-caption { color:var(--muted); margin:4px 0 13px; font-size:14px; }
.track-stats { display:flex; flex-wrap:wrap; gap:18px; color:#4f4f4f; font-size:14px; }.track-stat { display:inline-flex; align-items:center; gap:4px; }.track-stat .material-symbols-rounded { font-size:18px; }.track-stats b { color:var(--ink); font-variant-numeric:tabular-nums; }.stat-growth { color:var(--positive); }.empty-state { padding:36px 24px; color:var(--muted); line-height:1.5; }.aside-copy { color:var(--muted); font-size:13px; line-height:1.5; padding-top:52px; }
.detail-head { display:flex; align-items:center; gap:12px; margin:6px 0 16px; }.back-link { display:grid; place-items:center; width:34px; height:34px; border-radius:50%; color:var(--ink); text-decoration:none; }.back-link:hover { background:var(--soft); }.detail-title { font-size:20px; font-weight:750; letter-spacing:-.5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.detail-summary { display:grid; grid-template-columns:repeat(3,1fr); border-bottom:1px solid var(--line); }.detail-metric { padding:18px 20px; border-right:1px solid var(--line); }.detail-metric:last-child { border-right:0; }.metric-label { color:var(--muted); font-size:12px; margin-bottom:5px; }.metric-value { font-size:19px; font-weight:750; font-variant-numeric:tabular-nums; }.video-row { display:grid; grid-template-columns:126px minmax(0,1fr) 20px; gap:14px; align-items:center; padding:14px 20px; border-bottom:1px solid var(--line); }.video-row:last-child { border-bottom:0; }.video-thumb { height:72px; border-radius:10px; }.video-name { font-size:15px; font-weight:700; line-height:1.35; }.video-meta { margin-top:7px; color:var(--muted); font-size:13px; }.row-arrow { color:var(--muted); }
.video-hero { display:grid; grid-template-columns:190px 1fr; gap:18px; padding:20px; border-bottom:1px solid var(--line); }.video-hero .video-thumb { height:108px; }.history-heading { padding:18px 20px 10px; font-size:15px; font-weight:700; }.history-table { width:100%; border-collapse:collapse; font-size:14px; }.history-table th { color:var(--muted); font-size:12px; font-weight:600; text-align:left; padding:10px 20px; border-bottom:1px solid var(--line); }.history-table td { padding:12px 20px; border-bottom:1px solid var(--line); font-variant-numeric:tabular-nums; }.history-table tr:last-child td { border-bottom:0; }.history-table td:not(:first-child), .history-table th:not(:first-child) { text-align:right; }.inline-growth { color:var(--positive); font-size:12px; margin-left:4px; }.youtube-link{display:inline-flex;align-items:center;gap:6px;margin-top:16px;padding:9px 12px;border:1px solid var(--line);border-radius:10px;color:var(--ink);font-size:13px;font-weight:650;text-decoration:none}.youtube-link:hover{background:var(--soft)}.youtube-link .material-symbols-rounded{font-size:18px}.fab{position:fixed;right:32px;bottom:32px;display:grid;place-items:center;width:56px;height:56px;background:#fff;border:1px solid var(--line);border-radius:18px;color:var(--ink);box-shadow:0 4px 14px #0002;text-decoration:none;z-index:20}.fab .material-symbols-rounded{font-size:28px}.fab:hover{background:var(--soft)}.delete-link,.icon-delete{display:grid;place-items:center;color:#777;text-decoration:none}.icon-delete{width:30px;height:30px;border-radius:50%}.icon-delete:hover{background:#f5eaea;color:#b3261e}.track-card{grid-template-columns:48px 1fr 30px}.track-main{color:inherit;text-decoration:none}.video-row{grid-template-columns:126px minmax(0,1fr) 30px}.video-link{display:contents}div[role="dialog"]{border-radius:24px!important;background:#fff!important;box-shadow:0 18px 48px #0003!important}div[role="dialog"] button[kind="primary"]{background:#111!important;color:#fff!important;border-color:#111!important;border-radius:12px!important}div[role="dialog"] [data-testid="stForm"]{border:0!important;padding:0!important}div[role="dialog"] input{border-radius:12px!important;background:#f4f4f4!important}
@media (max-width:760px) { .block-container { padding:14px 12px 32px !important; }.threads-shell { display:block; }.threads-nav { position:static; display:flex; align-items:center; gap:10px; margin-bottom:20px; }.wordmark { margin:0 auto 0 0; font-size:23px; }.threads-nav .nav-item, .threads-nav .nav-muted { display:none; }.threads-nav .nav-item.active { display:flex; padding:8px 10px; }.aside-copy { display:none; }.track-card { padding:18px 16px; }.intro { padding:18px 16px; }.detail-metric { padding:15px 12px; }.metric-value { font-size:16px; }.video-row { grid-template-columns:104px minmax(0,1fr) 16px; padding:12px 14px; gap:11px; }.video-thumb { height:62px; }.video-hero { grid-template-columns:1fr; padding:14px; }.video-hero .video-thumb { height:180px; }.history-table th, .history-table td { padding:10px 12px; }.history-table { font-size:13px; } }
</style>
"""


def compact_number(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,}"


def page_url(view: str = "home", **params: str) -> str:
    return "?" + urlencode({"view": view, **params}) if view != "home" else "?"


def thumbnail_url(video: dict) -> str:
    video_id = quote(str(video.get("youtube_video_id") or ""), safe="")
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def playlist_summary(playlist: dict) -> dict:
    videos = get_videos_for_playlist(playlist["id"])
    snapshots = get_snapshots_for_videos([video["id"] for video in videos])
    _, totals = compute_playlist_metrics(videos, snapshots)
    return {"playlist": playlist, "videos": videos, "snapshots": snapshots, "totals": totals}


def metric_html(icon: str, value: int, label: str) -> str:
    return f'<span class="track-stat"><span class="material-symbols-rounded">{icon}</span><b>{compact_number(value)}</b> {label}</span>'


def render_shell(title: str, content: str, back_url: str | None = None) -> None:
    header = f'<div class="feed-title">{escape(title)}</div>' if title else ""
    if back_url:
        header = f'<div class="detail-head"><a class="back-link" href="{escape(back_url)}" aria-label="Quay lại"><span class="material-symbols-rounded">arrow_back</span></a><div class="detail-title">{escape(title)}</div></div>'
    st.html(
        f'''<main class="threads-shell">{header}<section class="feed-box">{content}</section></main>'''
    )


def render_home(playlists: list[dict]) -> None:
    cards = []
    for playlist in playlists:
        summary = playlist_summary(playlist)
        videos, totals = summary["videos"], summary["totals"]
        title = escape(playlist.get("title") or "Mục chưa có tên")
        cover = f'<img src="{thumbnail_url(videos[0])}" alt="">' if videos else title[:1].upper()
        growth = totals["delta_update_views"]
        growth_html = f'<span class="stat-growth">+{compact_number(growth)} từ lần cập nhật trước</span>' if growth else ""
        cards.append(
            f'''<article class="track-card"><div class="track-avatar">{cover}</div><a class="track-main" href="{page_url("playlist", playlist=playlist["id"])}"><div class="track-meta"><div class="track-name">{title}</div><div class="track-count">· {len(videos)} {"video" if len(videos) == 1 else "videos"}</div></div><div class="track-caption">YouTube playlist tracker</div><div class="track-stats">{metric_html("visibility", totals["views"], "views")}{metric_html("favorite", totals["likes"], "likes")}{growth_html}</div></a><a class="icon-delete" href="?view=delete&playlist={playlist["id"]}" aria-label="Xóa playlist"><span class="material-symbols-rounded">delete</span></a></article>'''
        )
    content = '<div class="intro"><div class="intro-title">Your tracked playlists</div><div class="intro-copy">A quiet overview of the latest YouTube numbers.</div></div>'
    content += '<div class="history-heading">Playlists <a class="delete-link" href="?view=add">+ Thêm playlist</a></div>'
    content += "".join(cards) or '<div class="empty-state">Chưa có dữ liệu theo dõi.</div>'
    render_shell("", content)


def render_playlist(playlist: dict) -> None:
    summary = playlist_summary(playlist)
    videos, snapshots, totals = summary["videos"], summary["snapshots"], summary["totals"]
    metrics = f'''<div class="detail-summary"><div class="detail-metric"><div class="metric-label">Views</div><div class="metric-value">{compact_number(totals["views"])}</div></div><div class="detail-metric"><div class="metric-label">Likes</div><div class="metric-value">{compact_number(totals["likes"])}</div></div><div class="detail-metric"><div class="metric-label">Từ lần cập nhật trước</div><div class="metric-value stat-growth">+{compact_number(totals["delta_update_views"])}</div></div></div>'''
    rows = []
    for video in videos:
        metric = compute_video_metrics(video, snapshots.get(video["id"], []))
        rows.append(
            f'''<article class="video-row"><a class="video-link" href="{page_url("video", playlist=playlist["id"], video=video["id"])}"><div class="video-thumb"><img src="{thumbnail_url(video)}" alt=""></div><div><div class="video-name">{escape(video["title"])}</div><div class="video-meta">{compact_number(metric["views"])} views · {compact_number(metric["likes"])} likes · <span class="stat-growth">+{compact_number(metric["delta_update_views"])}</span></div></div></a><a class="icon-delete" href="?view=delete_video&playlist={playlist["id"]}&video={video["id"]}" aria-label="Xóa video"><span class="material-symbols-rounded">delete</span></a></article>'''
        )
    content = metrics + f'<div class="history-heading">Videos <a class="delete-link" href="?view=playlist&playlist={playlist["id"]}&action=add_video">+ Thêm video</a></div>' + ("".join(rows) or '<div class="empty-state">Playlist chưa có video.</div>')
    render_shell(playlist["title"], content, page_url())


def short_timestamp(raw: str) -> str:
    timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(TZ)
    return timestamp.strftime("%d/%m · %H:%M")


def render_video(playlist: dict, video: dict) -> None:
    snapshots = get_snapshots_for_videos([video["id"]]).get(video["id"], [])
    latest = compute_video_metrics(video, snapshots)
    day_start = datetime.combine(datetime.now(TZ).date(), time.min, tzinfo=TZ).astimezone(ZoneInfo("UTC"))
    baseline = next((snap for snap in reversed(snapshots) if datetime.fromisoformat(snap["captured_at"].replace("Z", "+00:00")) < day_start), snapshots[0] if snapshots else {"views": 0, "likes": 0})
    table_rows = []
    for snapshot in reversed(snapshots):
        view_growth = snapshot["views"] - baseline["views"]
        like_growth = snapshot["likes"] - baseline["likes"]
        table_rows.append(f'''<tr><td>{short_timestamp(snapshot["captured_at"])}</td><td>{compact_number(snapshot["views"])} <span class="inline-growth">(+{compact_number(view_growth)})</span></td><td>{compact_number(snapshot["likes"])} <span class="inline-growth">(+{compact_number(like_growth)})</span></td></tr>''')
    youtube_url = f'https://www.youtube.com/watch?v={quote(str(video.get("youtube_video_id") or ""), safe="")}'
    hero = f'''<div class="video-hero"><div class="video-thumb"><img src="{thumbnail_url(video)}" alt=""></div><div><div class="track-caption">{escape(playlist["title"])}</div><div class="track-stats">{metric_html("visibility", latest["views"], "views")}{metric_html("favorite", latest["likes"], "likes")}</div><a class="youtube-link" href="{youtube_url}" target="_blank" rel="noopener noreferrer"><span class="material-symbols-rounded">open_in_new</span>Xem trên YouTube</a></div></div>'''
    table = '<div class="history-heading">Lịch sử</div><table class="history-table"><thead><tr><th>Mốc thời gian</th><th>Views</th><th>Likes</th></tr></thead><tbody>' + "".join(table_rows) + '</tbody></table>'
    render_shell(video["title"], hero + table, page_url("playlist", playlist=playlist["id"]))


@st.dialog("Thêm playlist", width="small")
def add_dialog():
    mode = st.radio("Cách thêm", ["Import playlist YouTube", "Tạo playlist nội bộ"], horizontal=True)
    with st.form("add_playlist"):
        value = st.text_input("URL playlist YouTube" if mode.startswith("Import") else "Tên playlist mới")
        submitted = st.form_submit_button(":material/add: Thêm", type="primary")
    if submitted:
        try:
            playlist = import_youtube_playlist(value) if mode.startswith("Import") else create_local_playlist(value)
            st.query_params["view"] = "playlist"; st.query_params["playlist"] = playlist["id"]; st.rerun()
        except Exception as error: st.error(str(error))


@st.dialog("Thêm video", width="small")
def video_dialog(playlist_id):
    with st.form("add_video"):
        url = st.text_input("URL video YouTube")
        submitted = st.form_submit_button(":material/add: Thêm video", type="primary")
    if submitted:
        try: add_video_to_playlist(playlist_id, url); st.rerun()
        except Exception as error: st.error(str(error))


@st.dialog("Xóa playlist", width="small")
def delete_dialog(playlist):
    st.warning(f'Xóa "{playlist["title"]}" cùng video và lịch sử riêng của playlist này?')
    if st.button(":material/delete: Xóa vĩnh viễn", type="primary"):
        delete_playlist(playlist["id"]); st.query_params.clear(); st.rerun()


@st.dialog("Xóa video", width="small")
def delete_video_dialog(playlist, video):
    st.warning(f'Xóa "{video["title"]}" cùng lịch sử số liệu trong playlist này?')
    if st.button(":material/delete: Xóa vĩnh viễn", type="primary", key="confirm_delete_video"):
        delete_video(video["id"]); st.query_params["view"] = "playlist"; st.query_params["playlist"] = playlist["id"]; st.rerun()


st.html(THREADS_CSS)
st.markdown("""<style>
section[role="dialog"] { background:#fff !important; border:1px solid #e8e8e8 !important; border-radius:20px !important; box-shadow:0 18px 48px rgba(0,0,0,.18) !important; padding:20px !important; }
section[role="dialog"], section[role="dialog"] h2, section[role="dialog"] p, section[role="dialog"] label, section[role="dialog"] input, section[role="dialog"] button { font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important; }
section[role="dialog"] h2 { font-size:1.3rem !important; letter-spacing:-.35px !important; margin-bottom:.35rem !important; }
section[role="dialog"] [data-testid="stElementContainer"] { margin-bottom:.15rem !important; }
section[role="dialog"] [data-testid="stWidgetLabel"] { margin-bottom:.25rem !important; }
section[role="dialog"] [data-testid="stRadio"] { margin-bottom:-.4rem !important; }
section[role="dialog"] [data-testid="stForm"] { border:0 !important; padding:0 !important; margin-top:-.2rem !important; background:transparent !important; }
section[role="dialog"] [data-testid="stTextInputRootElement"] { background:#f4f4f4 !important; border:1px solid #e1e1e1 !important; border-radius:12px !important; box-shadow:none !important; }
section[role="dialog"] input { background:transparent !important; border:0 !important; border-radius:12px !important; box-shadow:none !important; outline:0 !important; }
section[role="dialog"] button[kind="primary"] { background:#111 !important; color:#fff !important; border:1px solid #111 !important; border-radius:10px !important; }
section[role="dialog"] button[kind="primary"]:hover { background:#333 !important; border-color:#333 !important; }
section[role="dialog"] [data-testid="stBaseButton-primaryFormSubmit"] { background:transparent !important; color:#111 !important; border:1px solid #e1e1e1 !important; border-radius:10px !important; box-shadow:none !important; }
section[role="dialog"] [data-testid="stBaseButton-primaryFormSubmit"]:hover { background:#f4f4f4 !important; border-color:#d5d5d5 !important; }
</style>""", unsafe_allow_html=True)
if refreshed := st.session_state.pop("refresh_success", None):
    st.toast(f"Đã cập nhật số liệu cho {refreshed} video.", icon="✅")
try:
    playlists = list_playlists()
    playlist_by_id = {playlist["id"]: playlist for playlist in playlists}
    view = st.query_params.get("view", "home")
    playlist = playlist_by_id.get(st.query_params.get("playlist", ""))
    if view in ("playlist", "delete_video") and playlist:
        render_playlist(playlist)
        if st.query_params.get("action") == "add_video": video_dialog(playlist["id"])
        if view == "delete_video":
            selected_video = next((item for item in get_videos_for_playlist(playlist["id"]) if item["id"] == st.query_params.get("video")), None)
            if selected_video: delete_video_dialog(playlist, selected_video)
    elif view == "video" and playlist:
        video = next((item for item in get_videos_for_playlist(playlist["id"]) if item["id"] == st.query_params.get("video")), None)
        if video:
            render_video(playlist, video)
        else:
            render_shell("Không tìm thấy video", '<div class="empty-state">Video này không còn tồn tại.</div>', page_url("playlist", playlist=playlist["id"]))
    else:
        render_home(playlists)
        if view == "add": add_dialog()
    if view == "delete" and playlist: delete_dialog(playlist)

    refresh_params = dict(st.query_params)
    refresh_params["refresh"] = "1"
    refresh_url = "?" + urlencode(refresh_params)
    st.html(f'''<a class="fab" href="{escape(refresh_url)}" aria-label="Cập nhật số liệu" title="Cập nhật số liệu"><span class="material-symbols-rounded">refresh</span></a>''')
    if st.query_params.get("refresh") == "1":
        video_count = count_tracked_videos()
        if video_count > 50:
            st.toast(f"Cập nhật {video_count} video có thể tốn quota YouTube API.", icon="⚠️")
        with st.spinner("Đang cập nhật số liệu..."):
            refreshed = refresh_all()
        st.session_state["refresh_success"] = refreshed
        st.query_params.pop("refresh", None)
        st.rerun()
except Exception:
    render_shell("", '<div class="empty-state">Chưa thể kết nối dữ liệu. Khi sẵn sàng, hãy cấu hình secrets cho Supabase để xem các playlist đang theo dõi.</div>')
