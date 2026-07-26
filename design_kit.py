"""Design system cho giao diện Creator Studio."""
import colorsys
import streamlit as st

MAC_COLORS = ["#e5484d", "#d17d00", "#3178c6", "#7c5cc4", "#0f9d78", "#9f4a9c", "#5c7f2f"]
PLOTLY_CONFIG = {"scrollZoom": False, "displayModeBar": False, "responsive": True}


def _hsl_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


def build_color_map(names):
    colors = MAC_COLORS + [_hsl_hex((index * .618 + .05) % 1, .56, .48) for index in range(max(0, len(names) - len(MAC_COLORS)))]
    return {name: colors[index] for index, name in enumerate(names)}


def icon(name, size=18, color=None):
    color_style = f"color:{color};" if color else ""
    return f'<span class="material-symbols-rounded" style="font-size:{size}px;{color_style}">{name}</span>'


def format_plotly_fig(fig, is_pie=False):
    fig.update_layout(
        dragmode=False, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", color="#24211f"),
        margin=dict(t=12, r=12, b=12, l=12),
    )
    if not is_pie:
        fig.update_traces(marker_cornerradius=8, selector=dict(type="bar"))
    return fig


_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
:root { --ink:#24211f; --muted:#756f6a; --surface:#fff; --canvas:#f8f6f4; --line:#e5e0dc; --accent:#e5484d; --accent-dark:#c83b40; --positive:#16805b; --radius:16px; }
.stApp, html, body { background:var(--canvas); font-family:'DM Sans',-apple-system,sans-serif; color:var(--ink); }
.block-container { max-width:1180px; padding:28px 28px 56px; }
.material-symbols-rounded { vertical-align:-4px; font-variation-settings:'FILL' 0,'wght' 500,'GRAD' 0,'opsz' 24; }
.studio-brand { display:flex; align-items:center; gap:16px; margin:4px 0 20px; }.brand-mark { display:grid; place-items:center; width:76px; height:76px; color:white; background:var(--accent); border-radius:20px; box-shadow:0 8px 18px rgba(229,72,77,.20); }.brand-mark .material-symbols-rounded { font-size:34px!important; }.studio-brand h1 { font-size:28px; line-height:1; margin:1px 0 3px; letter-spacing:-1px; }.studio-brand p { color:var(--muted); line-height:1.25; margin:0; font-size:14px; }.eyebrow { color:var(--accent)!important; font-size:11px!important; font-weight:700; letter-spacing:.11em; line-height:1.1!important; margin:0!important; }.section-intro { margin:22px 0 10px; }.section-intro h2 { margin:1px 0 0; font-size:24px; letter-spacing:-.7px; }.status-line { display:flex; justify-content:space-between; color:var(--muted); font-size:13px; margin:16px 0 2px; }
[data-testid='stVerticalBlockBorderWrapper'], [data-testid='stExpander'] { background:var(--surface)!important; border:1px solid var(--line)!important; border-radius:var(--radius)!important; box-shadow:0 1px 1px rgba(36,33,31,.02)!important; }
[data-testid='stVerticalBlockBorderWrapper'] { padding:18px!important; } [data-testid='stExpander'] { margin:16px 0!important; } [data-testid='stExpander'] summary { padding:14px 18px!important; } [data-testid='stExpander'] summary p { font-size:14px!important; font-weight:700!important; color:var(--ink)!important; } [data-testid='stExpanderDetails'] { padding:0 18px 18px!important; }
.st-key-command_bar { background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:12px 20px 16px; box-shadow:0 8px 30px rgba(36,33,31,.04); }.st-key-command_bar label { color:var(--muted)!important; font-size:13px!important; }
button { min-height:44px!important; border-radius:10px!important; font-size:14px!important; font-weight:600!important; } button:focus-visible { outline:3px solid rgba(229,72,77,.28)!important; outline-offset:2px!important; } [data-testid='stButton'] button[kind='primary'] { background:var(--accent)!important; border-color:var(--accent)!important; } [data-testid='stButton'] button[kind='secondary'] { border-color:var(--line)!important; color:var(--ink)!important; background:#fff!important; }
[data-testid='stSelectbox'] [data-baseweb='select'] > div { border-color:var(--line)!important; border-radius:10px!important; min-height:44px; } button[kind='segmented_controlActive'] { background:var(--accent)!important; border-color:var(--accent)!important; color:#fff!important; }
.metric-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }.metric-grid article { background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:18px 20px; min-width:0; }.metric-grid span { display:block; color:var(--muted); font-size:13px; }.metric-grid strong { display:block; margin:8px 0 6px; font-size:29px; letter-spacing:-1px; white-space:nowrap; font-variant-numeric:tabular-nums; }.metric-grid em { color:var(--muted); font-size:12px; font-style:normal; }.growth,.positive { color:var(--positive)!important; font-weight:700!important; }.panel-title { margin:0; font-size:18px; letter-spacing:-.35px; }.panel-copy { color:var(--muted); font-size:13px; margin:5px 0 16px; }.analytics-gap { height:0; }
.st-key-trend_panel, .st-key-movers_panel, .st-key-comparison_panel { background:var(--surface)!important; }.st-key-movers_panel { min-height:334px; }.st-key-trend_panel [data-testid='stPlotlyChart'], .st-key-comparison_panel [data-testid='stPlotlyChart'] { background:var(--surface); border:1px solid #eee9e5; border-radius:12px; margin-top:6px; overflow:hidden; }.st-key-trend_panel [data-testid='stSegmentedControl'] { width:max-content!important; }.st-key-trend_panel [data-testid='stSegmentedControl'] > div { gap:8px!important; }.st-key-trend_panel [data-testid='stSegmentedControl'] button { min-height:34px!important; min-width:0!important; padding:0 10px!important; font-size:12px!important; border-radius:9px!important; }
.mover-list { display:flex; flex-direction:column; gap:9px; }.mover { display:grid; grid-template-columns:24px 1fr auto; align-items:center; gap:8px; }.mover>b { display:grid; place-items:center; width:22px; height:22px; border-radius:7px; color:var(--accent); background:#fff0f0; font-size:11px; }.mover strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; }.mover i { display:block; height:4px; background:#f0ece9; border-radius:99px; margin-top:4px; }.mover i span { display:block; height:100%; border-radius:inherit; background:var(--accent); }.mover em { color:var(--positive); font-size:11px; font-style:normal; font-weight:700; white-space:nowrap; }
.detail-title { margin-bottom:24px; }.table-shell { overflow:hidden; background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); } .table-shell table { width:100%; border-collapse:collapse; font-size:13px; }.table-shell th { color:var(--muted); font-weight:600; text-align:left; padding:11px 16px; background:#fcfbfa; border-bottom:1px solid var(--line); }.table-shell td { padding:10px 16px; border-bottom:1px solid #f0ece9; }.table-shell tr:last-child td { border-bottom:0; }.table-shell td:not(:first-child),.table-shell th:not(:first-child) { text-align:right; }.spark { width:94px; color:var(--accent); }.spark svg { width:88px; height:24px; }
.mobile-only { display:none; }.video-cards { display:grid; gap:10px; }.video-card { background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:14px 16px; }.video-card>div { display:flex; justify-content:space-between; align-items:center; gap:14px; color:var(--accent); }.video-card h4 { margin:0; color:var(--ink); font-size:15px; }.video-card svg { width:82px; height:24px; }
.st-key-empty_state { text-align:center; background:var(--surface); border:1px dashed #d7cfca; border-radius:20px; padding:52px 24px; }.st-key-empty_state h2 { margin-bottom:4px; }.st-key-empty_state p { color:var(--muted); }.empty-icon { color:var(--accent); margin-bottom:10px; }
@media (max-width:760px) { .block-container { padding:26px 16px 52px; }.studio-brand { gap:14px; margin-bottom:22px; }.brand-mark { width:76px; height:76px; border-radius:20px; }.brand-mark .material-symbols-rounded { font-size:32px!important; }.studio-brand h1 { font-size:25px; }.st-key-command_bar [data-testid='stHorizontalBlock'] { flex-direction:column!important; gap:0!important; }.st-key-command_bar [data-testid='stColumn'] { width:100%!important; margin-bottom:8px!important; }.metric-grid { grid-template-columns:repeat(2,1fr); gap:10px; margin-bottom:24px; }.metric-grid article { padding:18px; }.metric-grid strong { font-size:25px; }.status-line { display:block; line-height:2; }.status-line span { display:block; }.desktop-only { display:none!important; }.mobile-only { display:block!important; }.section-intro { margin-top:26px; }.section-intro h2 { font-size:22px; } [data-testid='stVerticalBlockBorderWrapper'] { padding:18px!important; } .st-key-movers_panel { min-height:0; } .st-key-trend_panel [data-testid='stHorizontalBlock'] { flex-direction:column!important; gap:10px!important; }.st-key-trend_panel [data-testid='stColumn'] { width:100%!important; margin-bottom:0!important; } }
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)
