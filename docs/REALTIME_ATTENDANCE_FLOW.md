# Realtime Attendance – Flow code và thuật toán

Tài liệu mô tả **chi tiết** luồng chạy, thuật toán và các file liên quan của chức năng **Điểm danh Realtime** (cửa sổ `RealtimeAttendanceWindow`).

---

## 1. File chính và phụ thuộc

### 1.1 File giao diện (entry point)

| File | Vai trò |
|------|--------|
| **`app/gui/realtime_attendance.py`** | Cửa sổ Tkinter: tạo UI, khởi tạo hệ thống, vòng lặp đọc camera → đẩy frame → nhận frame đã vẽ → hiển thị FPS & số đã điểm danh. |

### 1.2 File được gọi trực tiếp từ realtime_attendance.py

| File | Nội dung sử dụng |
|------|------------------|
| **`app/config.py`** | `Config.ENCODINGS_PATH` (đường dẫn file pickle encodings). |
| **`database/db_manager.py`** | `DatabaseManager(cooldown_minutes=0.05)`, `create_session(subject)`, `mark_attendance(...)` (gọi từ engine). |
| **`core/realtime_engine.py`** | `OptimizedAttendanceSystem(encodings, ids, db, session_id)`, `start()`, `put_frame()`, `get_display_frame()`, `get_count()`, `stop()`. |

### 1.3 Thư viện chuẩn / bên ngoài

- **tkinter**: Cửa sổ, Canvas, Label, Button.
- **cv2 (OpenCV)**: `VideoCapture`, `read()`, `resize()`, `cvtColor()` (trong engine + khi chuyển ảnh lên canvas).
- **pickle**: Đọc `face_encodings.pkl`.
- **time**: Đo FPS (`perf_counter`), cập nhật FPS định kỳ (`time.time()`).
- **datetime, timedelta**: Tạo tên phiên, thời gian kết thúc phiên (45 phút), đếm ngược thời gian còn lại.
- **PIL (Image, ImageTk)** (tùy chọn): Chuyển frame RGB → `PhotoImage` cho Canvas; nếu không có thì dùng PPM.

---

## 2. Luồng chạy tổng thể (flow)

```
[Main / run_realtime]
    │
    └─► RealtimeAttendanceWindow(parent, on_close)
            │
            ├─► __init__:
            │       create_ui()              # Thanh trên (session, FPS, timer), Canvas, thanh dưới (count, STOP)
            │       after(100, initialize_system)
            │       protocol("WM_DELETE_WINDOW", cleanup)
            │
            ├─► initialize_system (chạy sau 100ms):
            │       ├─ Kiểm tra Config.ENCODINGS_PATH tồn tại
            │       ├─ pickle.load(encodings, ids)
            │       ├─ DatabaseManager(0.05) → db
            │       ├─ db.create_session("RT_HHMM") → session_id
            │       ├─ end_time = now + 45 phút
            │       ├─ OptimizedAttendanceSystem(encodings, ids, db, session_id) → system
            │       ├─ system.start()        # Bật thread _process_loop
            │       ├─ cv2.VideoCapture(0), set 640x480, 30fps, buffer 1
            │       ├─ running = True
            │       ├─ update_loop()        # Bắt đầu vòng lặp hiển thị
            │       └─ update_timer()       # Bắt đầu đếm ngược
            │
            ├─► update_loop (lặp mỗi ~16ms, ~60 FPS hiển thị):
            │       ├─ cap.read() → frame
            │       ├─ system.put_frame(frame)           # Ghi frame mới nhất vào buffer
            │       ├─ system.get_display_frame(frame)  # Frame đã vẽ khung xanh/đỏ
            │       ├─ Resize theo kích thước canvas, chuyển RGB → PhotoImage (hoặc PPM)
            │       ├─ canvas.create_image(0,0, image=photo)
            │       ├─ system.get_count() → cập nhật lbl_count
            │       └─ Tính FPS (trung bình ~30 frame gần nhất), cập nhật lbl_fps mỗi 0.5s
            │
            ├─► update_timer (lặp mỗi 1s):
            │       remaining = end_time - now
            │       Nếu remaining <= 0 → cleanup()
            │       Cập nhật lbl_time "MM:SS"
            │
            └─► cleanup (đóng cửa sổ / STOP):
                    running = False
                    system.stop()   # Dừng thread _process_loop
                    cap.release()
                    destroy(); on_close_callback()
```

Luồng xử lý AI chạy **trong thread nền** do `OptimizedAttendanceSystem` quản lý (xem mục 4).

---

## 3. Chi tiết từng bước trong realtime_attendance.py

### 3.1 `__init__` và `create_ui`

