-- Bảng sinh viên
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,        -- Mã sinh viên (VD: NV001)
    name TEXT NOT NULL,         -- Họ tên
    department TEXT,            -- Phòng ban
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng nhật ký điểm danh
CREATE TABLE IF NOT EXISTS attendance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_str TEXT NOT NULL,     -- Lưu dạng 'YYYY-MM-DD' để dễ lọc báo cáo
    status TEXT DEFAULT 'Present',
    FOREIGN KEY(user_id) REFERENCES users(id)
);