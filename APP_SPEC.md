# Đặc tả toàn diện: YouTube Playlist Tracker

> File này mô tả đầy đủ mục đích, kiến trúc, dữ liệu, logic nghiệp vụ và giao diện của app,
> đủ chi tiết để một AI/developer khác có thể xây dựng lại **from scratch** mà không cần đọc
> source code gốc.

## 1. Mục đích app

Một web app nhỏ, chạy được cho 1 người dùng (không có đăng nhập/nhiều user), dùng để:

- Theo dõi (track) các playlist hoặc video YouTube theo thời gian.
- Mỗi lần "cập nhật", app gọi YouTube Data API để lấy số liệu view/like mới nhất của từng
  video, lưu thành 1 "snapshot" (bản ghi lịch sử) vào database.
- Hiển thị: tổng view/like hiện tại, thay đổi (delta) so với lần cập nhật gần nhất, thay đổi
  từ đầu ngày hôm nay (theo giờ Việt Nam, UTC+7), bảng chi tiết từng video trong playlist, và
  biểu đồ cột so sánh giữa các video.
- Người dùng chủ động bấm nút để cập nhật số liệu (không có cron/job nền tự động).

## 2. Tech stack

| Thành phần | Công nghệ |
|---|---|
| Frontend + backend | [Streamlit](https://streamlit.io/) (Python, server-rendered, single script chạy lại toàn bộ mỗi lần tương tác) |
| Database | Supabase (Postgres + REST API qua thư viện `supabase-py`) |
| Nguồn dữ liệu | YouTube Data API v3 (gọi trực tiếp bằng `requests`, không dùng SDK Google) |
| Biểu đồ | Plotly Express |
| Bảng dữ liệu | Pandas + HTML thuần tự dựng (không dùng `st.dataframe` để kiểm soát style) |
| Ngôn ngữ giao diện | Tiếng Việt (toàn bộ label, message) |

`requirements.txt`:
```
streamlit
supabase
plotly
pandas
requests
```

## 3. Cấu trúc file

```
app.py               # Giao diện Streamlit chính (toàn bộ UI, chạy từ trên xuống mỗi lần rerun)
design_kit.py        # CSS inject + helper màu sắc + helper format biểu đồ Plotly (tái dùng từ 1 dự án khác)
youtube_api.py       # Gọi YouTube Data API v3, parse URL, không phụ thuộc Streamlit
db.py                # Kết nối Supabase + toàn bộ CRUD/business logic ghi dữ liệu
analytics.py         # Tính toán delta & tổng hợp số liệu (thuần Python, không phụ thuộc DB/Streamlit)
supabase_schema.sql  # DDL tạo 3 bảng + policy RLS tuỳ chọn
.streamlit/config.toml           # Theme màu Streamlit
.streamlit/secrets.toml.example  # Mẫu file secrets (không commit bản thật)
```

Nguyên tắc tách lớp: `youtube_api.py` và `analytics.py` là pure functions, không import
Streamlit hay Supabase — dễ test độc lập. `db.py` là lớp duy nhất biết cả Supabase lẫn
YouTube API (orchestration). `app.py` chỉ gọi hàm từ các module kia, không chứa logic nghiệp vụ.

## 4. Data model (Supabase / Postgres)

3 bảng, quan hệ 1 playlist → nhiều video → nhiều snapshot:

```sql
create extension if not exists pgcrypto;

create table playlists (
    id uuid primary key default gen_random_uuid(),
    youtube_playlist_id text unique,   -- ID playlist thật của YouTube;
                                        -- nếu là video đơn lẻ (không thuộc playlist nào)
                                        -- thì lưu giá trị giả "video:<video_id>" để vẫn unique
    title text not null,
    url text not null,                 -- URL gốc người dùng nhập
    created_at timestamptz not null default now()
);

create table videos (
    id uuid primary key default gen_random_uuid(),
    youtube_video_id text not null,
    playlist_id uuid references playlists(id) on delete cascade,
    title text not null,
    position int,                      -- thứ tự video trong playlist (từ playlistItems.snippet.position)
    created_at timestamptz not null default now()
);

create table snapshots (
    id bigint generated always as identity primary key,
    video_id uuid not null references videos(id) on delete cascade,
    views bigint not null,
    likes bigint not null,
    captured_at timestamptz not null default now()
);

create index snapshots_video_captured_idx on snapshots (video_id, captured_at desc);
create index videos_playlist_idx on videos (playlist_id);
```

Điểm thiết kế quan trọng:
- **Video đơn lẻ** (người dùng dán URL `watch?v=...` thay vì playlist) vẫn được lưu như 1
  "playlist" có đúng 1 video con, để tái dùng toàn bộ UI/logic tính playlist metrics. ID giả
  `"video:<video_id>"` đảm bảo không trùng với ID playlist thật và tránh thêm trùng lặp.
- **Snapshot** là append-only (không update/xoá) — mỗi lần "cập nhật" chỉ insert thêm dòng
  mới, giữ lại toàn bộ lịch sử để tính delta theo thời gian.
- Xoá 1 playlist sẽ cascade xoá video + snapshot liên quan (không có tính năng xoá trên UI
  hiện tại, nhưng schema đã hỗ trợ).

### Row Level Security (RLS)

Mặc định khuyến nghị dùng **Supabase secret key** (trước đây gọi `service_role`) cho
`SUPABASE_KEY` vì app chạy hoàn toàn phía server, không lộ key ra trình duyệt → không cần bật
RLS. Nếu dùng publishable/anon key thì cần bật RLS + policy "allow all" (xem block SQL cuối
file `supabase_schema.sql`), vì Supabase bật RLS mặc định trên bảng mới và sẽ chặn hết
đọc/ghi nếu không có policy.

## 5. Tích hợp YouTube Data API v3

Gọi trực tiếp bằng `requests`, base URL `https://www.googleapis.com/youtube/v3`, tất cả
request kèm query param `key=<API_KEY>`.

### 5.1 Parse URL người dùng nhập (`parse_youtube_url`)

Nhận 1 URL bất kỳ, trả về tuple `("playlist", id)` hoặc `("video", id)`. Thứ tự nhận diện:
1. Query param `list=` → playlist.
2. Host là `youtu.be` → path là video id.
3. Query param `v=` → video.
4. Path chứa `/shorts/<11 ký tự>` hoặc `/embed/<11 ký tự>` (regex) → video.
5. Không khớp gì → raise lỗi "Không nhận diện được URL YouTube hợp lệ".

### 5.2 Các hàm gọi API

- `fetch_playlist_title(playlist_id, api_key)` — endpoint `playlists?part=snippet&id=...`,
  lấy `items[0].snippet.title`. Raise lỗi nếu playlist không tồn tại.
- `fetch_playlist_video_ids(playlist_id, api_key)` — endpoint `playlistItems`, phân trang bằng
  `pageToken` (mỗi trang tối đa `maxResults=50`), lặp tới khi hết `nextPageToken`. Bỏ qua item
  có `resourceId.kind != "youtube#video"`. Trả về list `{video_id, title, position}`.
- `fetch_video_stats(video_ids, api_key)` — endpoint `videos?part=snippet,statistics`, gộp tối
  đa 50 id/request (giới hạn API), trả về dict `video_id -> {title, views, likes}` (ép kiểu
  `int`, mặc định 0 nếu thiếu field).
- `fetch_single_video(video_id, api_key)` — gọi `fetch_video_stats` với 1 id, raise lỗi nếu
  không tìm thấy.

Mọi lỗi HTTP (status not ok) raise `YouTubeAPIError` với message lấy từ
`error.message` trong JSON response của Google (hoặc raw text nếu không parse được JSON).

## 6. Business logic ghi dữ liệu (`db.py`)

### 6.1 `add_tracked_item(url)` — Thêm mục theo dõi mới

1. Parse URL → `(kind, yt_id)`.
2. Nếu `kind == "playlist"`:
   - Kiểm tra đã tồn tại playlist với `youtube_playlist_id == yt_id` chưa → nếu có, trả về
     luôn (không tạo trùng, không fetch lại từ YouTube).
   - Nếu chưa: fetch title playlist, insert row `playlists`.
   - Fetch toàn bộ video id trong playlist (phân trang) + fetch stats hàng loạt.
   - Insert hàng loạt vào `videos` (bulk insert 1 lần).
   - Insert snapshot đầu tiên cho từng video (bulk insert 1 lần, cùng 1 timestamp `now()`).
3. Nếu `kind == "video"`:
   - ID playlist giả = `f"video:{yt_id}"`. Kiểm tra tồn tại tương tự → trả về nếu đã có.
   - Fetch info video đơn, insert `playlists` (title = title video), insert 1 row `videos`
     (position=0), insert 1 snapshot.
4. Trả về row playlist (dict) vừa tạo hoặc đã tồn tại.

### 6.2 `refresh_playlist(playlist_row)` — Cập nhật 1 playlist

- Lấy toàn bộ video hiện có của playlist trong DB (không gọi lại `playlistItems` — tức là
  **không tự phát hiện video mới thêm vào playlist trên YouTube sau khi đã track**, chỉ cập
  nhật số liệu cho các video đã có trong DB).
- `fetch_video_stats` cho toàn bộ video id đó, insert bulk 1 snapshot mới/video (cùng
  timestamp).

### 6.3 `refresh_all()` — Cập nhật tất cả playlist đang theo dõi

Lặp qua `list_playlists()`, gọi `refresh_playlist` cho từng cái tuần tự.

### 6.4 Hàm đọc dữ liệu

- `list_playlists()` — tất cả playlist, sort `created_at desc`.
- `get_videos_for_playlist(playlist_id)` — sort theo `position asc`.
- `get_snapshots_for_videos(video_ids)` — lấy snapshot của nhiều video 1 lần, group thành dict
  `video_id -> [snapshot...]` sort `captured_at asc` (cũ → mới). Dùng để tránh N+1 query khi
  hiển thị cả playlist.

Supabase client được cache bằng `st.cache_resource` (khởi tạo 1 lần/session).

## 7. Logic tính toán số liệu (`analytics.py`)

Thuần Python, không đụng DB. Input là list snapshot đã sort cũ→mới của 1 video.

### 7.1 `compute_video_metrics(video, snapshots)`

- Nếu không có snapshot nào: mọi giá trị = 0.
- `latest` = snapshot cuối cùng (mới nhất). `previous` = snapshot áp chót (nếu có ≥ 2 bản ghi).
- **Δ so với lần cập nhật trước** = `latest - previous` (0 nếu chưa có lần trước).
- **Mốc "đầu ngày hôm nay"**: tính "hôm nay" theo timezone `Asia/Ho_Chi_Minh` (UTC+7), lấy thời
  điểm 00:00:00 giờ VN hôm nay, convert sang UTC để so sánh với `captured_at` (lưu ở UTC).
  Duyệt tuần tự các snapshot (đã sort cũ→mới), `baseline_today` = snapshot **cuối cùng có
  `captured_at < today_start_utc`** (tức bản ghi gần nhất TRƯỚC khi sang ngày mới). Nếu không
  có snapshot nào trước mốc đó (video mới track trong chính ngày hôm nay), dùng snapshot đầu
  tiên của video làm mốc.
- **Δ hôm nay** = `latest - baseline_today`.
- Trả về dict: `video_id, title, views, likes, delta_update_views, delta_update_likes,
  delta_today_views, delta_today_likes`.

### 7.2 `compute_playlist_metrics(videos, snapshots_by_video)`

Gọi `compute_video_metrics` cho từng video, rồi cộng dồn (`sum`) tất cả field số thành
`totals` cấp playlist. Trả về `(per_video: list[dict], totals: dict)`.

## 8. Giao diện & luồng tương tác (`app.py`)

Trang đơn (single page), `layout="wide"`, tiêu đề "YouTube Playlist Tracker".

### 8.1 Khối "Thêm mục theo dõi"
- 1 ô text input (URL) + 1 nút "Theo dõi" (primary), nằm trong card viền bo góc.
- Bấm nút: validate không rỗng → gọi `add_tracked_item` (có spinner) → bắt `YouTubeAPIError`
  hiển thị `st.error` → nếu thành công: clear cache, `st.success`, `st.rerun()`.

### 8.2 Chọn playlist đang theo dõi
- Nếu chưa có playlist nào: hiện `st.info` + dừng render (`st.stop()`).
- `st.selectbox` liệt kê tất cả playlist (label = title), chọn 1 cái làm "playlist đang xem".

### 8.3 Nút cập nhật
- 2 cột: "Cập nhật playlist này" (primary, gọi `refresh_playlist`) và "Cập nhật tất cả
  playlist" (secondary, gọi `refresh_all`). Cả 2 đều: spinner → clear cache → success → rerun.

### 8.4 Hàng KPI (4 thẻ số liệu, `st.metric` trong 1 container có đường kẻ dọc phân cách giữa
các cột)
1. Tổng lượt view (kèm delta "hôm nay")
2. Tổng lượt like (kèm delta "hôm nay")
3. Δ View (lần cập nhật trước) — không kèm delta phụ
4. Δ Like (lần cập nhật trước) — không kèm delta phụ

