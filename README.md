# KẾ HOẠCH TRIỂN KHAI & BÁO CÁO TIẾN ĐỘ DỰ ÁN
**Đề tài:** Hệ thống Điểm danh bằng Nhận diện Khuôn mặt (Face Recognition Attendance System)
---

### 1. Xác định tính năng của dụ án & Tìm hiểu về công nghệ sử dụng và setup cấu trúc thư mục cho dự án

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

### 1.3 Công nghệ sử dụng
- **Ngôn ngữ:** Python.
- **Core AI:** OpenCV, Face_recognition
- **Giao diện (GUI):** Tkinter
- **Cơ sở dữ liệu:** SQLite.
- **Thư viện khác:** dlib, numpy, pandas.

### 1.4 Database
1.  **Thiết kế schame:** 

Cơ sở dữ liệu của hệ thống điểm danh sinh viên được thiết kế nhằm phục vụ việc:
- Quản lý thông tin sinh viên
- Quản lý các phiên học (buổi điểm danh)
- Lưu trữ và truy xuất kết quả điểm danh

Hệ thống đảm bảo mỗi sinh viên chỉ được điểm danh **một lần trong mỗi phiên học**, đồng thời hỗ trợ cả hình thức điểm danh **tự động** và **thủ công**.

---

## 2. Danh sách các bảng

Cơ sở dữ liệu bao gồm ba bảng chính:

- `students` – Lưu thông tin sinh viên
- `sessions` – Lưu thông tin phiên học
- `attendance_logs` – Lưu nhật ký điểm danh

---

## 2.1 Bảng `students` – Sinh viên

### Mô tả
Bảng `students` dùng để lưu trữ thông tin cơ bản của sinh viên trong hệ thống.

### Cấu trúc bảng

| Tên cột | Kiểu dữ liệu | Mô tả |
|------|-------------|------|
| `student_id` | TEXT (PK) | Mã sinh viên |
| `name` | TEXT | Họ và tên sinh viên |
| `class_name` | TEXT | Lớp học |
| `created_at` | TIMESTAMP | Thời gian tạo bản ghi |

### Câu lệnh tạo bảng

```sql
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    class_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 2.2 Bảng `sessions` – Phiên học / Buổi điểm danh

### Mô tả
Bảng `sessions` dùng để quản lý từng buổi học hoặc buổi điểm danh trong hệ thống.  
Mỗi phiên tương ứng với một lần mở camera để thực hiện nhận diện khuôn mặt sinh viên.

### Cấu trúc bảng

| Tên cột | Kiểu dữ liệu | Mô tả |
|--------|-------------|------|
| `session_id` | INTEGER (PK, AUTOINCREMENT) | Mã phiên học |
| `subject_name` | TEXT | Tên môn học |
| `room_name` | TEXT | Phòng học |
| `start_time` | TIMESTAMP | Thời gian bắt đầu mở camera |
| `end_time` | TIMESTAMP | Thời gian kết thúc phiên |

### Câu lệnh tạo bảng

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_name TEXT NOT NULL,
    room_name TEXT,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP
);
```

## 2.3 Bảng `attendance_logs` – Điểm danh

### Mô tả
Bảng `attendance_logs` dùng để lưu trữ kết quả điểm danh của sinh viên trong từng phiên học.  
Mỗi sinh viên chỉ được điểm danh một lần duy nhất trong một phiên học.

### Cấu trúc bảng

| Tên cột | Kiểu dữ liệu | Mô tả |
|--------|-------------|------|
| `log_id` | INTEGER (PK, AUTOINCREMENT) | Mã bản ghi điểm danh |
| `session_id` | INTEGER (FK) | Mã phiên học |
| `student_id` | TEXT (FK) | Mã sinh viên |
| `checkin_time` | TIMESTAMP | Thời gian điểm danh |
| `verification_method` | TEXT | Phương thức xác thực (`Auto`, `Manual`) |
| `confidence_score` | REAL | Điểm tin cậy do AI trả về |

### Câu lệnh tạo bảng

```sql
CREATE TABLE IF NOT EXISTS attendance_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    student_id TEXT NOT NULL,
    checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verification_method TEXT DEFAULT 'Auto',
    confidence_score REAL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    UNIQUE(session_id, student_id)
);
```

### Hình ảnh ERD

