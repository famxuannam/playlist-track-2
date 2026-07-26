"""Creator Studio dashboard cho YouTube Playlist Tracker."""
from datetime import datetime
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import TZ, build_daily_series, build_video_sparkline_points, compute_playlist_metrics
from design_kit import PLOTLY_CONFIG, build_color_map, format_plotly_fig, icon, inject_css
from db import (
    add_tracked_item, count_videos_by_playlist, delete_tracked_item,
    get_snapshots_for_videos, get_videos_for_playlist, list_playlists,
    move_tracked_item, refresh_all, refresh_playlist,
)
from youtube_api import YouTubeAPIError

st.set_page_config(page_title="Creator Studio · Playlist Tracker", layout="wide")
inject_css()


@st.dialog("Theo dõi mới")
def show_add_dialog():
    st.caption("Dán URL video hoặc playlist YouTube để bắt đầu theo dõi.")
    url = st.text_input("URL YouTube", placeholder="https://youtube.com/playlist?list=…")
    if st.button("Bắt đầu theo dõi", type="primary", width="stretch"):
        if not url.strip():
            st.warning("Hãy nhập URL YouTube.")
        else:
            try:
                with st.spinner("Đang lấy dữ liệu từ YouTube…"):
                    add_tracked_item(url)
                st.success("Đã thêm mục theo dõi.")
                st.rerun()
            except YouTubeAPIError as error:
                st.error(str(error))


def last_updated(snapshots):
    timestamps = [row["captured_at"] for items in snapshots.values() for row in items]
    if not timestamps:
        return "Chưa có dữ liệu"
    value = max(datetime.fromisoformat(item.replace("Z", "+00:00")) for item in timestamps).astimezone(TZ)
    return f"Hôm nay · {value:%H:%M}" if value.date() == datetime.now(TZ).date() else f"{value:%d/%m · %H:%M}"


def sparkline(points):
    polyline = " ".join(f"{x},{y}" for x, y in points)
    x, y = points[-1]
    return (
        '<svg viewBox="0 0 100 28" aria-hidden="true"><polyline points="%s" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="%s" cy="%s" r="2.5" fill="currentColor"/></svg>' % (polyline, x, y)
    )


def compact_number(value):
    return f"{value / 1_000_000:.1f}M" if abs(value) >= 1_000_000 else f"{value / 1_000:.1f}K" if abs(value) >= 1_000 else f"{value:,}"


playlists = list_playlists()
playlist_ids = [item["id"] for item in playlists]
if st.session_state.get("selected_tracker") not in playlist_ids:
    st.session_state.selected_tracker = playlist_ids[0] if playlist_ids else None

# Brand header
st.markdown(
    f'''<section class="studio-brand">
      <div class="brand-mark">{icon("play_arrow", 26)}</div>
      <div><p class="eyebrow">CREATOR STUDIO</p><h1>Playlist Pulse</h1>
      <p>Theo dõi tín hiệu tăng trưởng của video và playlist YouTube.</p></div>
    </section>''', unsafe_allow_html=True,
)

if not playlists:
    with st.container(key="empty_state"):
        st.markdown(f"<div class='empty-icon'>{icon('add_chart', 34)}</div><h2>Chưa có mục theo dõi</h2><p>Thêm playlist hoặc video đầu tiên để xây dựng Creator Studio của bạn.</p>", unsafe_allow_html=True)
        if st.button("Theo dõi mục đầu tiên", type="primary", key="empty_add"):
            show_add_dialog()
    st.stop()

labels = {item["id"]: item["title"] for item in playlists}
counts = count_videos_by_playlist()

# Command bar
with st.container(key="command_bar"):
    select_col, refresh_col, all_col, add_col = st.columns([5.2, 1.0, 1.2, 1.2], vertical_alignment="bottom")
    with select_col:
        selected_id = st.selectbox(
            "Đang xem", playlist_ids,
            format_func=lambda item_id: f"{labels[item_id]} · {counts.get(item_id, 0)} video",
            key="selected_tracker",
        )
    selected_playlist = next(item for item in playlists if item["id"] == selected_id)
    with refresh_col:
        refresh_current = st.button("Cập nhật", key="refresh_current", width="stretch")
    with all_col:
        refresh_everything = st.button("Cập nhật tất cả", key="refresh_all", width="stretch")
    with add_col:
        add_new = st.button("Theo dõi mới", type="primary", key="add_new", width="stretch")

if add_new:
    show_add_dialog()
if refresh_current:
    with st.spinner("Đang đồng bộ playlist…"):
        refresh_playlist(selected_playlist)
    st.toast("Đã cập nhật dữ liệu mới nhất.", icon="✓")
    st.rerun()
if refresh_everything:
    with st.spinner("Đang đồng bộ tất cả mục theo dõi…"):
        refresh_all()
    st.toast("Đã cập nhật tất cả mục.", icon="✓")
    st.rerun()

