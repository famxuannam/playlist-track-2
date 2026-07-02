"""
Design kit -- trích từ Forest Dashboard, dùng để tái sử dụng phong cách giao diện
(iOS/macOS: thẻ kính mờ, accent teal, font hệ thống Apple) cho app Streamlit khác.

Cách dùng trong app mới:

    import streamlit as st
    from design_kit import inject_css, MAC_COLORS, build_color_map, format_plotly_fig

    st.set_page_config(page_title="...", layout="wide")   # PHẢI gọi trước inject_css()
    inject_css()

    # Card kiểu "kính mờ": bọc nội dung trong 1 div class="glass-card", hoặc dùng
    # st.container(border=True) -- CSS trong file .streamlit/config.toml đi kèm + phần
    # [data-testid="stPlotlyChart"] trong CSS này đã tự áp style card cho biểu đồ rồi.
    st.markdown("<div class='glass-card'>Nội dung...</div>", unsafe_allow_html=True)

    # Màu nhất quán cho nhiều nhóm/danh mục (vd tô màu theo dự án trong biểu đồ)
    color_map = build_color_map(["Nhóm A", "Nhóm B", "Nhóm C"])

    # Biểu đồ Plotly đã chuẩn hoá style (bỏ nền, font, legend nằm ngang phía trên...)
    fig = format_plotly_fig(fig)

Nhớ copy kèm cả .streamlit/config.toml (theme màu nền/accent) sang app mới -- inject_css()
chỉ lo phần CSS chi tiết, không thay được cấu hình theme gốc của Streamlit.
"""
import colorsys

import streamlit as st

# ============================================================
# MÀU SẮC
# ============================================================

# Bảng màu phong cách Apple / Latte sáng -- dùng làm nguồn màu ưu tiên cho build_color_map().
MAC_COLORS = [
    "#007aff",  # Blue (Primary)
    "#34c759",  # Green
    "#ff9500",  # Orange
    "#ff2d55",  # Red
    "#5856d6",  # Indigo
    "#af52de",  # Purple
    "#5ac8fa",  # Light Blue
    "#ffcc00",  # Yellow
    "#32ade6",  # Cyan
    "#a2845e",  # Brown
    "#ff6482",  # Rose
    "#30b0c7",  # Teal
    "#00c7be",  # Mint
    "#bf5af2",  # Violet
    "#ff7b54",  # Coral
    "#8e8e93",  # Gray
]

# Hue (góc màu, 0..1) của accent chính #00a3ad, tính bằng colorsys.rgb_to_hls -- đổi số này
# nếu bạn dùng accent khác màu, để _teal_shades()/dải màu heatmap khớp đúng tông accent mới.
ACCENT_HUE = 0.5096


def _hsl_hex(h, s, l):
    """(hue, saturation, lightness) trong [0,1] -> mã màu hex."""
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"


def accent_shades(n, l_lo=0.90, l_hi=0.26):
    """Sinh n sắc độ cùng hue với accent (ACCENT_HUE) từ nhạt (l_lo) đến đậm (l_hi) --
    dùng cho heatmap/thang màu liên tục để đồng bộ 1 họ màu thay vì mỗi nơi 1 tông riêng."""
    return [_hsl_hex(ACCENT_HUE, 0.75, l_lo + (l_hi - l_lo) * i / (n - 1)) for i in range(n)]


def build_color_map(names):
    """Gán màu cố định cho từng tên (nhóm/danh mục/chuỗi bất kỳ). Ưu tiên bảng màu cơ sở
    MAC_COLORS; nếu nhiều hơn số màu sẵn có thì sinh thêm màu phân biệt bằng góc vàng
    (golden angle) để không bao giờ bị trùng màu, vẫn ổn định theo tên (cùng input -> cùng
    màu output, không đổi giữa các lần chạy)."""
    colors = list(MAC_COLORS)
    for k in range(len(names) - len(colors)):
        h = (0.61 + (k + 1) * 0.6180339887) % 1.0  # rải đều sắc độ
        colors.append(_hsl_hex(h, 0.62, 0.55))
    return {name: colors[i] for i, name in enumerate(names)}


# ============================================================
# BIỂU ĐỒ PLOTLY
# ============================================================

PLOTLY_CONFIG = {'scrollZoom': False, 'displayModeBar': False, 'responsive': True}


