# YouTube Playlist Tracker

App Streamlit theo dõi lượt view và lượt like của video/playlist YouTube theo thời gian, lưu lịch sử vào Supabase.

## 1. Tạo YouTube Data API v3 key

1. Vào [Google Cloud Console](https://console.cloud.google.com/) → tạo project (hoặc dùng project sẵn có).
2. APIs & Services → Library → bật **YouTube Data API v3**.
3. APIs & Services → Credentials → Create credentials → API key.

## 2. Tạo project Supabase

1. Tạo project mới tại [supabase.com](https://supabase.com/).
2. Vào **SQL Editor** → chạy nội dung file [`supabase_schema.sql`](./supabase_schema.sql) trong repo này để tạo các bảng `playlists`, `videos`, `snapshots`.
3. Lấy **Project URL** và **API key** (Settings → API) để dùng ở bước 3.

## 3. Cấu hình secrets

Copy file mẫu và điền giá trị thật:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Sửa `.streamlit/secrets.toml`:

```toml
YOUTUBE_API_KEY = "..."
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "..."
```

File này đã được `.gitignore`, không commit lên git.

## 4. Chạy local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 5. Sử dụng

- Nhập URL video hoặc playlist YouTube vào ô "Thêm mục theo dõi" → bấm **Theo dõi**.
- Chọn playlist/video muốn xem trong danh sách.
- Bấm **Cập nhật playlist này** để lấy số liệu mới nhất cho playlist đang chọn, hoặc **Cập nhật tất cả playlist** để cập nhật toàn bộ các mục đang theo dõi.
- App hiển thị: tổng view/like, thay đổi so với lần cập nhật trước, thay đổi từ đầu ngày (theo giờ Việt Nam), bảng chi tiết từng video, và biểu đồ so sánh giữa các video trong playlist.

## 6. Deploy lên Streamlit Community Cloud

1. Push repo lên GitHub.
2. Vào [share.streamlit.io](https://share.streamlit.io/) → New app → chọn repo, branch, file `app.py`.
3. Vào **App settings → Secrets** → dán nội dung giống `.streamlit/secrets.toml` (không upload file, chỉ paste nội dung qua UI).
4. Deploy.

## Cấu trúc dự án

| File | Vai trò |
|---|---|
| `app.py` | Giao diện Streamlit chính |
| `design_kit.py` | CSS/tiện ích giao diện (thẻ kính mờ, màu accent teal, style biểu đồ Plotly) |
| `youtube_api.py` | Gọi YouTube Data API v3 |
| `db.py` | Kết nối Supabase, CRUD playlists/videos/snapshots |
| `analytics.py` | Tính delta (so lần cập nhật trước / so đầu ngày) và tổng hợp số liệu |
| `supabase_schema.sql` | DDL tạo bảng trên Supabase |
