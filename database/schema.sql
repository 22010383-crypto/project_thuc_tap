-- Bảng nhân viên
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,        -- Mã nhân viên (VD: NV001)
    name TEXT NOT NULL,         -- Họ tên
    class_name TEXT,            
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng nhật ký điểm danh
CREATE TABLE IF NOT EXISTS attendance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_str TEXT NOT NULL,    
    subject TEXT DEFAULT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);