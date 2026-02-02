# Logic nhận diện khuôn mặt và xác định giả mạo

Tài liệu mô tả luồng xử lý nhận diện khuôn mặt và chống điểm danh giả (anti-spoofing) trong chế độ Real-time.

---

## 1. Tổng quan luồng xử lý

```
Frame từ camera
    → Resize (0.4x) → face_recognition.face_locations (HOG)
    → face_recognition.face_encodings
    → So khớp với known_encodings (tolerance 0.45) → person_id, confidence
    → Với mỗi face: RealtimeAntiSpoof.check(face_roi, person_id) → is_real
    → Nếu person_id đã trong checked_in: skip antispoof, hiển thị xanh
    → Nếu is_real và chưa check-in: ghi DB, thêm vào checked_in
    → Render: khung xanh (thật/đã điểm danh) hoặc đỏ (fake/unknown)
```

- **File chính:** `core/realtime_engine.py`
- **Nhận diện:** thư viện `face_recognition` (dlib HOG + encoding), so khớp theo khoảng cách Euclidean.
- **Chống giả:** class `RealtimeAntiSpoof` (blink, cử động đầu, texture, blur, nghi màn hình).

---

## 2. Nhận diện khuôn mặt

### 2.1. Phát hiện vùng mặt

- Frame được resize theo tỉ lệ **0.4** để tăng tốc.
- Dùng `face_recognition.face_locations(rgb, model='hog')` (HOG, chạy CPU).
- Mỗi frame chỉ xử lý mỗi **3 frame một lần** (skip 2 frame) để giảm tải.

### 2.2. Mã hóa và so khớp

- `face_recognition.face_encodings(rgb, face_locations, num_jitters=1)` → 128-D vector cho mỗi mặt.
- So với danh sách `known_encodings` (từ file pickle đăng ký trước):
  - `face_recognition.compare_faces(known_encodings, encoding, tolerance=0.45)`
  - `face_recognition.face_distance(known_encodings, encoding)` → chọn mặt gần nhất.
- **person_id** = id trong DB tương ứng mặt gần nhất (nếu match).
- **confidence** = `1 - face_distance` (càng gần 1 càng giống).

### 2.3. Cache người đã điểm danh

- Set **checked_in** lưu `person_id` đã điểm danh trong phiên.
- Khi gọi `process_frame(frame, already_checked_in=checked_in_set)`:
  - Nếu `person_id in already_checked_in`: **không** chạy anti-spoof, coi là đã hợp lệ, chỉ hiển thị khung xanh.
- Trong `_process_loop`: nếu `person_id in checked_in` thì bỏ qua, không gọi `mark_attendance` nữa.

---

## 3. Xác định giả mạo (Anti-spoofing)

Mỗi vùng mặt (mỗi `person_id`) có **state riêng** (`person_states[face_id]`): lịch sử EAR, số lần chớp mắt, vị trí mũi, cử động đầu, v.v. Các bước dưới áp dụng **độc lập** cho từng mặt.

### 3.1. Khi có MediaPipe

#### 3.1.1. Chớp mắt (Blink)

- Dùng **MediaPipe Face Mesh** lấy landmarks mắt (LEFT_EYE, RIGHT_EYE).
- **EAR (Eye Aspect Ratio)** = `(v1 + v2) / (2 * h)` với khoảng cách dọc/ngang giữa các điểm mắt.
- Mỗi frame đẩy `avg_ear` (trung bình hai mắt) vào `ear_history`.
- **Điều kiện đếm 1 lần chớp:**
  - EAR hiện tại **< 0.25** (mắt đóng).
  - Trong vài frame trước có EAR **> 0.27** (mắt mở).
  - Debounce **0.35s** giữa hai lần chớp (tránh nhiễu).
- `blink_count` tăng khi thỏa điều kiện trên.

#### 3.1.2. Cử động đầu (Head movement)

- Lấy tọa độ mũi (landmark 1), đẩy vào `head_positions` (deque 5 phần tử).
- Tính **movement** = max khoảng cách giữa hai vị trí mũi liên tiếp (trong vài frame).
- Nếu **movement > 0.04** → `movement_detected = True` (coi là có cử động đầu rõ).

#### 3.1.3. Texture và độ rõ (Blur)

