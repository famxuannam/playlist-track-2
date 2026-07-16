from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import TZ, build_daily_series, build_video_sparkline_points, compute_playlist_metrics
from design_kit import PLOTLY_CONFIG, build_color_map, format_plotly_fig, icon, inject_css
from db import (
    add_tracked_item,
    count_videos_by_playlist,
    get_snapshots_for_videos,
    get_videos_for_playlist,
    list_playlists,
    refresh_all,
    refresh_playlist,
)
from youtube_api import YouTubeAPIError

st.set_page_config(page_title="YouTube Playlist Tracker", layout="wide")
inject_css()


@st.dialog("Theo dõi mới")
def show_add_dialog():
    st.caption("Nhập URL video hoặc playlist YouTube muốn theo dõi.")
    new_url = st.text_input(
        "URL video hoặc playlist YouTube",
        placeholder="https://www.youtube.com/playlist?list=... hoặc https://www.youtube.com/watch?v=...",
        label_visibility="collapsed",
    )
    if st.button("Theo dõi", type="primary"):
        if not new_url.strip():
            st.warning("Vui lòng nhập URL.")
        else:
            try:
                with st.spinner("Đang lấy dữ liệu từ YouTube..."):
                    add_tracked_item(new_url)
                st.cache_data.clear()
                st.success("Đã thêm vào danh sách theo dõi.")
                st.rerun()
            except YouTubeAPIError as e:
                st.error(str(e))


def format_last_updated(snapshots_by_video):
    timestamps = [s["captured_at"] for snaps in snapshots_by_video.values() for s in snaps]
    if not timestamps:
        return None
    latest = max(
        datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in timestamps
    ).astimezone(TZ)
    if latest.date() == datetime.now(TZ).date():
        return f"hôm nay {latest.strftime('%H:%M')}"
    return latest.strftime("%d/%m %H:%M")


def wrap_label(text, max_len=14):
    """Bẻ tên video dài thành nhiều dòng (ngắt tại khoảng trắng) để trục X hiển thị
    nằm ngang thay vì phải xoay chéo."""
    words = text.split(" ")
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_len and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "<br>".join(lines)


playlists = list_playlists()
playlist_ids = [p["id"] for p in playlists]
selected_id = st.session_state.get("playlist_pills")
if selected_id not in playlist_ids:
    selected_id = playlist_ids[0] if playlist_ids else None
selected_playlist = next((p for p in playlists if p["id"] == selected_id), None)