Nếu playlist chưa có video nào: `st.info` + `st.stop()`.

### 8.5 Bảng chi tiết từng video
- Build từ `per_video` (list dict) qua Pandas, rename cột sang tiếng Việt.
- Render bằng HTML thuần tự dựng (không dùng `st.dataframe`) để kiểm soát style (nền trắng,
  số căn phải, định dạng `{:,}`). Lý do ghi trong code: `st.dataframe` dùng canvas nên khó ép
  style nền trắng theo theme.

### 8.6 Biểu đồ so sánh giữa các video
- `st.segmented_control` chọn 1 trong 4 chỉ số: Tổng view / Tổng like / Δ View hôm nay / Δ
  Like hôm nay.
- Bar chart Plotly Express, mỗi video 1 màu (theo `build_color_map`, ổn định theo tên).
- Tên video dài được tự động ngắt dòng tại khoảng trắng (`wrap_label`, `max_len=14`) để trục X
  hiển thị ngang (`tickangle=0`) thay vì bị xoay chéo khó đọc.
- Ẩn legend (đã đủ thông tin qua trục X), ẩn tiêu đề trục.

## 9. Design system (`design_kit.py`)

Phong cách "iOS/macOS glass card", tái dùng từ 1 dự án khác (Forest Dashboard) — module này
độc lập, có thể copy nguyên sang app Streamlit khác.

