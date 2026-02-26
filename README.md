# Hệ thống điểm danh nhận diện khuôn mặt

Hệ thống điểm danh tự động bằng nhận diện khuôn mặt (face recognition) và chống giả mạo (anti-spoofing). Giao diện Tkinter, backend Python, database SQLite.

---

## Công nghệ

| Thành phần | Công nghệ |
|------------|-----------|
| Ngôn ngữ | Python 3.8+ |
| Nhận diện khuôn mặt | face_recognition (dlib, HOG) |
| Liveness / chống giả | MediaPipe Face Mesh (blink, head movement), texture (Sobel), blur (Laplacian) |
| Xử lý ảnh | OpenCV, NumPy |
| Database | SQLite |
| Giao diện | Tkinter |
| Export | pandas, openpyxl |

---

## Cấu trúc dự án

```
face_attendance_system/
├── app/
│   ├── config.py              # Đường dẫn, camera, tolerance, ngưỡng EAR...
│   ├── main.py                # Entry: menu chính (Đăng ký, Quản lý SV, Điểm danh)
│   └── gui/
│       ├── register_window.py       # Đăng ký sinh viên + chụp face, lưu encoding
│       ├── user_management_window.py # CRUD sinh viên, xem danh sách, xuất báo cáo
│       └── realtime_attendance.py   # Cửa sổ điểm danh realtime (camera, FPS, số đã điểm danh)
├── core/
│   ├── face_detector.py       # Phát hiện vùng mặt (face_recognition HOG)
│   ├── face_encoder.py        # Mã hóa face → 128-D, load/save pickle (encodings, ids)
│   ├── face_matcher.py        # So khớp encoding với known_encodings
│   └── realtime_engine.py     # Engine chính: nhận diện + anti-spoof + render, double buffer, thread xử lý
├── database/
│   ├── db_manager.py          # Kết nối SQLite, students, sessions, attendance_logs, cooldown, mark_attendance
│   └── schema.sql             # Định nghĩa bảng students, sessions, attendance_logs (có liveness_score, liveness_details)
├── utils/
│   ├── logger.py              # Setup logging
│   ├── image_utils.py         # cv2 → PIL/PhotoImage (hiển thị Tkinter)
│   └── video_stream.py        # VideoStream (thread đọc camera, queue 1 frame)
├── data/
│   ├── database/             # attendance.db
│   └── encodings/            # face_encodings.pkl (encodings + ids)
├── logs/                     # app.log
├── exports/                  # Báo cáo Excel xuất từ quản lý SV
├── docs/
│   └── RECOGNITION_AND_ANTISPOOF.md   # Chi tiết logic nhận diện và chống giả mạo
├── migrate_database.py       # Thêm cột liveness vào attendance_logs (nếu DB cũ)
├── run_realtime.py           # Chạy nhanh cửa sổ điểm danh realtime
├── requirements.txt
└── README.md
```

---

## Chức năng

### 1. Đăng ký mới (Register)

- Nhập MSSV, họ tên, lớp.
- Bật camera, chụp ảnh khuôn mặt.
- `FaceEncoder`: detect face → encode 128-D → lưu vào `face_encodings.pkl` (encodings + ids).
- Ghi thông tin sinh viên vào bảng `students` (db_manager).

### 2. Quản lý sinh viên

- Xem, thêm, sửa, xóa sinh viên (bảng `students`).
- Xuất báo cáo điểm danh ra Excel (từ `attendance_logs` + sessions).

### 3. Điểm danh Realtime

- Mở camera, load `face_encodings.pkl` (encodings, ids).
- Tạo phiên mới (`sessions`), khởi tạo `OptimizedAttendanceSystem` (realtime_engine).
- Luồng xử lý:
  - **Capture:** đọc frame từ camera, ghi vào `SharedFrameBuffer`.
  - **AI thread:** lấy frame từ buffer → resize 0.4x → `face_locations` (HOG) → `face_encodings` → so khớp với known_encodings (tolerance 0.45) → với mỗi face: `RealtimeAntiSpoof.check(face_roi, person_id)`.
  - Người đã điểm danh trong phiên (`checked_in`) được bỏ qua antispoof và không ghi DB lại.
  - Nếu nhận diện được + anti-spoof pass (`is_real`) và chưa trong `checked_in`: gọi `db.mark_attendance(session_id, student_id, ...)` với confidence_score, liveness_score, liveness_details; thêm vào `checked_in`.