# --- Header ---
header_left, header_right = st.columns([3, 2], vertical_alignment="top")
with header_left:
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:16px;">
          <div style="width:52px;height:52px;border-radius:14px;
                      background:linear-gradient(135deg,#00b8c2 0%,#008a93 100%);
                      box-shadow:0 6px 14px rgba(0,163,173,0.35);
                      display:flex;align-items:center;justify-content:center;">
            <div style="width:0;height:0;border-top:9px solid transparent;
                        border-bottom:9px solid transparent;border-left:15px solid #ffffff;
                        margin-left:4px;"></div>
          </div>
          <div>
            <div style="font-size:28px;font-weight:700;letter-spacing:-0.6px;line-height:1.15;">
              YouTube Playlist Tracker
            </div>
            <div style="font-size:14px;color:#6e6e73;margin-top:3px;">
              Theo dõi lượt view và lượt like của video/playlist YouTube theo thời gian.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with header_right:
    btn_all_col, btn_this_col, btn_add_col = st.columns(3)
    with btn_all_col:
        clicked_refresh_all = st.button("Cập nhật tất cả", disabled=not playlists)
    with btn_this_col:
        clicked_refresh_this = st.button(
            "Cập nhật playlist này", type="primary", disabled=selected_playlist is None
        )
    with btn_add_col:
        clicked_add = st.button("+ Theo dõi mới", key="btn_add_new")

if clicked_add:
    show_add_dialog()
if clicked_refresh_this and selected_playlist:
    with st.spinner("Đang cập nhật số liệu..."):
        refresh_playlist(selected_playlist)
    st.cache_data.clear()
    st.success("Đã cập nhật.")
    st.rerun()
if clicked_refresh_all:
    with st.spinner("Đang cập nhật số liệu cho tất cả playlist..."):
        refresh_all()
    st.cache_data.clear()
    st.success("Đã cập nhật tất cả.")
    st.rerun()

if not playlists:
    st.info("Chưa có playlist/video nào được theo dõi. Bấm “+ Theo dõi mới” ở trên để thêm.")
    st.stop()

st.write("")

# --- Chip chọn playlist ---
video_counts = count_videos_by_playlist()
playlist_title_by_id = {p["id"]: p["title"] for p in playlists}
videos = get_videos_for_playlist(selected_id)
snapshots_by_video = get_snapshots_for_videos([v["id"] for v in videos])

chip_col, updated_col = st.columns([4, 1], vertical_alignment="center")
with chip_col:
    st.pills(
        "Playlist đang theo dõi",
        options=playlist_ids,
        format_func=lambda pid: f"{playlist_title_by_id[pid]} · {video_counts.get(pid, 0)} video",
        default=selected_id,
        label_visibility="collapsed",
        key="playlist_pills",
    )
with updated_col:
    last_updated = format_last_updated(snapshots_by_video)
    if last_updated:
        st.markdown(
            f"<div style='color:#6e6e73;font-size:13px;padding-top:9px;'>"
            f"Cập nhật lần cuối: {last_updated}</div>",
            unsafe_allow_html=True,
        )

if not videos:
    st.info("Playlist này chưa có video nào (hoặc chưa từng được cập nhật).")
    st.stop()

per_video, totals = compute_playlist_metrics(videos, snapshots_by_video)

st.write("")

# --- KPI ---
kpi_html = f"""
<div class="kpi-card">
  <div class="kpi-cell">
    <div class="kpi-label">Tổng lượt view</div>
    <div class="kpi-value">{totals['views']:,}</div>
    <div class="kpi-delta positive">{icon('trending_up', 16)}{totals['delta_today_views']:+,} hôm nay</div>
  </div>
  <div class="kpi-cell">
    <div class="kpi-label">Tổng lượt like</div>
    <div class="kpi-value">{totals['likes']:,}</div>
    <div class="kpi-delta positive">{icon('trending_up', 16)}{totals['delta_today_likes']:+,} hôm nay</div>
  </div>
  <div class="kpi-cell">
    <div class="kpi-label">{icon('update', 16)} View (lần cập nhật trước)</div>
    <div class="kpi-value accent">{totals['delta_update_views']:+,}</div>
    <div class="kpi-delta muted">so với lần cập nhật trước</div>
  </div>
  <div class="kpi-cell">
    <div class="kpi-label">{icon('update', 16)} Like (lần cập nhật trước)</div>
    <div class="kpi-value accent">{totals['delta_update_likes']:+,}</div>
    <div class="kpi-delta muted">so với lần cập nhật trước</div>
  </div>
</div>
"""
st.markdown(kpi_html, unsafe_allow_html=True)

st.write("")

# --- Trend chart + Ranking ---
col_trend, col_rank = st.columns([1.9, 1])
with col_trend:
    with st.container(border=True):
        title_col, toggle_col = st.columns([3, 2])
        with title_col:
            st.markdown(
                f'<div style="font-size:17px;font-weight:600;letter-spacing:-0.4px;'
                f'display:flex;align-items:center;gap:7px;padding-top:6px;">'
                f'{icon("show_chart", 20, "#00a3ad")}Xu hướng theo thời gian</div>',
                unsafe_allow_html=True,
            )
        with toggle_col:
            range_label = st.segmented_control(
                "Khoảng thời gian",
                options=["7 ngày", "30 ngày"],
                default="7 ngày",
                required=True,
                label_visibility="collapsed",
                key="trend_range",
            )
        days = 30 if range_label == "30 ngày" else 7
        trend_df = pd.DataFrame(build_daily_series(snapshots_by_video, days=days))
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_df["date"], y=trend_df["views"], name="Views", mode="lines",
            line=dict(color="#00a3ad", width=3), fill="tozeroy", fillcolor="rgba(0,163,173,0.16)",
        ))
        fig.add_trace(go.Scatter(
            x=trend_df["date"], y=trend_df["likes"], name="Likes", mode="lines",
            line=dict(color="#007aff", width=2.5), yaxis="y2",
        ))
        fig.update_layout(
            height=280,
            xaxis=dict(showgrid=False, tickformat="%d/%m"),
            yaxis=dict(showgrid=True, gridcolor="#ececee", zeroline=False, showticklabels=False, showline=False, ticks=""),
            yaxis2=dict(overlaying="y", showgrid=False, showticklabels=False, showline=False, ticks=""),
        )
        fig = format_plotly_fig(fig)
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

