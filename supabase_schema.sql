-- Chạy trong Supabase SQL editor (Project > SQL Editor > New query) trước khi dùng app.

create extension if not exists pgcrypto;

create table if not exists playlists (
    id uuid primary key default gen_random_uuid(),
    youtube_playlist_id text unique,      -- null nếu là video đơn lẻ; video đơn lẻ dùng "video:<id>"
    title text not null,
    url text not null,
    created_at timestamptz not null default now()
);

create table if not exists videos (
    id uuid primary key default gen_random_uuid(),
    youtube_video_id text not null,
    playlist_id uuid references playlists(id) on delete cascade,
    title text not null,
    position int,
    created_at timestamptz not null default now()
);

create table if not exists snapshots (
    id bigint generated always as identity primary key,
    video_id uuid not null references videos(id) on delete cascade,
    views bigint not null,
    likes bigint not null,
    captured_at timestamptz not null default now()
);

create index if not exists snapshots_video_captured_idx on snapshots (video_id, captured_at desc);
create index if not exists videos_playlist_idx on videos (playlist_id);

-- ============================================================
-- TÙY CHỌN: chỉ cần chạy khối dưới đây nếu bạn dùng "publishable key" (anon key) cho
-- SUPABASE_KEY thay vì "secret key" (service_role key). Supabase bật Row Level Security
-- (RLS) mặc định trên các bảng mới; nếu không có policy, publishable key sẽ bị chặn hoàn
-- toàn (kể cả đọc/ghi), gây lỗi "new row violates row-level security policy for table ...".
-- Nếu bạn đã dùng secret key trong SUPABASE_KEY thì KHÔNG cần chạy khối này (secret key bỏ
-- qua RLS). App này chạy hoàn toàn phía server (Streamlit), không có nhiều người dùng/đăng
-- nhập riêng biệt, nên policy "cho phép tất cả" dưới đây là đủ dùng.
-- ============================================================

alter table playlists enable row level security;
alter table videos enable row level security;
alter table snapshots enable row level security;

drop policy if exists "allow all for anon/authenticated" on playlists;
create policy "allow all for anon/authenticated" on playlists
    for all to anon, authenticated using (true) with check (true);

drop policy if exists "allow all for anon/authenticated" on videos;
create policy "allow all for anon/authenticated" on videos
    for all to anon, authenticated using (true) with check (true);

drop policy if exists "allow all for anon/authenticated" on snapshots;
create policy "allow all for anon/authenticated" on snapshots
    for all to anon, authenticated using (true) with check (true);
