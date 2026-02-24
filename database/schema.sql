-- 1. Bảng Sinh viên  
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,    
    name TEXT NOT NULL,             
    class_name TEXT NOT NULL,        
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Bảng Phiên học (Quản lý từng buổi điểm danh)
CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_name TEXT NOT NULL,     -- Tên môn học 
    room_name TEXT,                 -- Phòng học (VD: A2-304)
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Thời gian bắt đầu mở cam
    end_time TIMESTAMP,             -- Thời gian kết thúc 
);

-- 3. Bảng Nhật ký điểm danh (Kết quả) - Enhanced with Liveness
CREATE TABLE IF NOT EXISTS attendance_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,    -- Thuộc phiên nào?
    student_id TEXT NOT NULL,       -- Sinh viên nào?
    checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Thời gian quét
    
    -- Trạng thái nhận diện:
    -- 'Auto': Tự động quét
    -- 'Manual': Giáo viên tick tay (nếu SV quên thẻ/mặt lỗi)
    verification_method TEXT DEFAULT 'Auto', 
    
    -- Điểm tin cậy (Confidence score của AI, tùy chọn lưu để debug)
    confidence_score REAL,
    
    -- === NEW: Liveness Detection Scores ===
    liveness_score REAL DEFAULT 0.0,        -- Overall liveness score (0-1)
    liveness_passed BOOLEAN DEFAULT 1,      -- Did liveness check pass?
    liveness_details TEXT,                  -- JSON string with detailed liveness info
    
    -- Khóa ngoại
    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    
    -- QUAN TRỌNG: Ràng buộc này ngăn chặn 1 SV điểm danh 2 lần trong 1 buổi
    UNIQUE(session_id, student_id)
);

-- Tạo Index để tìm kiếm nhanh hơn khi dữ liệu lớn
CREATE INDEX idx_logs_student ON attendance_logs(student_id);
CREATE INDEX idx_logs_session ON attendance_logs(session_id);