### 9.1 Theme màu (`.streamlit/config.toml`)
```toml
[theme]
primaryColor = "#00a3ad"           # accent teal
backgroundColor = "#f5f5f7"        # nền xám nhạt kiểu macOS
secondaryBackgroundColor = "#e6e9ef"
textColor = "#1d1d1f"
font = "sans serif"
```

### 9.2 CSS inject (`inject_css()`, gọi 1 lần ngay sau `st.set_page_config`)
- Font hệ thống Apple (`-apple-system, BlinkMacSystemFont, ...`).
- `.block-container` giới hạn max-width 1200px, căn giữa.
- "Glass card": nền trắng, viền `#d1d1d6`, bo góc 16px, shadow rất nhẹ. Áp dụng qua class
  `.glass-card` (cho HTML tự dựng) hoặc tự động cho `st.container(border=True)` (target CSS
  selector `div[data-testid="stVerticalBlockBorderWrapper"]`) vì HTML thuần không bọc được
  widget Streamlit (mỗi lệnh `st.*` render 1 khối DOM riêng).
- Hàng KPI: dùng `st.container(border=True, key="kpi_row")` → CSS chọn theo
  `.st-key-kpi_row` để chỉ hàng đó có đường kẻ dọc phân cách giữa các cột.
- Bảng HTML tự dựng: card style + `font-variant-numeric: tabular-nums`, cột số căn phải.
- Nút primary: nền teal `#00a3ad`, chữ trắng, bo góc 8px, shadow teal nhạt, hover
  scale(0.98)+opacity. Nút secondary: nền trắng, chữ teal, viền xám.