![alt text](image.png)
[Xem ERD trên Mermaid Live](https://mermaid.live/view#pako:eNp9U21PgzAQ_ivkPuMCzrHJt8VVs-jQCCbGkJDa3kZ1tKYtRp377xZmpiLab9fnnrvn3jbAFEeIAfVM0JWmVS4999LsZkaSLPU2O7t5GbnNPGNrjtIWgntX5x1M0go7X2xNjSk6wHxB0my6uPKYRmqRF9Tu0G0uP9OTNJ1fJj_Sz5OMnJFrz6AxQsleBaa-f0Bmix4lWqnqTyHGUm0LK_pRlPwbthc5zTKSzKbJCSkuLs96ta7Vqquzp4zT87-b_AP7alyJ7FHIruKG-4xaLAWjtgleoS0V__K4JtMLjym5FC4-w8Iwpbtl7Uf__n5woDa_yoy9HEpqcuiM6h93l9FSIVsO-LDSgkO8pGuDPlSoK9rY0PYvB1uiKwoaHsclrde2oW0d74nKOzdFiK2uHVOrelXu49RP3O3S5xLvXdzoUJ-oWlqIw7ANAfEGXiAeRsHgeDgejsIgiqIgCo98eIV4NBoE0eHRJJyMw2E4jrY-vLU5g8FkPPIBubBKL3ZH097O9gMAOfZ9)


# Tuần 2

# 1. Mục tiêu công việc 

Dựa trên kế hoạch tổng thể, các đầu mục công việc đã thực hiện trong tuần này bao gồm:

- Thiết lập môi trường phát triển (Environment Setup)
- Xây dựng cấu trúc thư mục dự án (Project Structure / Base Code)
- Thiết kế và khởi tạo Cơ sở dữ liệu (Database Setup)
- Xây dựng các hàm tiền xử lý dữ liệu hình ảnh (Data Preprocessing)

---

# 2. Chi tiết thực hiện

## 2.1. Thiết lập môi trường phát triển

Đã tiến hành cài đặt các thư viện cần thiết dựa trên công nghệ gợi ý (OpenCV, dlib / face_recognition).

- **Ngôn ngữ**: Python 3.x  
- **Quản lý thư viện**: pip  

### File `requirements.txt`

```plaintext
opencv-python
numpy
face_recognition
pandas
openpyxl
cmake
dlib
```

---

## 2.2. Cấu trúc dự án (Project Structure)

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

## 2.3. Thiết kế Cơ sở dữ liệu (Database Design)

### Bảng `users`

| Tên cột | Kiểu dữ liệu | Mô tả |
|-------|------------|------|
| `id` | INTEGER (PK, AUTOINCREMENT) | ID nội bộ |
| `user_id` | TEXT (UNIQUE) | Mã sinh viên |
| `name` | TEXT | Họ tên |
| `face_encoding` | BLOB | Vector khuôn mặt |
| `created_at` | TIMESTAMP | Thời gian tạo |

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE,
    name TEXT,
    face_encoding BLOB,
    created_at TIMESTAMP
);
```

## Bảng `sessions` – Phiên học / Buổi điểm danh
 
### Cấu trúc bảng

| Tên cột | Kiểu dữ liệu | Mô tả |
|--------|-------------|------|
| `session_id` | INTEGER (PK, AUTOINCREMENT) | Mã phiên học |
| `subject_name` | TEXT | Tên môn học |
| `room_name` | TEXT | Phòng học |
| `start_time` | TIMESTAMP | Thời gian bắt đầu mở camera |
| `end_time` | TIMESTAMP | Thời gian kết thúc phiên |

### Câu lệnh tạo bảng

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_name TEXT NOT NULL,
    room_name TEXT,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP
);
```

## Bảng `attendance_logs` – Điểm danh

### Cấu trúc bảng

| Tên cột | Kiểu dữ liệu | Mô tả |
|--------|-------------|------|
| `log_id` | INTEGER (PK, AUTOINCREMENT) | Mã bản ghi điểm danh |
| `session_id` | INTEGER (FK) | Mã phiên học |
| `student_id` | TEXT (FK) | Mã sinh viên |
| `checkin_time` | TIMESTAMP | Thời gian điểm danh |
| `verification_method` | TEXT | Phương thức xác thực (`Auto`, `Manual`) |
| `confidence_score` | REAL | Điểm tin cậy do AI trả về |

### Câu lệnh tạo bảng

```sql
CREATE TABLE IF NOT EXISTS attendance_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    student_id TEXT NOT NULL,
    checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verification_method TEXT DEFAULT 'Auto',
    confidence_score REAL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    UNIQUE(session_id, student_id)
);
```