- Hiển thị: khung **xanh** (đã điểm danh / người thật), khung **đỏ** (chưa nhận diện / không phải người thật). FPS và số người đã điểm danh hiển thị trên giao diện.

---

## Logic xử lý chính

### Nhận diện khuôn mặt

1. Frame resize 0.4x → `face_recognition.face_locations(rgb, model='hog')`.
2. `face_recognition.face_encodings(rgb, face_locations)` → 128-D mỗi mặt.
3. So khớp: `compare_faces` + `face_distance` với `known_encodings`, tolerance 0.45 → `person_id`, confidence.

### Chống giả mạo (Anti-spoof)

- Mỗi mặt có state riêng theo `person_id` (blink_count, movement_detected, ear_history, head_positions).
- **Khi có MediaPipe:**
  - **Chớp mắt:** EAR (Eye Aspect Ratio) từ Face Mesh; EAR < 0.25 coi là đóng, trước đó > 0.27 là mở; debounce 0.35s → tăng `blink_count`.
  - **Cử động đầu:** theo dõi vị trí mũi (landmark 1); movement > 0.04 → `movement_detected = True`.
  - **Texture:** Sobel gradient + variance theo block 16×16 (real face nhiều biến thiên, ảnh/màn hình mịn) → texture_score ≥ 0.42.
  - **Blur:** Laplacian variance → blur_score ≥ 0.28.
  - **Nghi màn hình:** tỉ lệ pixel rất sáng (V>245) hoặc độ sáng quá đều → ép texture xuống, reject.
  - **Kết luận:** `is_real` = (blink ≥ 1 hoặc movement_detected) và texture_ok và blur_ok và không screen_like.
- **Khi không có MediaPipe:** chỉ texture + blur + screen_like (ngưỡng chặt hơn, xem `_check_texture_only`).

Chi tiết đầy đủ: [docs/RECOGNITION_AND_ANTISPOOF.md](docs/RECOGNITION_AND_ANTISPOOF.md).

### Database và cooldown

- **students:** student_id, name, class_name.
- **sessions:** session_id, subject_name, start_time, end_time.
- **attendance_logs:** session_id, student_id, checkin_time, verification_method, confidence_score, liveness_score, liveness_passed, liveness_details; UNIQUE(session_id, student_id).
- Cooldown: `DatabaseManager.can_checkin(student_id, session_id)` kiểm tra đã điểm danh trong phiên hoặc thời gian chờ giữa hai lần điểm danh (cấu hình theo cooldown_minutes). Chỉ khi `can_checkin` True mới ghi `mark_attendance`.

---

## Cấu hình

- **app/config.py:** `DB_PATH`, `ENCODINGS_PATH`, `RESIZE_SCALE`, `DETECTION_MODEL` (hog/cnn), `MATCH_TOLERANCE`, `EYE_AR_THRESH`, `YAW_THRESH`, camera index, log path...
- Ngưỡng anti-spoof (blink, movement, texture, blur, screen_like) nằm trong `core/realtime_engine.py` (class `RealtimeAntiSpoof`).

---

## Cài đặt và chạy

### Cài đặt phụ thuộc

```bash
pip install -r requirements.txt
```

Cần: `opencv-python`, `face-recognition`, `dlib`, `numpy`, `pandas`, `openpyxl`, `Pillow`. Tùy chọn: `mediapipe` (để dùng blink + head movement).

### Khởi tạo DB (lần đầu hoặc DB cũ thiếu cột liveness)

```bash
python migrate_database.py
# Trả lời y khi được hỏi
```

### Chạy ứng dụng

```bash
python -m app.main
```

Menu chính: **Đăng ký mới**, **Quản lý sinh viên**, **Điểm danh (Realtime)**, **Thoát**.

### Chạy nhanh cửa sổ điểm danh realtime

```bash
python run_realtime.py
```

---

## Database schema (tóm tắt)

- **students:** student_id (TEXT PK), name, class_name, created_at.
- **sessions:** session_id (INTEGER PK), subject_name, start_time, end_time.
- **attendance_logs:** log_id (PK), session_id, student_id, checkin_time, verification_method, confidence_score, liveness_score, liveness_passed, liveness_details; UNIQUE(session_id, student_id).

---

 