- Input/selectbox: bo góc 8px, viền xám nhạt.
- Biểu đồ Plotly/Vega: tự động bọc trong khung glass-card + đổ bóng khối cho bar/pie
  (`filter: drop-shadow`, cần `cliponaxis=False` ở phía Plotly để bóng không bị cắt).
- `segmented_control` đang chọn: nền teal đặc, chữ trắng (đồng bộ nút primary).
- Responsive: `@media (max-width: 640px)` giảm cỡ chữ heading, giảm padding, cho phép
  scroll ngang riêng cho Vega chart.

### 9.3 Helper màu (`build_color_map`, `MAC_COLORS`, `accent_shades`)
- `MAC_COLORS`: bảng 16 màu cố định lấy cảm hứng từ hệ màu iOS/macOS (Blue, Green, Orange,
  Red, Indigo, Purple...).
- `build_color_map(names)`: gán màu ổn định (deterministic) cho từng tên trong danh sách —
  cùng tên luôn ra cùng màu dù rerun. Ưu tiên dùng bảng `MAC_COLORS`; nếu số lượng tên nhiều
  hơn 16, sinh thêm màu bằng kỹ thuật "golden angle" (`0.6180339887`) trên vòng hue để rải màu
  đều, không bao giờ trùng nhau.
- `accent_shades(n, l_lo, l_hi)`: sinh dải màu cùng hue với accent chính (dùng cho heatmap/thang
  màu liên tục nếu cần — hiện app này không dùng heatmap).

