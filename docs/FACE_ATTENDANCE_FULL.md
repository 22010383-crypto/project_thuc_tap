# Tài liệu tổng hợp: Điểm danh khuôn mặt Real-time

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Thư viện sử dụng](#2-thư-viện-sử-dụng)
3. [Thuật toán nền tảng](#3-thuật-toán-nền-tảng)
4. [Kiến trúc & luồng dữ liệu](#4-kiến-trúc--luồng-dữ-liệu)
5. [File và chức năng từng file](#5-file-và-chức-năng-từng-file)
6. [Nội dung chi tiết realtime_attendance.py](#6-nội-dung-chi-tiết-realtime_attendancepy)
7. [Engine realtime & anti-spoof](#7-engine-realtime--anti-spoof)
8. [Database & dữ liệu](#8-database--dữ-liệu)
9. [Tham số có thể chỉnh](#9-tham-số-có-thể-chỉnh)
10. [Euclidean Distance & Face Encoding](#10-euclidean-distance--face-encoding)

---

## 1. Tổng quan hệ thống

- **Mục tiêu:** Điểm danh bằng khuôn mặt real-time: camera → nhận diện → kiểm tra người thật (liveness/anti-spoof) → ghi DB.
- **Entry point giao diện:** `app/gui/realtime_attendance.py` (cửa sổ `RealtimeAttendanceWindow`).
- **Entry point chạy app:** `run_realtime.py` (mở Tkinter, tạo `RealtimeAttendanceWindow`).
- **Lõi xử lý:** `core/realtime_engine.py` (`OptimizedAttendanceSystem`, `RealtimeRecognitionEngine`, `RealtimeAntiSpoof`).

Luồng tóm tắt:

```
Camera → Main Thread (UI) → SharedFrameBuffer → Background Thread (AI)
  → Face locations (HOG) → Face encodings → So khớp (Euclidean)
  → Anti-spoof (blink/head + texture/blur) → mark_attendance → Render (xanh/đỏ) → Hiển thị
```

---

## 2. Thư viện sử dụng

| Thư viện | Vai trò |
|----------|---------|
| **face_recognition** | Wrapper trên dlib: `face_locations`, `face_encodings`, `face_distance`, `compare_faces`. Dùng HOG (hoặc CNN) để detect, ResNet để encode 128-D. |
| **dlib** | Lõi C++: HOG/CNN detection, ResNet encoding, shape_predictor 68 landmarks (dùng trong `liveness_detector.py`, không dùng trong realtime engine). |
| **OpenCV (cv2)** | Đọc camera (`VideoCapture`), resize, BGR↔RGB, grayscale, Sobel, Laplacian, DCT, HSV, vẽ khung. |
| **NumPy** | Ma trận, vector, khoảng cách, std, variance. |
| **MediaPipe** | Face Mesh 468 landmarks: tính EAR (chớp mắt), vị trí mũi (cử động đầu). Tùy chọn; nếu không cài thì realtime engine dùng chế độ texture-only. |
| **tkinter** | Cửa sổ, Canvas, Label, Button, `after()` cho vòng lặp. |
| **PIL (Pillow)** | `Image.fromarray`, `ImageTk.PhotoImage` để đưa frame lên Canvas; nếu không có thì fallback PPM. |
| **pickle** | Đọc file `face_encodings.pkl` (encodings + ids). |
| **sqlite3** | Lưu sessions, attendance_logs (qua `DatabaseManager`). |
| **logging** | Log lỗi, điểm danh, reject. |

---

## 3. Thuật toán nền tảng

### 3.1 Phát hiện khuôn mặt (Face Detection)

- **HOG (Histogram of Oriented Gradients):** Phân tích gradient cạnh trong các ô ảnh, dùng cho `face_recognition.face_locations(..., model='hog')`. Chạy CPU, nhanh.
- **CNN (tùy chọn):** Trong config có thể đổi `DETECTION_MODEL = "cnn"`; chính xác hơn nhưng cần GPU.
[Thuật tóa HOG](https://phamdinhkhanh.github.io/2019/11/22/HOG.html)
[Thuật tóa CNN](https://vietnix.vn/cnn-la-gi/?utm_source=ggads&utm_medium=pmax&utm_campaign={CampaignName}&p=&gad_source=1&gad_campaignid=23234186547&gbraid=0AAAAABwedNJdrh1woYLUqvxJCEJuAxtHp&gclid=Cj0KCQiA-YvMBhDtARIsAHZuUzJxgVc3ETQWU3_pTuE-eMP30KfmXibXGJX0WW_t4xuzGmTro2t19qEaAiMnEALw_wcB)
[Mô hình Facenet ](https://phamdinhkhanh.github.io/2020/03/12/faceNetAlgorithm.html)

### 3.2 Mã hóa khuôn mặt (Face Encoding)

- **ResNet (Deep Residual Network):** Mạng CNN đã train sẵn, biến ảnh mặt thành **vector 128 chiều** (face embedding). Hai ảnh cùng người → vector gần nhau; khác người → xa nhau.
- **face_recognition.face_encodings(rgb, face_locations, num_jitters=1):** Trả về list vector 128-D. `num_jitters` = số lần biến đổi ảnh (zoom/xoay) khi encode; tăng thì chính xác hơn nhưng chậm hơn.
[Mô hình Facenet ](https://viblo.asia/p/gioi-thieu-mang-resnet-vyDZOa7R5wj)

### 3.3 So khớp (Matching) – Euclidean Distance

- **Khoảng cách Euclid** giữa hai vector A, B (128 chiều):
  \[
  d(A,B) = \sqrt{\sum_{i=1}^{128} (a_i - b_i)^2}
  \]
- **face_recognition.face_distance(known_encodings, unknown_encoding)** trả về mảng khoảng cách tới từng khuôn mặt đã biết.
- **Ngưỡng (tolerance):** Trong realtime engine dùng `0.45`. Nếu `distance < tolerance` → cùng một người; **confidence** thường lấy `1 - distance`.

[Euclidean Distance chi tiết](Euclidean_Distance.md)

### 3.4 Chớp mắt (Blink) – EAR

- **EAR (Eye Aspect Ratio):** Tỉ lệ chiều cao/chiều ngang mắt.
  \[
  EAR = \frac{\|p_2-p_6\| + \|p_3-p_5\|}{2 \times \|p_1-p_4\|}
  \]
- Mắt mở: EAR cao (~0.25–0.3); mắt nhắm: EAR thấp (< 0.25). Trong realtime: EAR < 0.25 coi là đóng; trước đó có EAR > 0.27 coi là mở → đếm 1 lần chớp; debounce 0.35s.
[Eye Aspect Ratio](https://datahacker.rs/011-how-to-detect-eye-blinking-in-videos-using-dlib-and-opencv-in-python/)

### 3.5 Cử động đầu (Head Pose)

- **solvePnP:** Cho 6 điểm 2D trên ảnh (mũi, cằm, mắt, miệng) và 6 điểm 3D mô hình mặt chuẩn → ước lượng rotation (yaw, pitch, roll). Dlib/MediaPipe đều dùng cách này.
- Trong realtime: theo dõi **tọa độ mũi** (landmark 1); nếu thay đổi giữa các frame (movement > 0.04) → coi là có cử động đầu.
[Head Pose tài liệu chi tiết](HEAD_POSE.md)

### 3.6 Texture (phân biệt da thật / ảnh / màn hình)

- **Sobel:** Đạo hàm bậc nhất theo x, y → gradient magnitude. Da thật nhiều chi tiết (lỗ chân lông, nếp) → std(grad) cao; ảnh/màn hình mịn → std thấp.
- **Block variance:** Chia ảnh 64×64 thành block 16×16, tính variance từng block → std của các variance. Real face không đều → block_score cao.

### 3.7 Độ rõ ảnh (Blur)

- **Laplacian variance:** `cv2.Laplacian(gray, cv2.CV_64F).var()`. Ảnh rõ → biên sắc → variance cao; ảnh mờ → variance thấp.
- **blur_score** = min(lap_var / 100, 1.0).

### 3.8 Phát hiện màn hình (Screen-like)

- **HSV, kênh V (Value):** Tỉ lệ pixel rất sáng (V > 245) → bright_ratio. Độ đồng đều: std(V)/mean(V) → uniform_ratio.
- **screen_like** = (bright_ratio > 0.15) hoặc (uniform_ratio < 0.10) → nghi ảnh từ màn hình, ép texture_score xuống tối đa 0.38.

### 3.9 Tần số (DCT / FFT) – dùng ở module khác

- **DCT (Discrete Cosine Transform):** Nhanh hơn FFT trên ảnh; so sánh năng lượng tần số thấp (góc trên-trái) vs cao (góc dưới-phải). Ảnh in/ảnh số hóa thường ít tần số cao.
- **FFT:** Dùng trong `advanced_liveness_detector`, `silent_face_antispoof` (blur, glare, frequency, moiré).

### 3.10 LBP (Local Binary Pattern) – không dùng trong realtime

- So sánh 8 lân cận với pixel trung tâm → mã 8 bit; variance LBP cao = texture phong phú. Dùng trong `silent_face_antispoof`; tốn CPU nên realtime engine không dùng.

---

## 4. Kiến trúc & luồng dữ liệu

### 4.1 Hai luồng

- **Main Thread (UI):** Đọc camera, `put_frame(frame)`, `get_display_frame(frame)`, vẽ lên Canvas, cập nhật FPS và số người điểm danh, đếm ngược thời gian phiên. **Không** chạy nhận diện/anti-spoof.
- **Background Thread (AI):** Đọc frame từ `SharedFrameBuffer`, gọi `engine.process_frame()`, với mỗi face chạy anti-spoof, ghi DB khi hợp lệ, cập nhật `latest_results` và `check_in_count`.

### 4.2 SharedFrameBuffer (Double Buffering)

- Hai buffer A, B; một vai trò **write**, một **read**.
- **write(frame):** Copy frame vào buffer write, đổi vai trò write/read (có lock).
- **read():** Trả về buffer đang đọc (frame mới nhất).
- Mục đích: Luồng UI luôn ghi frame mới; luồng AI luôn đọc frame mới nhất; không dùng queue dài → giảm lag.

### 4.3 Sơ đồ luồng end-to-end

```
[Camera] cap.read()
    ↓
[RealtimeAttendanceWindow] update_loop (~60 FPS hiển thị)
    ↓
system.put_frame(frame)  →  SharedFrameBuffer.write(frame)
    ↓
[Thread nền] _process_loop:
    frame = frame_buffer.read()
    checked_in_set = { str(pid) for pid in self.checked_in }
    results = engine.process_frame(frame, already_checked_in=checked_in_set)
        → resize 0.4x → face_locations (HOG) → face_encodings
        → compare_faces / face_distance → person_id, confidence
        → mỗi face: antispoof.check(face_roi, person_id) → is_real, score, ...
    Với result: nếu đã trong checked_in → bỏ qua
                nếu is_real và qua cooldown → db.mark_attendance(...); checked_in.add(person_id)
    latest_results = results
    ↓
get_display_frame(frame) → renderer.render(frame, latest_results, checked_in_ids)
    → frame có khung xanh (đã điểm danh / real) hoặc đỏ (unknown / fake)
    ↓
Resize theo canvas, BGR→RGB → PhotoImage (hoặc PPM) → canvas.create_image()
get_count() → lbl_count; FPS từ thời gian mỗi vòng update_loop
```

---

## 5. File và chức năng từng file

### 5.1 Entry & GUI

| File | Chức năng |
|------|-----------|
| **run_realtime.py** | Thêm project root vào path, tạo `tk.Tk()` (ẩn), mở `RealtimeAttendanceWindow(root, on_close)`, chạy `mainloop()`. |
| **app/gui/realtime_attendance.py** | Cửa sổ 1280×800: top bar (session, FPS, timer), Canvas hiển thị camera, bottom bar (số đã điểm danh, nút STOP). Load encodings, tạo DB session, khởi tạo `OptimizedAttendanceSystem`, mở camera, chạy `update_loop` và `update_timer`, cleanup khi đóng/STOP. |

### 5.2 Config & Data

| File | Chức năng |
|------|-----------|
| **app/config.py** | `Config`: ENCODINGS_PATH, DB_PATH, RESIZE_SCALE, DETECTION_MODEL, MATCH_TOLERANCE, SHAPE_PREDICTOR_PATH, EYE_AR_THRESH, YAW_THRESH, v.v. `Config.ensure_dirs()` tạo thư mục data/encodings, database, models, logs, exports. |

### 5.3 Core (logic nhận diện & anti-spoof)

| File | Lớp / chức năng chính |
|------|------------------------|
| **core/face_detector.py** | `FaceDetector`: resize frame, BGR→RGB, `face_locations(..., model=Config.DETECTION_MODEL)`, scale tọa độ về frame gốc. Output: list (top, right, bottom, left). |
| **core/face_encoder.py** | `FaceEncoder`: load/save encodings từ pickle, encode(frame, face_locations), is_face_registered(encoding), add_face(frame, user_id), remove_encoding(user_id). |
| **core/face_matcher.py** | `FaceMatcher(encoder)`: find_match(unknown_encoding) → (user_id, confidence) dùng face_distance + MATCH_TOLERANCE. |
| **core/liveness_detector.py** | `ActionLivenessDetector`: dlib 68 landmarks, EAR, solvePnP → yaw. Cung cấp {valid, ear, yaw}; không dùng trực tiếp trong realtime window. |
| **core/advanced_liveness_detector.py** | `LivenessDetector`: MediaPipe Face Mesh, active (EAR, head pose, EAR variance) + passive (blur, glare, FFT). Trả về is_real, score. |
| **core/silent_face_antispoof.py** | `SilentFaceAntiSpoof`: passive (LBP, FFT, blur, color, moiré). `HybridLivenessDetector`: kết hợp passive + active. |
| **core/fast_antispoof.py** | `FastAntiSpoof`: blur + DCT + color, cache theo face_id. `SmartFrameProcessor`, `DebouncedUIUpdater`, `OptimizedAntiSpoofDetector`. |
| **core/realtime_engine.py** | **Dùng trực tiếp bởi realtime_attendance:** SharedFrameBuffer, FastTextureAnalyzer, FastFrequencyAnalyzer, RealtimeAntiSpoof, RealtimeRecognitionEngine, SmoothRenderer, **OptimizedAttendanceSystem**. |

### 5.4 Database

| File | Chức năng |
|------|-----------|
| **database/db_manager.py** | `DatabaseManager(cooldown_minutes)`: init_db (students, sessions, attendance_logs với confidence_score, liveness_score, liveness_passed, liveness_details). create_session(subject), can_checkin(student_id, session_id), mark_attendance(session_id, student_id, method, confidence_score, liveness_score, liveness_details). |

---

## 6. Nội dung chi tiết realtime_attendance.py

### 6.1 Imports và khởi tạo cửa sổ

- **tkinter**, **cv2**, **pickle**, **time**, **os**, **datetime**, **timedelta**
- **Config** (ENCODINGS_PATH), **DatabaseManager**, **OptimizedAttendanceSystem**
- **PIL (Image, ImageTk)** tùy chọn; không có thì dùng PPM cho PhotoImage.

### 6.2 RealtimeAttendanceWindow(parent, on_close)

- **geometry:** 1280×800.
- **Biến:** system, cap, running, fps_frame_times, fps_update_interval (0.5s), last_fps_update, end_time (now + 45 phút).
- **create_ui():** Top bar (lbl_session, lbl_fps, lbl_time), Canvas (nền đen), Bottom bar (lbl_count "Checked in: 0", nút STOP).
- **after(100, initialize_system):** Trì hoãn 100ms rồi gọi initialize_system.
- **protocol("WM_DELETE_WINDOW", cleanup):** Đóng cửa sổ → cleanup.

### 6.3 initialize_system()

1. Kiểm tra `Config.ENCODINGS_PATH` tồn tại; không có → messagebox lỗi, cleanup.
2. `pickle.load` → encodings, ids (hoặc person_ids); rỗng → lỗi, cleanup.
3. `DatabaseManager(cooldown_minutes=0.05)` → cooldown 3 giây.
4. `db.create_session("RT_" + HHMM)` → session_id; end_time = now + 45 phút.
5. `OptimizedAttendanceSystem(encodings, ids, db, session_id)` → system; `system.start()` (bật thread _process_loop).
6. `cv2.VideoCapture(0)`, set 640×480, 30 FPS, CAP_PROP_BUFFERSIZE=1.
7. running = True; gọi update_loop(); update_timer().

### 6.4 update_loop()

- Chỉ chạy khi `self.running`.
- `ret, frame = self.cap.read()`.
- Nếu có frame: `system.put_frame(frame)`, `display = system.get_display_frame(frame)`.
- Resize display theo canvas (winfo_width/height), BGR→RGB; tạo PhotoImage (PIL hoặc PPM), `canvas.create_image(0, 0, anchor=NW, image=photo)`.
- `lbl_count.config(text="Checked in: " + str(system.get_count()))`.
- Đo elapsed mỗi vòng; lưu vào fps_frame_times (tối đa 30); mỗi 0.5s cập nhật lbl_fps = 1.0 / avg(elapsed).
- `self.after(16, self.update_loop)` (~60 FPS hiển thị).

### 6.5 update_timer()

- Mỗi 1s: remaining = end_time - now; nếu remaining <= 0 → cleanup(); ngược lại cập nhật lbl_time "MM:SS". `self.after(1000, self.update_timer)`.

### 6.6 cleanup()

- running = False; system.stop(); cap.release(); self.destroy(); on_close_callback().

---

## 7. Engine realtime & anti-spoof

### 7.1 OptimizedAttendanceSystem

- **__init__(known_encodings, known_ids, db_manager, session_id):** Tạo RealtimeRecognitionEngine(use_antispoof=True), SmoothRenderer, lưu db, session_id, checked_in (set), cooldown (dict), cooldown_seconds=3.0, frame_buffer (SharedFrameBuffer), results_lock, count_lock.
- **start():** running=True, tạo Thread(target=_process_loop, daemon=True), start().
- **stop():** running=False, join thread timeout 1.0.
- **_process_loop:** Đọc frame từ buffer; checked_in_set = {str(pid) for pid in checked_in}; results = engine.process_frame(frame, already_checked_in=checked_in_set). Với mỗi result: bỏ qua nếu không person_id hoặc đã trong checked_in; nếu không antispoof['is_real'] → log, bỏ qua; kiểm tra cooldown; gọi db.mark_attendance(..., confidence_score, liveness_score, liveness_details); nếu success thì checked_in.add(person_id_str), cập nhật cooldown, tăng check_in_count. Ghi latest_results (có lock); sleep(0.001).
- **put_frame(frame):** frame_buffer.write(frame).
- **get_display_frame(frame):** Lấy latest_results (lock), checked_in_set, renderer.render(frame, results, checked_in_ids).
- **get_count():** Trả về check_in_count (lock).

### 7.2 RealtimeRecognitionEngine

- **process_frame(frame, already_checked_in=None):** Skip mỗi skip_frames frame (dùng last_results). Resize frame (0.4x), BGR→RGB; face_locations (HOG); face_encodings (num_jitters=1). Scale box ×2.5 về frame gốc. Với mỗi (box, encoding): compare_faces + face_distance → person_id, confidence. Nếu person_id trong already_checked_in → antispoof giả (is_real=True) không chạy check. Ngược lại nếu use_antispoof và person_id: cắt face_roi → antispoof.check(face_roi, str(person_id), frame). Mỗi face trả về {box, id, confidence, antispoof}. Lưu last_results; return results.

### 7.3 RealtimeAntiSpoof.check(face_bgr, face_id, full_frame)

- **State theo face_id:** ear_history (deque 10), blink_count, last_blink, head_positions (deque 5), movement_detected, frames_checked.
- **MediaPipe:** Face Mesh → landmarks. EAR (LEFT_EYE, RIGHT_EYE) → avg_ear; đếm blink (EAR < 0.25 và max(recent) > 0.27, debounce 0.35s). Mũi (landmark 1) → head_positions; movement = max khoảng cách liên tiếp; > 0.04 → movement_detected.
- **Texture:** FastTextureAnalyzer.analyze(face_gray) (Sobel + block variance). **Blur:** Laplacian(gray).var() → blur_score = min(var/100, 1.0).
- **Screen-like:** HSV V; bright_ratio (V>245), uniform_ratio = std(V)/mean(V); screen_like = bright_ratio>0.15 or uniform_ratio<0.10; nếu screen_like thì texture_score = min(texture_score, 0.38).
- **has_action** = blink_count >= 1 or movement_detected. **texture_ok** = texture_score >= 0.42. **blur_ok** = blur_score >= 0.28.
- **is_real** = has_action and texture_ok and blur_ok and (not screen_like).
- Trả về dict: is_real, score, blur, texture, blink_count, movement, reason.
- **Fallback không MediaPipe:** _check_texture_only: chỉ texture + blur + screen_like; texture_ok >= 0.48, blur_ok >= 0.35; is_real = (not screen_like) and texture_ok and blur_ok.

### 7.4 SmoothRenderer

- **smooth_box(person_id, new_box):** Nếu chưa có last_boxes[person_id] thì gán;否则 EMA: smooth_box = old*0.6 + new*0.4 (từng tọa độ).
- **render(frame, results, checked_in_ids):** Với mỗi result: box (có smooth nếu có person_id); màu xanh nếu person_id trong checked_in_ids hoặc antispoof['is_real']; đỏ nếu không. cv2.rectangle(frame, (left, top), (right, bottom), color, 2).

---

## 8. Database & dữ liệu

### 8.1 File pickle (encodings)

- **Đường dẫn:** Config.ENCODINGS_PATH (thường `data/encodings/face_encodings.pkl`).
- **Nội dung:** Dict `{"encodings": [array 128-D, ...], "ids": [person_id, ...]}` (hoặc key "person_ids"). Được tạo/cập nhật khi đăng ký khuôn mặt (FaceEncoder.add_face, save_database).

### 8.2 SQLite (attendance.db)

- **students:** student_id (PK), name, class_name, created_at.
- **sessions:** session_id (AUTO), subject_name, start_time, end_time.
- **attendance_logs:** log_id (AUTO), session_id, student_id, checkin_time, verification_method, confidence_score, liveness_score, liveness_passed, liveness_details (JSON). UNIQUE(session_id, student_id). Index: student_id, session_id, checkin_time.

### 8.3 create_session(subject)

- INSERT INTO sessions (subject_name); return lastrowid.

### 8.4 can_checkin(student_id, session_id)

- Lấy lần điểm danh gần nhất của student_id; nếu trong cooldown_delta → (False, "Vui lòng đợi..."). Nếu session_id cho trước: kiểm tra đã có (session_id, student_id) trong attendance_logs → (False, "Đã điểm danh trong phiên này rồi"). Otherwise (True, "OK").

### 8.5 mark_attendance(session_id, student_id, method, confidence_score, liveness_score, liveness_details)

- Gọi can_checkin; nếu không OK trả về (False, reason).
- PRAGMA table_info(attendance_logs): nếu có cột confidence_score thì dùng schema mới (INSERT với confidence_score, liveness_score, liveness_passed, liveness_details JSON);否则 schema cũ (chỉ session_id, student_id, verification_method). Commit; return (True, "Điểm danh thành công").

---

## 9. Tham số có thể chỉnh

| Tham số | Vị trí | Ý nghĩa |
|--------|--------|---------|
| tolerance | RealtimeRecognitionEngine | Ngưỡng so khớp face (0.45). |
| skip_frames | RealtimeRecognitionEngine | Cứ mỗi skip_frames frame mới chạy nhận diện (mặc định 2). |
| resize (0.4) | process_frame | Tỉ lệ resize frame trước HOG (0.4 = 40%). |
| EAR đóng | RealtimeAntiSpoof | EAR < 0.25 coi là mắt nhắm. |
| EAR mở | RealtimeAntiSpoof | max(recent) > 0.27 để đếm blink. |
| movement | RealtimeAntiSpoof | Khoảng cách mũi > 0.04 → cử động đầu. |
| texture_ok | RealtimeAntiSpoof | texture_score >= 0.42 (có MediaPipe). |
| blur_ok | RealtimeAntiSpoof | blur_score >= 0.28. |
| screen_like | RealtimeAntiSpoof | bright_ratio > 0.15 hoặc uniform_ratio < 0.10. |
| texture-only | _check_texture_only | texture >= 0.48, blur >= 0.35 khi không MediaPipe. |
| cooldown_seconds | OptimizedAttendanceSystem | 3.0 giây giữa hai lần điểm danh cùng người. |
| smooth_factor | SmoothRenderer | 0.6 (EMA box). |
| RESIZE_SCALE, MATCH_TOLERANCE, DETECTION_MODEL | app/config.py | Scale detect, tolerance, hog/cnn. |
| cooldown_minutes | DatabaseManager(0.05) | Realtime dùng 0.05 → 3 phút (thực tế engine còn cooldown_seconds 3s trong phiên). |

---

## 10. Euclidean Distance & Face Encoding

### 10.1 Euclidean Distance

- **Công thức:** \(d(A,B) = \sqrt{\sum_{i=1}^{n}(a_i - b_i)^2}\). Trong face: n=128.
- **Ý nghĩa:** Khoảng cách càng nhỏ → hai khuôn mặt càng giống nhau. So sánh encoding đầu vào với từng encoding trong DB; nếu min(distance) < threshold → cùng người; confidence có thể lấy 1 - distance.

### 10.2 Face Encoding (FaceEncoder workflow)

- **Detection:** face_recognition.face_locations (HOG/CNN) → (top, right, bottom, left).
- **Encoding:** face_recognition.face_encodings(rgb, face_locations, num_jitters=1) → vector 128-D. BGR→RGB; np.ascontiguousarray để tránh lỗi khi gọi C++.
- **Matching:** face_distance(known_encodings, encoding) → distances; argmin → best_match_index; nếu distance < MATCH_TOLERANCE → user_id = known_ids[best_match_index].
- **Chống trùng khi đăng ký:** is_face_registered(encoding): nếu min(distance) < MATCH_TOLERANCE → báo trùng, không add.

---