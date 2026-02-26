# Tài liệu thư mục `core` – Logic & chức năng từng file

Thư mục `core` chứa toàn bộ logic nhận diện khuôn mặt, mã hóa, so khớp, phát hiện liveness và anti-spoof. Tài liệu này mô tả từng file: mục đích, lớp chính, luồng xử lý và phụ thuộc.

---

## Tổng quan kiến trúc

```
core/
├── __init__.py                 # Package marker (rỗng)
├── face_detector.py            # Phát hiện vị trí khuôn mặt (HOG)
├── face_encoder.py             # Mã hóa face → vector 128D, CRUD encoding
├── face_matcher.py             # So khớp vector với DB (Euclidean)
├── liveness_detector.py        # Active liveness (dlib: EAR, solvePnP)
├── advanced_liveness_detector.py  # Active + Passive (MediaPipe, FFT, blur, glare)
├── silent_face_antispoof.py    # Passive only: LBP, FFT, blur, moiré, color
├── fast_antispoof.py           # Anti-spoof nhanh: DCT, blur, color, cache
└── realtime_engine.py          # Engine realtime: texture, blink, DB, UI
```

**Luồng dùng chính:**  
`FaceDetector` → `FaceEncoder.encode` / `FaceMatcher.find_match` cho nhận diện.  
Liveness/anti-spoof: `liveness_detector` / `advanced_liveness_detector` (active+passive), `silent_face_antispoof` (passive), `fast_antispoof` (tối ưu FPS), **realtime_engine** (hệ thống điểm danh realtime thực tế).

---

## 1. `face_detector.py`

**Mục đích:** Tìm vị trí (bounding box) các khuôn mặt trong frame.

**Lớp chính:** `FaceDetector`

**Logic:**

1. Resize frame theo `Config.RESIZE_SCALE` để giảm tải CPU.
2. Chuyển BGR → RGB (face_recognition dùng RGB).
3. Gọi `face_recognition.face_locations(..., model=Config.DETECTION_MODEL)` — mặc định **HOG** (không cần GPU).
4. Scale lại tọa độ từ ảnh nhỏ về kích thước frame gốc (nhân với `1/scale`).

**Output:** List `[(top, right, bottom, left), ...]` theo tọa độ frame gốc.

**Phụ thuộc:** `cv2`, `face_recognition`, `app.config.Config`.

---

## 2. `face_encoder.py`

**Mục đích:** Quản lý **face encoding** (vector 128 chiều từ ResNet/dlib): load/save file, encode từ ảnh, thêm/xóa người dùng, kiểm tra trùng.

**Lớp chính:** `FaceEncoder`

**Logic chính:**

- **`load_database()`:** Đọc file pickle tại `Config.ENCODINGS_PATH`, nạp `encodings` và `ids` vào RAM.
- **`encode(frame, face_locations)`:** Cắt vùng mặt theo `face_locations`, chuyển BGR→RGB (contiguous), gọi `face_recognition.face_encodings(..., num_jitters=1)` → list vector 128D.
- **`is_face_registered(encoding)`:** So khoảng cách với mọi encoding trong DB; nếu `min_distance < Config.MATCH_TOLERANCE` → coi là trùng, trả về `(True, matched_id)`.
- **`add_face(frame, user_id)`:** Detect 1 mặt, encode; nếu trùng (qua `is_face_registered`) thì báo lỗi; không trùng thì append vào list và `save_database()`.
- **`remove_encoding(user_id)`:** Loại encoding/ids theo `user_id`, ghi lại file.
- **`save_database()`:** Ghi `{"encodings", "ids"}` ra file pickle.

**Output:** Encodings trong RAM + file; các method trả về bool/string thông báo.

**Phụ thuộc:** `face_recognition`, `pickle`, `os`, `cv2`, `numpy`, `app.config.Config`.

---

## 3. `face_matcher.py`

**Mục đích:** So khớp **một** encoding lạ với toàn bộ encoding trong DB (từ encoder).

**Lớp chính:** `FaceMatcher(encoder)`

**Logic:**

1. Nếu `encoder.known_encodings` rỗng → trả về `(None, 1.0)`.
2. `face_recognition.face_distance(known_encodings, unknown_encoding)` → khoảng cách Euclidean tới từng người.
3. Lấy index có khoảng cách nhỏ nhất; nếu `best_distance < Config.MATCH_TOLERANCE` → trả về `(user_id, confidence)` với `confidence = 1.0 - best_distance`.

**Output:** `(user_id | None, confidence | best_distance)`.

**Phụ thuộc:** `face_recognition`, `numpy`, `app.config.Config`.

---

## 4. `liveness_detector.py`

**Mục đích:** **Active liveness** dựa trên dlib: EAR (chớp mắt) và head pose (góc quay đầu). Không tự quyết “real/fake”, chỉ cung cấp số liệu cho lớp trên.

**Lớp chính:** `ActionLivenessDetector`

**Logic:**