### 9.4 Helper biểu đồ (`format_plotly_fig`, `PLOTLY_CONFIG`)
- Bỏ nền (transparent), set font Apple, legend nằm ngang phía trên bên trái, margin gọn.
- Bo góc trên của cột bar (`marker_cornerradius=6`), `cliponaxis=False` để không cắt bóng đổ.
- `PLOTLY_CONFIG = {'scrollZoom': False, 'displayModeBar': False, 'responsive': True}` — ẩn
  toolbar Plotly, tắt zoom scroll (tránh conflict scroll trang), responsive theo khung chứa.

## 10. Cấu hình & secrets

`.streamlit/secrets.toml` (không commit, đã có trong `.gitignore`; file mẫu
`secrets.toml.example` được commit):
```toml
YOUTUBE_API_KEY = "..."
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "..."   # nên dùng "secret key" (service_role), không phải publishable/anon key
```

## 11. Setup từ đầu (thứ tự làm lại app)

1. Tạo Google Cloud project → bật **YouTube Data API v3** → tạo API key.
2. Tạo Supabase project → chạy `supabase_schema.sql` trong SQL Editor → lấy Project URL +
   secret key.
3. Tạo `.streamlit/secrets.toml` từ file mẫu, điền 3 giá trị trên.
4. `pip install -r requirements.txt` rồi `streamlit run app.py`.
5. Deploy: push GitHub → Streamlit Community Cloud → New app → paste nội dung secrets qua
   UI (App settings → Secrets), không upload file.

## 12. Giới hạn / hành vi cần biết khi implement lại

- Không có xác thực người dùng — bất kỳ ai truy cập URL app đều thấy chung 1 danh sách theo
  dõi (thiết kế cho 1 người dùng cá nhân).
- Không có nút xoá playlist/video trên UI (dù schema hỗ trợ cascade delete).
- `refresh_playlist` **không** phát hiện video mới được thêm vào playlist YouTube sau khi đã
  track lần đầu — chỉ cập nhật số liệu cho video đã lưu trong DB. Muốn lấy video mới phải
  track lại (nhưng `add_tracked_item` sẽ early-return vì playlist đã tồn tại) → đây là hạn chế
  đã biết, có thể cải tiến khi xây lại (ví dụ: thêm hàm đồng bộ lại danh sách video mỗi lần
  refresh).
- Cập nhật là thao tác thủ công (người dùng bấm nút), không có scheduler/cron chạy nền.
- YouTube API có quota (mặc định 10,000 unit/ngày); mỗi lần refresh tốn quota theo số lượng
  video (gọi `videos.list` theo batch 50 id = tương đối rẻ, nhưng track playlist lớn lần đầu
  sẽ tốn thêm quota cho `playlistItems.list` phân trang).
- Delta "hôm nay" phụ thuộc **thời điểm các lần refresh trước đó** (baseline là snapshot cuối
  cùng trước 00:00 giờ VN) — nếu không refresh trong 1 ngày, delta hôm nay của ngày kế tiếp sẽ
  tính từ bản ghi cũ nhất còn lại trước mốc, không phải "chỉ trong hôm nay" theo nghĩa chặt.