- **geometry:** 1280x800.
- **Biến trạng thái:** `system`, `cap`, `running`, `fps_frame_times`, `fps_update_interval` (0.5s), `last_fps_update`.
- **create_ui:**
  - **Top bar (height 50):** `lbl_session` (trái), `lbl_fps` (trái, màu lime), `lbl_time` (phải).
  - **Canvas:** full giữa, nền đen, dùng để vẽ ảnh từ camera (đã qua engine).
  - **Bottom bar (height 70):** `lbl_count` ("Checked in: 0"), nút STOP gọi `cleanup`.
- **after(100, initialize_system):** Trì hoãn 100ms rồi gọi `initialize_system` để cửa sổ kịp hiển thị trước khi load nặng.

### 3.2 `initialize_system`

1. **Kiểm tra file encodings:** `os.path.exists(Config.ENCODINGS_PATH)`. Không có → báo lỗi, `cleanup()`.
2. **Load encodings:** `pickle.load` → `encodings = data.get('encodings', [])`, `ids = data.get('ids') or data.get('person_ids', [])`. Rỗng → báo lỗi, `cleanup()`.
3. **Database và phiên:**
   - `DatabaseManager(cooldown_minutes=0.05)` → cooldown 3 giây (0.05*60).
   - `db.create_session("RT_" + HHMM)` → INSERT vào `sessions`, lấy `session_id`.
   - `end_time = datetime.now() + timedelta(minutes=45)`.
4. **Khởi tạo engine:** `OptimizedAttendanceSystem(encodings, ids, db, session_id)` → `system`; gọi `system.start()` để chạy thread `_process_loop`.
5. **Camera:** `cv2.VideoCapture(0)`, set width=640, height=480, FPS=30, CAP_PROP_BUFFERSIZE=1 (giảm trễ).
6. **Bắt đầu vòng lặp:** `running = True`, gọi `update_loop()` và `update_timer()` (tự lên lịch lại bằng `after`).

### 3.3 `update_loop`

- **Điều kiện:** Chỉ chạy khi `self.running`.
- **Đọc frame:** `ret, frame = self.cap.read()`.
- **Nếu có frame:**
  - **Đẩy frame vào engine:** `self.system.put_frame(frame)` → ghi vào `SharedFrameBuffer` (double buffer).
  - **Lấy frame đã xử lý:** `display = self.system.get_display_frame(frame)` → engine đọc `latest_results`, vẽ khung xanh/đỏ lên bản sao frame, trả về frame đã vẽ.
  - **Hiển thị lên Canvas:** Resize `display` theo `canvas.winfo_width/height`, BGR→RGB, tạo `PhotoImage` (hoặc PPM nếu không có PIL), `canvas.create_image(0,0, anchor=NW, image=photo)`.
  - **Cập nhật số người điểm danh:** `count = self.system.get_count()` → `lbl_count.config(text="Checked in: {count}")`.
  - **Tính FPS:** Đo `elapsed = perf_counter() - t0` cho mỗi lần lặp; lưu vào `fps_frame_times` (tối đa 30 phần tử). Mỗi 0.5s: `fps = 1.0 / avg(elapsed)`, cập nhật `lbl_fps`.
- **Lên lịch lặp lại:** `self.after(16, self.update_loop)` (~60 FPS cho phần hiển thị).

### 3.4 `update_timer`

- Mỗi 1 giây: `remaining = end_time - datetime.now()`.
- Nếu `remaining <= 0` → gọi `cleanup()` (kết thúc phiên).
- Cập nhật `lbl_time` dạng "MM:SS".
- `self.after(1000, self.update_timer)`.

### 3.5 `cleanup`

- `running = False` → `update_loop` và `update_timer` sẽ thoát.
- `system.stop()` → dừng thread `_process_loop`.
- `cap.release()`.
- `destroy()`; gọi `on_close_callback()` (ví dụ quay lại menu chính).

---

## 4. Luồng trong core/realtime_engine.py (OptimizedAttendanceSystem)

### 4.1 Kiến trúc luồng

- **Luồng chính (Tkinter):** Gọi `put_frame(frame)` và `get_display_frame(frame)`, `get_count()`.
- **Luồng nền (daemon):** `_process_loop()` đọc frame từ buffer, gọi engine nhận diện + anti-spoof, ghi DB khi hợp lệ, cập nhật `latest_results` và `check_in_count`.

### 4.2 SharedFrameBuffer (double buffer)

- Hai buffer (A, B); một dùng cho ghi (write), một cho đọc (read).
- **write(frame):** Copy frame vào buffer write, sau đó đổi vai trò write/read (lock).
- **read():** Trả về buffer đang ở vai trò read (luôn là frame mới nhất đã ghi).
- Mục đích: Luồng UI chỉ ghi, luồng AI chỉ đọc; giảm lock, tránh queue chờ → giảm lag hiển thị.

### 4.3 _process_loop (thread nền)