with col_rank:
    with st.container(border=True):
        top5 = sorted(per_video, key=lambda m: m["delta_today_views"], reverse=True)[:5]
        max_delta = max((m["delta_today_views"] for m in top5), default=0) or 1
        rows_html = []
        for i, m in enumerate(top5, start=1):
            tier = 1 if i == 1 else (2 if i <= 3 else 3)
            bar_style = "gradient" if i <= 3 else "flat"
            width_pct = max(0, min(100, round(m["delta_today_views"] / max_delta * 100)))
            rows_html.append(
                f'<div class="rank-row"><div class="rank-badge tier-{tier}">{i}</div>'
                f'<div style="min-width:0;"><div class="rank-name">{m["title"]}</div>'
                f'<div class="rank-bar-track">'
                f'<div class="rank-bar-fill {bar_style}" style="width:{width_pct}%;"></div>'
                f'</div></div>'
                f'<div class="rank-delta">{icon("arrow_upward", 14)}{m["delta_today_views"]:+,}</div></div>'
            )
        st.markdown(
            f"""
            <div class="rank-card">
              <div class="rank-title">{icon('local_fire_department', 20, '#ff9500')}Tăng trưởng nhanh nhất</div>
              <div class="rank-subtitle">{icon('trending_up', 14)}Mức tăng view hôm nay, xếp theo tốc độ</div>
              <div class="rank-rows">{''.join(rows_html)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.write("")

# --- Bảng chi tiết từng video ---
table_rows = []
for m in per_video:
    points = build_video_sparkline_points(snapshots_by_video.get(m["video_id"], []), days=7)
    poly = " ".join(f"{x},{y}" for x, y in points)
    dot_x, dot_y = points[-1]
    spark_svg = (
        '<svg viewBox="0 0 100 26" style="width:100px;height:26px;display:block;">'
        f'<polyline points="{poly}" fill="none" stroke="#00a3ad" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"></polyline>'
        f'<circle cx="{dot_x}" cy="{dot_y}" r="2.5" fill="#00a3ad"></circle></svg>'
    )
    # 1 dòng, không xuống dòng -- st.markdown gộp nhiều đoạn HTML nối chuỗi bằng dòng
    # trắng ở giữa có thể khiến trình render markdown hiểu sai điểm kết thúc HTML block
    # (thẻ đóng đứng riêng 1 dòng sau dòng trắng bị in ra thành text, xem inject_css()).
    table_rows.append(
        f'<tr><td style="font-weight:500;">{m["title"]}</td>'
        f'<td class="spark-cell">{spark_svg}</td>'
        f'<td style="text-align:right;font-weight:600;">{m["views"]:,}</td>'
        f'<td style="text-align:right;color:#34c759;font-weight:600;">{m["delta_today_views"]:+,}</td>'
        f'<td style="text-align:right;color:#6e6e73;">{m["delta_update_views"]:+,}</td>'
        f'<td style="text-align:right;">{m["likes"]:,}</td>'
        f'<td style="text-align:right;color:#34c759;font-weight:600;">{m["delta_today_likes"]:+,}</td></tr>'
    )

st.markdown(
    f"""
    <div class="data-table-card">
      <div style="padding:20px 24px 14px 24px;font-size:17px;font-weight:600;letter-spacing:-0.4px;
                  display:flex;align-items:center;gap:7px;">
        {icon('smart_display', 20, '#00a3ad')}Chi tiết từng video
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Video</th>
            <th class="spark-header">Xu hướng 7 ngày</th>
            <th style="text-align:right;">Views</th>
            <th style="text-align:right;">{icon('trending_up', 15)} View hôm nay</th>
            <th style="text-align:right;">{icon('update', 15)} View trước</th>
            <th style="text-align:right;">Likes</th>
            <th style="text-align:right;">{icon('trending_up', 15)} Like hôm nay</th>
          </tr>
        </thead>
        <tbody>
          {''.join(table_rows)}
        </tbody>
      </table>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# --- Biểu đồ so sánh giữa các video ---
df = pd.DataFrame(per_video).rename(columns={
    "title": "Video",
    "views": "Views",
    "likes": "Likes",
    "delta_update_views": "Δ View (cập nhật trước)",
    "delta_update_likes": "Δ Like (cập nhật trước)",
    "delta_today_views": "Δ View (hôm nay)",
    "delta_today_likes": "Δ Like (hôm nay)",
})
color_map = build_color_map(df["Video"].tolist())
df["Video (nhãn trục)"] = df["Video"].apply(wrap_label)

metric_options = {
    "Tổng view": "Views",
    "Tổng like": "Likes",
    "View hôm nay": "Δ View (hôm nay)",
    "Like hôm nay": "Δ Like (hôm nay)",
}
with st.container(border=True):
    st.markdown(
        f'<div style="font-size:17px;font-weight:600;letter-spacing:-0.4px;'
        f'display:flex;align-items:center;gap:7px;padding-top:6px;">'
        f'{icon("bar_chart", 20, "#00a3ad")}So sánh giữa các video</div>',
        unsafe_allow_html=True,
    )
    selected_metric_label = st.segmented_control(
        "Chỉ số hiển thị",
        options=list(metric_options.keys()),
        default=list(metric_options.keys())[0],
        required=True,
        label_visibility="collapsed",
        key="compare_metric",
    )
    column = metric_options[selected_metric_label]

    fig = px.bar(df, x="Video (nhãn trục)", y=column, color="Video", color_discrete_map=color_map)
    fig = format_plotly_fig(fig)
    fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title=None)
    fig.update_xaxes(tickangle=0, automargin=True)
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
