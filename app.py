import pandas as pd
import plotly.express as px
import streamlit as st

from analytics import compute_playlist_metrics
from design_kit import PLOTLY_CONFIG, build_color_map, format_plotly_fig, inject_css
from db import (
    add_tracked_item,
    get_snapshots_for_videos,
    get_videos_for_playlist,
    list_playlists,
    refresh_all,
    refresh_playlist,
)
from youtube_api import YouTubeAPIError

st.set_page_config(page_title="YouTube Playlist Tracker", layout="wide")
inject_css()

st.markdown("# YouTube Playlist Tracker")
st.caption("Theo dõi lượt view và lượt like của video/playlist YouTube theo thời gian.")

# --- Thêm mục theo dõi mới ---
with st.container(border=True):
    st.markdown("### Thêm mục theo dõi")
    col_url, col_btn = st.columns([4, 1])
    with col_url:
        new_url = st.text_input(
            "URL video hoặc playlist YouTube",
            placeholder="https://www.youtube.com/playlist?list=... hoặc https://www.youtube.com/watch?v=...",
            label_visibility="collapsed",
        )
    with col_btn:
        add_clicked = st.button("Theo dõi", type="primary")
    if add_clicked:
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

st.write("")

# --- Chọn playlist đang theo dõi ---
playlists = list_playlists()
if not playlists:
    st.info("Chưa có playlist/video nào được theo dõi. Hãy thêm URL ở trên.")
    st.stop()

playlist_labels = {p["id"]: p["title"] for p in playlists}
selected_id = st.selectbox(
    "Chọn playlist/video đang theo dõi",
    options=list(playlist_labels.keys()),
    format_func=lambda pid: playlist_labels[pid],
)
selected_playlist = next(p for p in playlists if p["id"] == selected_id)

col_refresh_one, col_refresh_all = st.columns(2)
with col_refresh_one:
    if st.button("Cập nhật playlist này", type="primary"):
        with st.spinner("Đang cập nhật số liệu..."):
            refresh_playlist(selected_playlist)
        st.cache_data.clear()
        st.success("Đã cập nhật.")
        st.rerun()
with col_refresh_all:
    if st.button("Cập nhật tất cả playlist", type="secondary"):
        with st.spinner("Đang cập nhật số liệu cho tất cả playlist..."):
            refresh_all()
        st.cache_data.clear()
        st.success("Đã cập nhật tất cả.")
        st.rerun()

st.write("")

# --- Số liệu playlist đang chọn ---
videos = get_videos_for_playlist(selected_id)
if not videos:
    st.info("Playlist này chưa có video nào (hoặc chưa từng được cập nhật).")
    st.stop()

snapshots_by_video = get_snapshots_for_videos([v["id"] for v in videos])
per_video, totals = compute_playlist_metrics(videos, snapshots_by_video)

st.markdown(f"## {selected_playlist['title']}")

card_specs = [
    ("Tổng lượt view", totals["views"], totals["delta_today_views"]),
    ("Tổng lượt like", totals["likes"], totals["delta_today_likes"]),
    ("Δ View (lần cập nhật trước)", totals["delta_update_views"], None),
    ("Δ Like (lần cập nhật trước)", totals["delta_update_likes"], None),
]
with st.container(border=True, key="kpi_row"):
    card_cols = st.columns(4)
    for col, (label, value, delta) in zip(card_cols, card_specs):
        with col:
            if delta is not None:
                st.metric(label, f"{value:,}", delta=f"{delta:+,} hôm nay")
            else:
                st.metric(label, f"{value:,}")

st.write("")

# --- Bảng chi tiết từng video ---
st.markdown("### Chi tiết từng video")
df = pd.DataFrame(per_video).rename(columns={
    "title": "Video",
    "views": "Views",
    "likes": "Likes",
    "delta_update_views": "Δ View (cập nhật trước)",
    "delta_update_likes": "Δ Like (cập nhật trước)",
    "delta_today_views": "Δ View (hôm nay)",
    "delta_today_likes": "Δ Like (hôm nay)",
})
table_df = df.drop(columns=["video_id"])
table_html = ["<div class='data-table-card'><table class='data-table'><thead><tr>"]
table_html += [f"<th>{col}</th>" for col in table_df.columns]
table_html.append("</tr></thead><tbody>")
for _, row in table_df.iterrows():
    table_html.append("<tr>")
    table_html.append(f"<td>{row['Video']}</td>")
    for col in table_df.columns[1:]:
        table_html.append(f"<td>{row[col]:,}</td>")
    table_html.append("</tr>")
table_html.append("</tbody></table></div>")
st.markdown("".join(table_html), unsafe_allow_html=True)

st.write("")


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


# --- Biểu đồ so sánh giữa các video ---
st.markdown("### So sánh giữa các video")
color_map = build_color_map(df["Video"].tolist())
df["Video (nhãn trục)"] = df["Video"].apply(wrap_label)

metric_options = {
    "Tổng view": "Views",
    "Tổng like": "Likes",
    "Δ View hôm nay": "Δ View (hôm nay)",
    "Δ Like hôm nay": "Δ Like (hôm nay)",
}
selected_metric_label = st.segmented_control(
    "Chỉ số hiển thị",
    options=list(metric_options.keys()),
    default=list(metric_options.keys())[0],
    required=True,
    label_visibility="collapsed",
)
column = metric_options[selected_metric_label]

fig = px.bar(df, x="Video (nhãn trục)", y=column, color="Video", color_discrete_map=color_map)
fig = format_plotly_fig(fig)
fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title=None)
fig.update_xaxes(tickangle=0, automargin=True)
st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)