1. **Đọc frame:** `frame = self.frame_buffer.read()`. Nếu `None` thì sleep 1ms, tiếp tục.
2. **Tập đã điểm danh:** `checked_in_set = { str(pid) for pid in self.checked_in }`.
3. **Nhận diện + anti-spoof:** `results = self.engine.process_frame(frame, already_checked_in=checked_in_set)` (xem mục 5).
4. **Xử lý từng kết quả:**
   - Bỏ qua nếu không có `person_id`.
   - Nếu `person_id` đã trong `self.checked_in` → bỏ qua (không ghi DB lại).
   - Nếu `antispoof['is_real']` = False → log reject, bỏ qua.
   - Cooldown: nếu cùng `person_id` vừa điểm danh trong `cooldown_seconds` (3s) → bỏ qua.
   - Gọi `self.db.mark_attendance(session_id, person_id_str, method='Realtime', confidence_score=..., liveness_score=..., liveness_details={...})`.
   - Nếu `mark_attendance` trả về success: thêm `person_id_str` vào `checked_in`, cập nhật `cooldown`, tăng `check_in_count` (có lock).
5. **Cập nhật kết quả hiển thị:** `self.latest_results = results` (trong `results_lock`).
6. `time.sleep(0.001)` rồi lặp lại.

### 4.4 put_frame / get_display_frame / get_count

- **put_frame(frame):** `frame_buffer.write(frame)`.
- **get_display_frame(frame):** Lấy `latest_results` (có lock), `checked_in_set` từ `self.checked_in`, gọi `renderer.render(frame, results, checked_in_ids=checked_in_set)` → trả về frame đã vẽ khung (xanh/đỏ).
- **get_count():** Trả về `check_in_count` (đọc có lock).

---

## 5. RealtimeRecognitionEngine – nhận diện và anti-spoof

### 5.1 process_frame(frame, already_checked_in)

- **Skip frame:** Mỗi `skip_frames` frame (ví dụ 2) mới xử lý một lần → dùng `last_results` cho frame còn lại (giảm tải CPU).
- **Resize:** `small_frame = cv2.resize(frame, (0,0), fx=0.4, fy=0.4)`; chuyển BGR → RGB cho thư viện face_recognition.
- **Phát hiện mặt:** `face_recognition.face_locations(rgb_small, model='hog')` (HOG trên CPU).
- **Mã hóa:** `face_recognition.face_encodings(rgb_small, face_locations, num_jitters=1)` → 128-D mỗi mặt.
- **Scale lại tọa độ:** face_locations tính trên ảnh 0.4x → nhân 2.5 để map về frame gốc.
- Với mỗi (box, face_encoding):
  - **So khớp:** `compare_faces(known_encodings, encoding, tolerance=0.45)`, `face_distance` → chọn index gần nhất; nếu match thì `person_id = known_ids[index]`, `confidence = 1 - distance`.
  - **Anti-spoof:**
    - Nếu `person_id in already_checked_in`: trả về kết quả giả (is_real=True, v.v.) để chỉ vẽ xanh, không chạy thuật toán.
    - Nếu có `person_id` và bật antispoof: cắt vùng mặt `frame[top:bottom, left:right]` → `antispoof.check(face_roi, str(person_id), frame)`.
  - Mỗi face trả về: `box`, `id`, `confidence`, `antispoof` (dict chứa is_real, score, blur, texture, blink_count, movement, reason).
- Lưu `last_results = results` và trả về.

### 5.2 Thuật toán chống giả mạo (RealtimeAntiSpoof.check)

**Đầu vào:** Ảnh vùng mặt BGR (`face_roi`), `face_id` (person_id dạng str), optional full frame.

**State theo từng người:** `person_states[face_id]`: ear_history (deque 10), blink_count, last_blink, head_positions (deque 5), movement_detected, frames_checked.

**Khi có MediaPipe:**

1. **Chớp mắt (EAR – Eye Aspect Ratio):**
   - MediaPipe Face Mesh → landmarks mắt trái/phải (LEFT_EYE, RIGHT_EYE).
   - Công thức EAR: với 6 điểm mỗi mắt, tính 2 khoảng cách dọc (v1, v2) và 1 khoảng cách ngang (h); `EAR = (v1 + v2) / (2*h)`.
   - Trung bình EAR hai mắt → đẩy vào `ear_history`.
   - **Đếm 1 lần chớp:** EAR hiện tại < 0.25 (mắt đóng) và trong 6 frame gần nhất có EAR > 0.27 (mắt mở); debounce 0.35s giữa hai lần chớp → tăng `blink_count`.

2. **Cử động đầu:**
   - Landmark mũi (index 1) → (x, y). Đẩy vào `head_positions`.
   - Khi có ≥ 3 vị trí: movement = max khoảng cách Euclid giữa hai vị trí liên tiếp. Nếu movement > 0.04 → `movement_detected = True`.

