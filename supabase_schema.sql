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