---

# 3. Tiền xử lý dữ liệu (Data Preprocessing)

Đọc và chuẩn hóa ảnh:
Sử dụng cv2.imread để đọc ảnh đầu vào.
Chuyển đổi không gian màu từ BGR (OpenCV mặc định) sang RGB (yêu cầu của thư viện face_recognition).

Mã hóa khuôn mặt (Encoding):
Sử dụng thư viện face_recognition (dựa trên dlib) để trích xuất 128 đặc trưng (128-d embeddings) của khuôn mặt.
Xử lý ngoại lệ: Bỏ qua các ảnh không tìm thấy khuôn mặt hoặc có nhiều hơn 1 khuôn mặt.

# 4. Kết quả & Khó khăn

## Kết quả
- [x] Hoàn thành khung dự án
- [x] Tạo CSDL attendance.db
- [x] Mã hóa khuôn mặt thành công

# Tuần 3
---

## 1. TỔNG QUAN HỆ THỐNG (EXECUTIVE SUMMARY)
Hệ thống được thiết kế để giải quyết bài toán xác thực danh tính (Identity Verification) trong môi trường thời gian thực (Real-time). Khác với các hệ thống nhận diện khuôn mặt truyền thống, giải pháp này tích hợp một pipeline bảo mật đa lớp (Multi-layer Security Pipeline) để chống lại các hành vi giả mạo (Spoofing attacks) như sử dụng ảnh in, video quay lại hoặc màn hình điện thoại.

### Các module chính:
1.  **Face Recognition Engine:** Nhận diện và định danh người dùng.
2.  **Passive Liveness Detection (Chống giả mạo thụ động):** Phân tích tín hiệu hình ảnh (độ mờ, tần số, màu sắc) để phát hiện vật thể giả mạo mà không cần người dùng tương tác.
3.  **Active Liveness Detection (Chống giả mạo chủ động):** Yêu cầu và phân tích hành vi người dùng (chớp mắt, quay đầu).
4.  **Optimized Core:** Bộ điều phối hiệu năng giúp hệ thống chạy mượt trên CPU thông thường.

---

## 2. KIẾN TRÚC CÔNG NGHỆ (TECHNOLOGY STACK)

| Lớp công nghệ | Thư viện / Công cụ | Chi tiết kỹ thuật |
| :--- | :--- | :--- |
| **Ngôn ngữ** | Python 3.8+ | Sử dụng vì hệ sinh thái thư viện khoa học dữ liệu mạnh mẽ. |
| **Xử lý ma trận** | **NumPy** | Xử lý mảng đa chiều, tính toán vector hóa (Vectorization) thay cho vòng lặp để tối ưu tốc độ. |
| **Computer Vision** | **OpenCV (`cv2`)** | Xử lý ảnh cơ bản, chuyển đổi không gian màu (BGR $\leftrightarrow$ RGB/HSV/Gray), tính toán Laplace, DCT. |
| **Face Engine** | **Dlib (C++)** | Core engine chạy ngầm. Sử dụng thuật toán HOG cho detection và ResNet cho encoding. |
| **Wrapper** | **Face_recognition** | API cấp cao của Dlib, giúp đơn giản hóa việc gọi các hàm C++. |
| **Algorithm** | **SciPy** | Tính toán khoảng cách Euclidean trong không gian n-chiều. |
| **Serialization** | **Pickle** | Lưu trữ cơ sở dữ liệu vector khuôn mặt dưới dạng binary. |

---

## 3. PHÂN TÍCH CHI TIẾT THUẬT TOÁN (ALGORITHMIC ANALYSIS)

### 3.1. Module Nhận Diện Khuôn Mặt (Face Recognition)

#### A. Phát hiện khuôn mặt (Face Detection) - `FaceDetector`
* **Phương pháp:** Histogram of Oriented Gradients (HOG).
* **Nguyên lý:**
    1.  Ảnh đầu vào được chuyển sang Grayscale.
    2.  Tính toán gradient (hướng và cường độ thay đổi độ sáng) cho từng pixel.
    3.  Chia ảnh thành các ô nhỏ (cells), xây dựng biểu đồ hướng (histogram of directions) cho từng ô.
    4.  Sử dụng cửa sổ trượt (sliding window) và bộ phân loại SVM (Support Vector Machine) để tìm khu vực có đặc trưng HOG giống khuôn mặt.