- **Texture:** `FastTextureAnalyzer.analyze(face_gray)`:
  - Resize mặt về 64×64, tính Sobel theo x, y → `grad_mag`.
  - `texture_score` từ `std(grad_mag)` và variance theo block 16×16 (real face nhiều biến thiên, ảnh/màn hình mịn hơn).
- **Blur:** `blur_score = min(Laplacian(gray).var() / 100, 1.0)` (ảnh càng rõ, variance càng cao).
- Ngưỡng: **texture_ok** = texture_score ≥ 0.42, **blur_ok** = blur_score ≥ 0.28.

#### 3.1.4. Nghi ảnh màn hình (Screen-like)

- Chuyển vùng mặt sang HSV, lấy kênh V (độ sáng).
- **bright_ratio** = tỉ lệ pixel có V > 245 (vùng rất sáng, dễ là reflection màn hình).
- **uniform_ratio** = std(V) / mean(V) (ảnh màn hình/ảnh phẳng thường rất đều).
- **screen_like** = (bright_ratio > 0.15) hoặc (uniform_ratio < 0.10).
- Nếu `screen_like`: ép texture_score xuống tối đa 0.38 (dễ rớt texture_ok).

#### 3.1.5. Quyết định “người thật”

- **has_action** = (`blink_count` ≥ 1) **hoặc** `movement_detected`.
- **is_real** = `has_action` **và** `texture_ok` **và** `blur_ok` **và** **không** `screen_like`.
- Thiếu action (không chớp, không cử động) → fake. Texture thấp hoặc nghi màn hình → fake.

### 3.2. Khi không có MediaPipe (texture-only)

- Không có blink/movement → chỉ dựa vào texture, blur và screen_like.
- **texture_ok** ≥ 0.48, **blur_ok** ≥ 0.35, **không** screen_like (cùng quy tắc bright/uniform như trên).
- **is_real** = texture_ok và blur_ok và không screen_like.
- Chế độ này dễ từ chối nhầm mặt thật trong điều kiện ánh sáng kém; nên cài MediaPipe để dùng blink + movement.

---

## 4. Ghi nhận điểm danh và hiển thị

- Chỉ khi **đã nhận diện được person_id**, **is_real = True** và **person_id chưa trong checked_in** thì mới gọi `db.mark_attendance(...)` (ghi DB) và thêm `person_id` vào `checked_in`.
- **Render (SmoothRenderer):**
  - **Khung xanh:** mặt đã điểm danh (trong checked_in) hoặc mặt thật (is_real) chưa/đã điểm danh.
  - **Khung đỏ:** không nhận diện được (unknown) hoặc không phải người thật (is_real = False).
- Chỉ vẽ khung màu, không hiển thị chữ hay trạng thái chi tiết trên ảnh.

---

## 5. Tham số chính (có thể chỉnh trong code)

| Tham số | Vị trí (gần đúng) | Ý nghĩa |
|--------|--------------------|--------|
| tolerance | RealtimeRecognitionEngine | Ngưỡng so khớp face (0.45). |
| EAR đóng | RealtimeAntiSpoof.check | EAR < 0.25 để coi là chớp mắt. |
| EAR mở | RealtimeAntiSpoof.check | max(recent) > 0.27 trước khi đếm blink. |
| movement | RealtimeAntiSpoof.check | movement > 0.04 để coi là cử động đầu. |
| texture_ok | RealtimeAntiSpoof.check | texture_score ≥ 0.42 (có MediaPipe). |
| blur_ok | RealtimeAntiSpoof.check | blur_score ≥ 0.28. |
| screen_like | RealtimeAntiSpoof.check | bright_ratio > 0.15 hoặc uniform_ratio < 0.10. |
| texture-only | _check_texture_only | texture ≥ 0.48, blur ≥ 0.35 khi không có MediaPipe. |

---

## 6. File liên quan

- **core/realtime_engine.py:** SharedFrameBuffer, FastTextureAnalyzer, FastFrequencyAnalyzer, RealtimeAntiSpoof, RealtimeRecognitionEngine, SmoothRenderer, OptimizedAttendanceSystem.
- **app/gui/realtime_attendance.py:** Giao diện điểm danh realtime, đọc frame từ camera, gọi system.put_frame / get_display_frame / get_count, hiển thị FPS.
- **database/db_manager.py:** mark_attendance (ghi session_id, student_id, confidence_score, liveness_score, liveness_details).

---

*Tài liệu tương ứng với logic trong `core/realtime_engine.py` (realtime mode) tại thời điểm viết.*