# Management stays visible but quiet.
with st.expander("Quản lý danh sách theo dõi", expanded=False):
    st.caption("Đổi thứ tự hiển thị hoặc xóa vĩnh viễn một mục cùng lịch sử snapshot của mục đó.")
    pending_id = st.session_state.get("pending_delete_id")
    pending = next((item for item in playlists if item["id"] == pending_id), None)
    if pending:
        st.warning(f"Xóa vĩnh viễn “{pending['title']}”? Hành động này không thể hoàn tác.")
        confirm, cancel = st.columns(2)
        with confirm:
            if st.button("Xóa vĩnh viễn", type="primary", key="confirm_delete"):
                delete_tracked_item(pending["id"])
                st.session_state.pop("pending_delete_id", None)
                st.session_state.selected_tracker = None
                st.rerun()
        with cancel:
            if st.button("Hủy", key="cancel_delete"):
                st.session_state.pop("pending_delete_id", None)
                st.rerun()
    for index, item in enumerate(playlists):
        name, up, down, remove = st.columns([8, 1, 1, 1])
        with name:
            kind = "Video" if item["youtube_playlist_id"].startswith("video:") else "Playlist"
            st.markdown(f"**{escape(item['title'])}** · :gray[{kind}]")
        with up:
            if st.button("↑", key=f"up_{item['id']}", disabled=index == 0, help="Đưa lên"):
                move_tracked_item(item["id"], -1); st.rerun()
        with down:
            if st.button("↓", key=f"down_{item['id']}", disabled=index == len(playlists) - 1, help="Đưa xuống"):
                move_tracked_item(item["id"], 1); st.rerun()
        with remove:
            if st.button("Xóa", key=f"remove_{item['id']}"):
                st.session_state.pending_delete_id = item["id"]; st.rerun()

videos = get_videos_for_playlist(selected_id)
snapshots = get_snapshots_for_videos([item["id"] for item in videos])
if not videos:
    st.info("Mục này chưa có video. Hãy bấm Cập nhật để đồng bộ lại từ YouTube.")
    st.stop()
metrics, totals = compute_playlist_metrics(videos, snapshots)

st.markdown(f"<div class='status-line'><span>{icon('schedule', 16)} Cập nhật gần nhất: {last_updated(snapshots)}</span><span>{len(videos)} video đang theo dõi</span></div>", unsafe_allow_html=True)

# Daily snapshot
st.markdown(
    f'''<section class="section-intro"><p class="eyebrow">TÌNH HÌNH HÔM NAY</p><h2>{escape(selected_playlist['title'])}</h2></section>
    <div class="metric-grid">
      <article><span>Tổng lượt xem</span><strong>{totals['views']:,}</strong><em class="growth">{icon('trending_up', 15)} {totals['delta_today_views']:+,} hôm nay</em></article>
      <article><span>Tổng lượt thích</span><strong>{totals['likes']:,}</strong><em class="growth">{icon('trending_up', 15)} {totals['delta_today_likes']:+,} hôm nay</em></article>
      <article><span>View từ lần trước</span><strong>{totals['delta_update_views']:+,}</strong><em>Nhịp cập nhật gần nhất</em></article>
      <article><span>Like từ lần trước</span><strong>{totals['delta_update_likes']:+,}</strong><em>Nhịp cập nhật gần nhất</em></article>
    </div>''', unsafe_allow_html=True,
)
st.markdown("<div class='analytics-gap'></div>", unsafe_allow_html=True)

# Trend and movers
trend_col, mover_col = st.columns([1.8, 1], vertical_alignment="top")
with trend_col:
    with st.container(border=True, key="trend_panel"):
        heading, metric_controls, period_controls = st.columns([1.25, .8, .9], vertical_alignment="center")
        with heading:
            st.markdown(f"<h3 class='panel-title'>{icon('monitoring', 20)} Xu hướng</h3>", unsafe_allow_html=True)
        with metric_controls:
            metric_choice = st.segmented_control("Chỉ số", ["Views", "Likes"], default="Views", key="trend_metric", label_visibility="collapsed")
        with period_controls:
            period = st.segmented_control("Khoảng thời gian", ["7 ngày", "30 ngày"], default="7 ngày", key="trend_period", label_visibility="collapsed")
        series = pd.DataFrame(build_daily_series(snapshots, days=30 if period == "30 ngày" else 7))
        field = "views" if metric_choice == "Views" else "likes"
        color = "#e5484d" if field == "views" else "#d17d00"
        fig = go.Figure(go.Scatter(x=series["date"], y=series[field], mode="lines", line=dict(color=color, width=3), fill="tozeroy", fillcolor="rgba(229,72,77,.10)"))
        fig.update_layout(height=240, showlegend=False, xaxis=dict(tickformat="%d/%m"), yaxis=dict(showgrid=True, gridcolor="#ebe7e4", tickformat="~s"))
        st.plotly_chart(format_plotly_fig(fig), width="stretch", config=PLOTLY_CONFIG)

with mover_col:
    with st.container(border=True, key="movers_panel"):
        st.markdown(f"<h3 class='panel-title'>{icon('local_fire_department', 20)} Đang tăng trưởng</h3><p class='panel-copy'>Video có mức tăng lượt xem cao nhất hôm nay.</p>", unsafe_allow_html=True)
        top = sorted(metrics, key=lambda item: item["delta_today_views"], reverse=True)[:8]
        highest = max((item["delta_today_views"] for item in top), default=0) or 1
        rows = "".join(
            f"<div class='mover'><b>{index}</b><div><strong>{escape(item['title'])}</strong><i><span style='width:{max(3, item['delta_today_views'] / highest * 100):.0f}%'></span></i></div><em>+{compact_number(item['delta_today_views'])}</em></div>"
            for index, item in enumerate(top, 1)
        )
        st.markdown(f"<div class='mover-list'>{rows}</div>", unsafe_allow_html=True)