* **Tối ưu hóa:**
    * **Scale Pyramid:** Hệ thống resize ảnh đầu vào nhỏ lại (theo `Config.RESIZE_SCALE`) để giảm số lượng phép tính trên pixel.
    * **Coordinate Mapping:** Tọa độ $(x, y)$ tìm được trên ảnh nhỏ được nhân với nghịch đảo tỉ lệ ($1/scale$) để map về ảnh gốc.

#### B. Mã hóa đặc trưng (Feature Encoding) - `FaceEncoder`
* **Mô hình:** Deep Residual Network (ResNet-34).
* **Input:** Vùng ảnh khuôn mặt (Face chip) đã được căn chỉnh (aligned).
* **Process:** Ảnh đi qua 34 lớp tích chập (Convolutional layers).
* **Output:** Một vector 128 chiều (128-D Embedding).
* **Tính chất:** Vector này bất biến với thay đổi nhỏ về ánh sáng và góc độ.
* **Xử lý bộ nhớ:** Sử dụng `np.ascontiguousarray` để đảm bảo vùng nhớ chứa ảnh là liên tục, giúp thư viện C++ (Dlib) truy xuất dữ liệu trực tiếp mà không cần copy, giảm độ trễ (latency).

#### C. So khớp (Matching) - `FaceMatcher`
* **Phương pháp:** Khoảng cách Euclidean (L2 Norm).
* **Công thức:**
    $$d(\vec{u}, \vec{v}) = \sqrt{\sum_{i=1}^{128} (u_i - v_i)^2}$$
    Trong đó $\vec{u}$ là vector khuôn mặt từ camera, $\vec{v}$ là vector trong database.
* **Ngưỡng (Thresholding):**
    * Nếu $\min(d) < \text{Config.MATCH\_TOLERANCE}$ $\rightarrow$ **Match**.
    * Độ tin cậy (Confidence) ước lượng: $C = 1.0 - \min(d)$.

---

### 3.2. Module Chống Giả Mạo Thụ Động (Passive Liveness - `FastAntiSpoof`)

Đây là lớp bảo vệ đầu tiên, sử dụng các kỹ thuật xử lý ảnh cổ điển (Heuristic-based) để loại bỏ các tấn công bằng ảnh in/màn hình.

#### A. Phân tích độ mờ (Blur Detection)
* **Giả thuyết:** Ảnh chụp lại (recapture) từ màn hình hoặc giấy in thường mất chi tiết cạnh (edges) so với khuôn mặt thật.
* **Thuật toán:** Phương sai của toán tử Laplace (Variance of Laplacian).
    $$\text{Score} = \text{Var}(\nabla^2 \text{Image})$$
* **Thực thi:** Sử dụng kernel tích chập $3 \times 3$. Nếu phương sai thấp dưới ngưỡng `BLUR_THRESH`, ảnh bị coi là quá mượt (có thể là màn hình) hoặc mất nét $\rightarrow$ **FAKE**.

#### B. Phân tích miền tần số (Frequency Analysis)
* **Giả thuyết:** Da người thật có kết cấu chi tiết ngẫu nhiên. Ảnh màn hình thường chứa nhiễu lưới (Moiré pattern) hoặc bị khử nhiễu quá mức (low-pass filtering).
* **Thuật toán:** Biến đổi Cosine rời rạc (Discrete Cosine Transform - DCT).
* **Quy trình:**
    1.  Chuyển ảnh xám sang miền tần số bằng `cv2.dct`.
    2.  Tính năng lượng tần số thấp (góc trên trái ma trận DCT) và tần số cao (góc dưới phải).
    3.  Tỷ lệ $R = \frac{\text{High Freq Energy}}{\text{Low Freq Energy}}$.
* **Quyết định:** Nếu $R < \text{FREQ\_THRESH}$, ảnh thiếu chi tiết tần số cao $\rightarrow$ **FAKE**.

#### C. Phân tích dải màu (Color Diversity)
* **Giả thuyết:** Cảm biến camera khi chụp lại màn hình thường làm mất dải động (Dynamic Range) của màu sắc.
* **Thuật toán:**
    1.  Chuyển ảnh sang không gian màu HSV (Hue, Saturation, Value).
    2.  Tính độ lệch chuẩn (Standard Deviation - $\sigma$) cho từng kênh màu.
    3.  Tính trung bình cộng: $\bar{\sigma} = \text{mean}(\sigma_H, \sigma_S, \sigma_V)$.
