# Ghi chú cho Claude Code

- Khi làm việc trên nhánh `claude/youtube-playlist-analytics-2cfzl4` và đã push fix/thay đổi
  lên đó, **tự động đồng bộ (merge/fast-forward) sang `main` luôn, không cần hỏi lại** —
  người dùng đã xác nhận việc này áp dụng cho mọi lần sau, không chỉ 1 lần. Ưu tiên cách an
  toàn: fast-forward hoặc cherry-pick từng commit lên `main` thay vì force-push, trừ khi có lý
  do đặc biệt cần rewrite history (vẫn phải hỏi trước cho force-push/rewrite history).