- **`get_landmarks(frame, face_rect)`:** Dùng `dlib.shape_predictor` (68 điểm) trên vùng mặt → shape.
- **`calculate_ear(shape)`:** EAR = (|p2-p6| + |p3-p5|) / (2*|p1-p4|) cho mắt trái/phải, trung bình. EAR thấp = mắt nhắm.
- **`calculate_pose(frame, shape)`:** 6 điểm ảnh (mũi, cằm, mắt, miệng) + model 3D → `cv2.solvePnP` → rotation → **yaw** (góc quay trái/phải), clip [-90, 90].
- **`analyze_action(frame, face_rect)`:** Gọi `get_landmarks` → `calculate_ear` + `calculate_pose` → dict `{valid, ear, yaw}`.

Camera matrix được cache theo kích thước frame.

**Output:** Dict `{valid, ear, yaw}` để logic bên ngoài quyết định blink/head movement.

**Phụ thuộc:** `cv2`, `numpy`, `dlib`, `scipy.spatial.distance`, `app.config.Config` (đường dẫn shape predictor).

---

## 5. `advanced_liveness_detector.py`

**Mục đích:** Liveness **đầy đủ**: Active (MediaPipe EAR + head pose) + Passive (blur, glare, FFT). Trả về kết luận `is_real` và score.

**Lớp chính:** `LivenessDetector`

**Logic:**

- **Active (60%):**
  - MediaPipe Face Mesh → landmarks.
  - EAR từ 6 điểm mắt trái/phải; đếm blink khi EAR < ngưỡng liên tục `BLINK_CONSEC_FRAMES`.
  - Head pose: solvePnP từ 6 điểm 3D → yaw, pitch, roll; “head_moved” nếu |yaw| hoặc |pitch| > ngưỡng.
  - EAR variance (30 frame) để phát hiện ảnh tĩnh (static).
- **Passive (40%):**
  - **Blur:** Laplacian variance trên vùng mặt; dưới ngưỡng → trừ điểm.
  - **Glare:** Kênh V (HSV), tỉ lệ pixel sáng > 200 → glare score.
  - **Frequency:** FFT, so sánh vùng tần số cao vs thấp; ảnh in thường ít tần số cao.
- **Tổng hợp:** `final_score = active*0.6 + passive*0.4`; `is_real = (final_score >= 0.5)`.

**Output:** Dict `{is_real, score, action, reason, details: {active, passive}}`.

**Phụ thuộc:** `cv2`, `numpy`, `mediapipe`, `logging`.

---

## 6. `silent_face_antispoof.py`

**Mục đích:** **Passive** anti-spoof không cần hành động người dùng: ảnh in, màn hình, replay. Dùng LBP, FFT, blur, màu, moiré.

**Lớp chính:** `SilentFaceAntiSpoof`, `HybridLivenessDetector`

**SilentFaceAntiSpoof – Logic:**

- **Blur:** Laplacian variance (giống advanced).
- **Texture (LBP):** Local Binary Pattern 8 lân cận, tính variance LBP; mặt thật nhiều texture, ảnh in/màn hình thường “phẳng”.
- **Frequency:** FFT, tỉ lệ high/low frequency.
- **Color:** Độ lệch chuẩn HSV (H, S, V); màu tự nhiên thường đa dạng hơn.
- **Moiré:** FFT, vùng ring 20–50 px từ tâm; nhiều peak bất thường → nghi chụp màn hình.
- Điểm tổng có trọng số (blur, texture, frequency, color, moiré); `is_real = (final_score >= 0.5)`.

**HybridLivenessDetector:** Kết hợp passive (SilentFaceAntiSpoof) + active (ear, yaw từ bên ngoài qua `active_data`). Có thể chỉ dùng passive (`require_action=False`).

**Output:** Dict `is_real`, `score`, `confidence`, `reason`, `details` (từng hạng mục).

**Phụ thuộc:** `cv2`, `numpy`, `logging`. LBP tính trên từng pixel → nặng CPU.

---

## 7. `fast_antispoof.py`

**Mục đích:** Anti-spoof **tối ưu FPS**: bỏ LBP, dùng blur + DCT + color, cache theo `face_id`, dùng cho pipeline realtime.

**Lớp chính:** `FastAntiSpoof`, `SmartFrameProcessor`, `DebouncedUIUpdater`, `OptimizedAntiSpoofDetector`

**FastAntiSpoof – Logic:**

- Resize mặt về 64x64.
- **Blur:** Laplacian variance, chuẩn hóa theo `BLUR_THRESH`.
- **Frequency:** DCT (nhanh hơn FFT), so năng lượng low (góc trên-trái) vs high (góc dưới-phải).
- **Color:** std HSV (vectorized).
- Điểm tổng weighted; `is_real = (final_score >= 0.45)`.
- Cache kết quả theo `face_id` với `CACHE_DURATION` (mặc định 2s).

**SmartFrameProcessor:** Giới hạn số frame xử lý theo `target_fps` (ví dụ 25 FPS) → `should_process_frame()`.

**DebouncedUIUpdater:** Giới hạn tần suất cập nhật UI theo key và `min_interval`.

**OptimizedAntiSpoofDetector:** Kết hợp FastAntiSpoof + SmartFrameProcessor + DebouncedUIUpdater; có `process_frame()`, `get_stats()`, `get_current_fps()`.