3. **Texture (FastTextureAnalyzer):**
   - Ảnh xám resize 64×64.
   - Sobel theo x, y (kernel 3) → gradient magnitude; `texture_score` từ std(grad_mag) chuẩn hóa (chia 45, clip 1).
   - Chia ảnh block 16×16, tính variance từng block → std của các variance → block_score. Kết quả: `0.65*texture_score + 0.35*block_score`. (Da thật nhiều biến thiên, ảnh/màn hình mịn hơn.)

4. **Blur:**
   - Laplacian(grayscale) → variance. `blur_score = min(lap_var/100, 1.0)` (ảnh rõ thì variance cao).

5. **Nghi màn hình (screen-like):**
   - Chuyển mặt sang HSV, kênh V.
   - `bright_ratio = tỉ lệ pixel V > 245`; `uniform_ratio = std(V)/mean(V)`.
   - `screen_like = (bright_ratio > 0.15) hoặc (uniform_ratio < 0.10)`. Nếu True thì ép `texture_score = min(texture_score, 0.38)`.

6. **Quyết định is_real:**
   - `has_action = (blink_count >= 1) hoặc movement_detected`.
   - `texture_ok = texture_score >= 0.42`, `blur_ok = blur_score >= 0.28`.
   - `is_real = has_action and texture_ok and blur_ok and (not screen_like)`.
   - Trả về dict: is_real, score, blur, texture, blink_count, movement, reason.

**Khi không có MediaPipe:** Gọi `_check_texture_only(face_bgr)`: chỉ texture + blur + screen_like; ngưỡng chặt hơn (texture ≥ 0.48, blur ≥ 0.35), không có blink/movement.

### 5.3 SmoothRenderer.render

- Với mỗi result: lấy box, person_id, antispoof.
- Nếu có person_id: làm mượt box bằng nội suy tuyến tính với `last_boxes[person_id]` (smooth_factor 0.6).
- Màu khung:
  - **Xanh (0,255,0):** `person_id` trong `checked_in_ids` hoặc `antispoof['is_real']`.
  - **Đỏ (0,0,255):** không nhận diện được (person_id None) hoặc không phải người thật (is_real False).
- Vẽ một hình chữ nhật lên frame: `cv2.rectangle(frame, (left, top), (right, bottom), color, 2)`.
- Không vẽ chữ hay thanh trạng thái phụ.

---

## 6. Database và file dữ liệu

### 6.1 File sử dụng

| Nguồn | File / Bảng | Dùng cho |
|-------|-------------|----------|
| **Config** | `Config.ENCODINGS_PATH` | Đường dẫn file pickle (thường `data/encodings/face_encodings.pkl`). |
| **Pickle** | `face_encodings.pkl` | `encodings` (list vector 128-D), `ids` (list person_id). Được tạo khi đăng ký (Register). |

### 6.2 DatabaseManager (đoạn liên quan)

- **create_session(subject):** INSERT vào `sessions (subject_name)`, trả về `session_id` (lastrowid).
- **can_checkin(student_id, session_id):** Kiểm tra lần điểm danh gần nhất (mọi phiên) có trong khoảng cooldown không; kiểm tra đã điểm danh trong phiên `session_id` chưa. Trả về (True/False, lý do).
- **mark_attendance(session_id, student_id, method, confidence_score, liveness_score, liveness_details):** Gọi `can_checkin` trước; nếu OK thì INSERT vào `attendance_logs` (session_id, student_id, checkin_time, verification_method, confidence_score, liveness_score, liveness_passed, liveness_details dạng JSON). Có xử lý schema cũ (thiếu cột liveness thì INSERT không có các cột đó).

---

## 7. Sơ đồ luồng dữ liệu (tóm tắt)

```
[Camera] → cap.read()
    ↓
[RealtimeAttendanceWindow] update_loop
    ↓
system.put_frame(frame)  →  SharedFrameBuffer.write(frame)
    ↓
[Thread nền] _process_loop:
    frame = frame_buffer.read()
    results = engine.process_frame(frame, already_checked_in)
        → face_locations (HOG) → face_encodings → compare_faces → person_id, confidence
        → mỗi face: antispoof.check(face_roi, person_id) → is_real, score, ...
    Với result is_real và chưa checked_in: db.mark_attendance(...); checked_in.add(person_id)
    latest_results = results
    ↓
[RealtimeAttendanceWindow] get_display_frame(frame)
    → renderer.render(frame, latest_results, checked_in_ids) → frame có khung xanh/đỏ
    ↓
Resize, RGB → PhotoImage → canvas.create_image()
get_count() → lbl_count
(FPS tính từ thời gian mỗi vòng update_loop)
```

---