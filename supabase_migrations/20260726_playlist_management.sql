-- Chạy một lần trong Supabase SQL Editor cho database đã tồn tại.
-- Thêm thứ tự hiển thị bền vững cho các mục theo dõi.

alter table playlists add column if not exists display_position bigint;

with numbered as (
    select id, row_number() over (order by created_at) * 1000 as sort_value
    from playlists
)
update playlists
set display_position = numbered.sort_value
from numbered
where playlists.id = numbered.id
  and playlists.display_position is null;

alter table playlists alter column display_position set default 1000;
alter table playlists alter column display_position set not null;

create index if not exists playlists_display_position_idx
    on playlists (display_position);