* **Quyết định:** Nếu $\bar{\sigma}$ thấp $\rightarrow$ Màu sắc đơn điệu, bệt màu $\rightarrow$ **FAKE**.

---

### 3.3. Module Chống Giả Mạo Chủ Động (Active Liveness - `ActionLivenessDetector`)

Yêu cầu sự hợp tác của người dùng để xác nhận hành vi sinh học.

#### A. Trích xuất điểm đặc trưng (Facial Landmarks)
* **Model:** Ensemble of Regression Trees (ERT) - pre-trained trên bộ dữ liệu iBUG 300-W.
* **Output:** 68 tọa độ $(x, y)$ đại diện cho viền hàm, lông mày, mũi, mắt và môi.

#### B. Phát hiện chớp mắt (Eye Blink Detection)
* **Chỉ số:** Tỷ lệ khung hình mắt (Eye Aspect Ratio - EAR).
* **Công thức:**
    $$EAR = \frac{||p_2 - p_6|| + ||p_3 - p_5||}{2 \times ||p_1 - p_4||}$$
    *(Với $p_1 \dots p_6$ là các điểm landmark quanh mắt theo chiều kim đồng hồ)*.
* **Logic:**
    * Mắt mở: $EAR \approx 0.25 - 0.30$.
    * Mắt nhắm: $EAR < 0.20$ (Tử số tiến về 0).
    * Hệ thống phát hiện sự chuyển đổi trạng thái: Mở $\rightarrow$ Nhắm $\rightarrow$ Mở là 1 lần chớp mắt.

#### C. Ước lượng tư thế đầu (Head Pose Estimation)
* **Bài toán:** Perspective-n-Point (PnP).
* **Mục tiêu:** Tìm hướng nhìn của khuôn mặt (Góc Yaw, Pitch, Roll).
* **Dữ liệu đầu vào:**
    1.  **2D Image Points:** Các điểm landmark mũi, cằm, mắt, miệng trên ảnh.
    2.  **3D Model Points:** Tọa độ 3D chuẩn của khuôn mặt người (Generic Face Model).
    3.  **Camera Matrix:** Ma trận nội tham (Focal length, Optical center).
* **Giải thuật:** Sử dụng `cv2.solvePnP` (phương pháp Iterative) để tìm vector tịnh tiến ($t$) và vector quay ($r$).
* **Tính góc:** Chuyển đổi vector quay ($r$) thành ma trận quay ($R$) bằng công thức Rodrigues, sau đó phân rã thành góc Euler. Góc **Yaw** được sử dụng để xác định hành động quay trái/phải.

---

## 4. TỐI ƯU HIỆU NĂNG (OPTIMIZATION STRATEGY)

Để đảm bảo hệ thống hoạt động Real-time (25+ FPS) trên CPU, các kỹ thuật sau đã được áp dụng trong `OptimizedAntiSpoofDetector`:

1.  **Adaptive Frame Skipping (Bỏ khung hình thông minh):**
    * Class `SmartFrameProcessor` theo dõi thời gian xử lý thực tế.
    * Nếu CPU đang quá tải (thời gian xử lý > khoảng cách giữa các frame camera), hệ thống sẽ chủ động bỏ qua các frame tiếp theo để tránh lag tích lũy (latency buildup).

2.  **Result Caching (Bộ nhớ đệm kết quả):**
    * Class `FastAntiSpoof` duy trì một `dict` lưu kết quả `(is_real, timestamp)` của từng `face_id`.
    * Nếu khuôn mặt đó vừa được kiểm tra (trong vòng 2 giây - `CACHE_DURATION`), hệ thống trả về kết quả cũ ngay lập tức mà không cần chạy lại thuật toán DCT/Laplacian tốn kém.

3.  **Debounced UI Updates:**
    * Class `DebouncedUIUpdater` ngăn chặn việc cập nhật giao diện quá nhanh (ví dụ: cập nhật text mỗi 1ms). Chỉ cho phép vẽ lại UI sau mỗi khoảng thời gian `min_interval` (ví dụ: 100ms) để tiết kiệm tài nguyên render.

4.  **Ma trận Camera Caching:**
    * Trong `ActionLivenessDetector`, ma trận nội tham máy ảnh (`camera_matrix`) chỉ được tính một lần duy nhất cho mỗi độ phân giải ảnh và được lưu lại (`_camera_matrix_cache`), tránh tính toán lại dư thừa trong mỗi vòng lặp.

---