**Output:** Dict `is_real`, `score`, `confidence`, `reason`, `cached`, (optional) `processing_time`.

**Phụ thuộc:** `cv2`, `numpy`, `time`, `logging`, `collections.deque`.

---

## 8. `realtime_engine.py`

**Mục đích:** **Engine điểm danh realtime** end-to-end: capture → nhận diện mặt → anti-spoof (texture + blink/head) → ghi DB → render. Dùng double buffer, một luồng xử lý, bỏ qua frame, cache cho người đã điểm danh.

**Lớp chính:**

- **SharedFrameBuffer:** Double buffer có lock; luồng capture `write()`, luồng xử lý `read()`.
- **FastTextureAnalyzer:** Sobel gradient magnitude + variance theo block 16x16 → texture score (mặt thật cao, màn hình/ảnh thấp).
- **FastFrequencyAnalyzer:** DCT, tỉ lệ high/low → score tần số.
- **RealtimeAntiSpoof:**  
  - Nếu có MediaPipe: EAR (blink) + vị trí mũi (head movement) + texture + blur + “screen_like” (sáng chói / độ đều V trong HSV).  
  - Điều kiện “real”: có ít nhất 1 blink **hoặc** movement **và** texture_ok **và** blur_ok **và** không screen_like.  
  - State theo `face_id` (ear_history, blink_count, head_positions).  
  - Không có MediaPipe: fallback `_check_texture_only()` (ngưỡng chặt hơn).
- **RealtimeRecognitionEngine:**  
  - Resize frame (fx=fy=0.4), HOG detect, face_encodings, so khớp với `known_encodings` (tolerance 0.45).  
  - Với mỗi face: nếu `person_id` nằm trong `already_checked_in` → **không** chạy anti-spoof, coi như real (chỉ hiển thị).  
  - Còn lại: gọi `RealtimeAntiSpoof.check(face_roi, person_id)`.  
  - Skip frame theo `skip_frames` (mặc định 2).
- **SmoothRenderer:** Làm mượt bounding box theo person_id (interpolation), vẽ khung xanh (đã điểm danh hoặc real) / đỏ (chưa nhận diện hoặc fake).
- **OptimizedAttendanceSystem:**  
  - Khởi tạo engine + renderer + DB + session_id.  
  - Luồng nền `_process_loop`: đọc frame từ buffer → `engine.process_frame(frame, already_checked_in=checked_in_set)` → với mỗi kết quả: nếu đã trong `checked_in` thì bỏ qua; nếu `antispoof['is_real']` và qua cooldown thì `db.mark_attendance(...)` và thêm vào `checked_in`.  
  - `put_frame()` để đẩy frame; `get_display_frame()` để lấy frame đã vẽ box; `get_count()` số lần điểm danh trong phiên.

**Output:** Danh sách `{box, id, confidence, antispoof}`; DB được ghi khi pass anti-spoof; frame hiển thị có box màu và số lượng check-in.

**Phụ thuộc:** `cv2`, `numpy`, `face_recognition`, `threading`, `collections.deque`, `time`, `logging`; tùy chọn `mediapipe`.

---

## Bảng so sánh nhanh

| File | Chức năng chính | Active Liveness | Passive Liveness | Dùng trong |
|------|------------------|-----------------|------------------|------------|
| face_detector | Detect vị trí mặt | - | - | Mọi pipeline |
| face_encoder | Encode, CRUD DB encoding | - | - | Đăng ký + nhận diện |
| face_matcher | So khớp 1-N | - | - | Nhận diện |
| liveness_detector | EAR + pose (dlib) | ✓ | - | Logic active cũ |
| advanced_liveness_detector | MediaPipe + blur/glare/FFT | ✓ | ✓ | Pipeline đầy đủ |
| silent_face_antispoof | LBP, FFT, blur, moiré, color | (qua Hybrid) | ✓ | Anti-spoof chi tiết |
| fast_antispoof | Blur, DCT, color, cache | - | ✓ | Realtime nhẹ |
| realtime_engine | End-to-end điểm danh | ✓ (blink/head) | ✓ (texture/blur/screen) | **Cửa sổ điểm danh realtime** |

---

## Gợi ý sử dụng

- **Đăng ký mặt / quản lý danh sách:** `FaceDetector` + `FaceEncoder` (và có thể `FaceMatcher` để kiểm tra trùng).
- **Điểm danh realtime (app chính):** Dùng `OptimizedAttendanceSystem` trong `realtime_engine.py`; encoding/ids lấy từ `FaceEncoder`, DB từ `database.db_manager`.
- **Chỉ cần anti-spoof nhanh, không blink:** `FastAntiSpoof` hoặc `OptimizedAntiSpoofDetector`.
- **Cần passive mạnh (LBP, moiré):** `SilentFaceAntiSpoof` hoặc `HybridLivenessDetector` (đổi lại tốn CPU hơn).

Tài liệu chi tiết hơn về luồng điểm danh realtime và nhận diện/anti-spoof: `docs/REALTIME_ATTENDANCE_FLOW.md`, `docs/RECOGNITION_AND_ANTISPOOF.md`.