def format_plotly_fig(fig, is_pie=False):
    """Chuẩn hoá style 1 figure Plotly cho khớp giao diện: bỏ nền, font hệ thống Apple,
    legend nằm ngang phía trên (giống app Xcode), bo góc + đổ bóng cột (khớp CSS đi kèm)."""
    fig.update_layout(
        dragmode=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="-apple-system, BlinkMacSystemFont, sans-serif", color="#1d1d1f"),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, xanchor='left', title_text=''),
        margin=dict(t=10, r=28),
        xaxis=dict(automargin=True),
    )
    if is_pie:
        fig.update_traces(marker=dict(line=dict(color='#ffffff', width=2)))
    else:
        # Bo góc TRÊN cột; cliponaxis=False để bóng đỉnh cột (CSS g.barlayer) không bị cắt.
        fig.update_traces(marker_cornerradius=6, cliponaxis=False, selector=dict(type='bar'))
    return fig


# ============================================================
# CSS
# ============================================================

_CSS = """
<style>
/* Đặt font trên html/body để kế thừa xuống; KHÔNG đặt !important rộng lên mọi phần tử
   để tránh đè font của icon (Material Symbols hoặc icon font khác nếu dùng). */
html, body, .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
.stApp { background-color: #f5f5f7; }

.block-container { max-width: 1200px !important; margin: 0 auto !important; padding-top: 2rem !important; }

/* Thẻ "kính mờ" -- component nền tảng nhất của phong cách này, dùng cho mọi khối nội dung
   (bọc HTML tự dựng trong div.glass-card, hoặc để nguyên -- biểu đồ Plotly/Vega bên dưới
   đã tự có style này). */
.glass-card {
    background: #fff;
    border: 1px solid #d1d1d6;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 1px 1px rgba(0,0,0,0.02);
}

/* Bản tương đương glass-card cho st.container(border=True) -- dùng khi cần bọc nhiều widget
   Streamlit (text_input, button, metric...) vì HTML <div> tự dựng qua st.markdown KHÔNG bọc
   được các widget nằm giữa (mỗi lệnh st.* render 1 khối DOM riêng, trình duyệt tự đóng thẻ
   dở dang) -- st.container(border=True) mới thực sự tạo 1 khối DOM bao trọn nội dung bên trong. */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #fff !important;
    border: 1px solid #d1d1d6 !important;
    border-radius: 16px !important;
    box-shadow: 0 1px 1px rgba(0,0,0,0.02) !important;
}

/* Hàng KPI (stat row) -- gắn key="kpi_row" cho st.container(border=True) bọc các
   st.metric() để chỉ hàng đó có đường kẻ dọc phân cách, không ảnh hưởng các hàng cột khác. */
.st-key-kpi_row [data-testid="stColumn"]:not(:last-child) {
    border-right: 1px solid #d1d1d6;
}
.st-key-kpi_row [data-testid="stColumn"] {
    padding: 0 16px;
}
.st-key-kpi_row [data-testid="stColumn"]:first-child {
    padding-left: 4px;
}

/* Bảng chi tiết dựng bằng HTML thuần (st.dataframe dùng canvas nên khó ép nền trắng) --
   cùng phong cách glass-card, số căn phải kiểu bảng số liệu. */
.data-table-card {
    background: #fff;
    border: 1px solid #d1d1d6;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 1px 1px rgba(0,0,0,0.02);
}
table.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
}
table.data-table th {
    text-align: left;
    padding: 12px 16px;
    color: #6e6e73;
    font-weight: 500;
    border-bottom: 1px solid #d1d1d6;
    white-space: nowrap;
}
table.data-table td {
    padding: 10px 16px;
    border-bottom: 1px solid #ececee;
    font-variant-numeric: tabular-nums;
}
table.data-table tr:last-child td { border-bottom: none; }
table.data-table td:not(:first-child), table.data-table th:not(:first-child) { text-align: right; }

h1, h2, h3 { color: #1d1d1f !important; font-weight: 600 !important; letter-spacing: -0.5px !important; }
hr { border-color: rgba(0,0,0,0.08) !important; }

div[data-testid="stButton"] button[kind="primary"] {
    background-color: #00a3ad !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 500 !important;
    padding: 6px 16px !important;
    box-shadow: 0 2px 5px rgba(0,163,173,0.3) !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stButton"] button[kind="primary"]:hover { transform: scale(0.98); opacity: 0.9; }

div[data-testid="stButton"] button[kind="secondary"] {
    background-color: white !important;
    color: #00a3ad !important;
    border-radius: 8px !important;
    border: 1px solid #d1d1d6 !important;
    font-weight: 500 !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
}
div[data-testid="stButton"] button { width: 100%; }

.stSelectbox > div > div, .stTextInput > div > div > input {
    border-radius: 8px !important;
    border: 1px solid #d1d1d6 !important;
    background-color: rgba(255,255,255,0.8) !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
}

/* Biểu đồ Plotly/Altair: tự động có khung thẻ kính mờ + căn giữa, không cần bọc thêm div. */
[data-testid="stPlotlyChart"], [data-testid="stVegaLiteChart"] {
    display: flex !important;
    justify-content: center !important;
    width: 100% !important;
    margin: 0 auto !important;
    background: #fff;
    border: 1px solid #d1d1d6;
    border-radius: 16px;
    padding: 14px;
    box-shadow: 0 1px 1px rgba(0,0,0,0.02);
}
/* Đổ bóng CẢ KHỐI cho cột & pie (không phải từng path riêng) -> trong 1 cột nhiều segment
   kề nhau hợp thành khối đặc nên chỉ ra bóng viền ngoài, không lem bên trong. Cần
   cliponaxis=False (đặt ở figure, xem format_plotly_fig) để bóng đỉnh cột không bị cắt. */
[data-testid="stPlotlyChart"] g.barlayer { filter: drop-shadow(0 2.5px 2.5px rgba(0,0,0,0.30)); }
[data-testid="stPlotlyChart"] g.pielayer { filter: drop-shadow(0 3px 4px rgba(0,0,0,0.30)); }

/* Mục dạng gập/mở (expander) trông như tiêu đề mục, không như hộp thu gọn mặc định */
[data-testid="stExpander"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    margin: 6px 0 4px 0 !important;
}
[data-testid="stExpander"] details { border: none !important; background: transparent !important; border-radius: 0 !important; }
[data-testid="stExpander"] summary {
    padding: 8px 2px !important;
    border-bottom: 2px solid #d1d1d6 !important;
    border-radius: 0 !important;
    transition: color 0.15s ease, border-color 0.15s ease !important;
}
[data-testid="stExpander"] summary:hover { border-bottom-color: #00a3ad !important; }
[data-testid="stExpander"] summary:hover svg,
[data-testid="stExpander"] summary:hover p { color: #00a3ad !important; }
[data-testid="stExpander"] details[open] > summary { border-bottom-color: #00a3ad !important; }
[data-testid="stExpander"] details[open] > summary svg { color: #00a3ad !important; }
[data-testid="stExpander"] summary p {
    font-size: 1.35rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.4px !important;
    color: #1d1d1f !important;
}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] { padding-top: 12px !important; }

/* Nút đang chọn trong segmented_control -> nền màu accent đặc + chữ trắng + đổ bóng,
   đồng bộ với nút primary. */
[data-testid="stButtonGroup"] { margin-bottom: 10px; }
button[kind="segmented_controlActive"] {
    background-color: #00a3ad !important;
    color: #fff !important;
    border-color: #00a3ad !important;
    box-shadow: 0 2px 5px rgba(0,163,173,0.3) !important;
}

/* ===== Tinh chỉnh riêng cho điện thoại (không ảnh hưởng desktop) ===== */
@media (max-width: 640px) {
    h1 { font-size: 1.9rem !important; line-height: 1.15 !important; }
    h2, [data-testid="stHeading"] h2 { font-size: 1.35rem !important; }
    h3 { font-size: 1.1rem !important; }
    [data-testid="stExpander"] summary p { font-size: 1.15rem !important; }
    .block-container { padding-left: 0.8rem !important; padding-right: 0.8rem !important; padding-top: 1rem !important; }

    .glass-card { padding: 14px !important; height: auto !important; }
    [data-testid="stHorizontalBlock"] { align-items: flex-start !important; }
    [data-testid="stColumn"] { margin-bottom: 12px !important; }

    [data-testid="stPlotlyChart"], [data-testid="stVegaLiteChart"] { padding: 6px !important; }
    [data-testid="stVegaLiteChart"] { overflow-x: auto !important; justify-content: flex-start !important; }
}
</style>
"""


def inject_css():
    """Gọi 1 lần, ngay sau st.set_page_config(). Bơm CSS toàn cục cho phong cách thẻ kính
    mờ + accent teal. Đi kèm .streamlit/config.toml (theme màu nền/accent) trong cùng bộ này
    -- 2 phần bổ sung cho nhau, không thay thế được nhau."""
    st.markdown(_CSS, unsafe_allow_html=True)
