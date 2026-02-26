## 3.5 Cử động đầu (Head Pose)

### 3.5.0 Khái niệm & mục tiêu
**Head Pose** mô tả tư thế đầu trong không gian 3D so với camera. Thông thường ta quan tâm 3 góc Euler:

- **Yaw (ψ)**: quay trái/phải (nhìn sang trái hoặc phải)
- **Pitch (θ)**: ngẩng/cúi (nhìn lên hoặc xuống)
- **Roll (φ)**: nghiêng đầu (tai gần vai)

**Mục tiêu của mục 3.5:**
1. **Ước lượng tư thế đầu** (yaw/pitch/roll) bằng phương pháp hình học 3D–2D (PnP).
2. **Phát hiện cử động đầu realtime** (có/không) bằng tín hiệu đơn giản, rẻ tính toán (theo dõi tọa độ mũi).

---

### 3.5.1 Phương pháp hình học: `solvePnP` (Perspective-n-Point)

#### (1) Bài toán PnP là gì?
Ta có:
- Một tập điểm **3D** trên mô hình khuôn mặt chuẩn:  \(\mathbf{X}_i = [X_i, Y_i, Z_i]^T\)
- Các điểm tương ứng **2D** trên ảnh: \(\mathbf{x}_i = [u_i, v_i]^T\)

Nhiệm vụ: tìm **R** (ma trận quay 3×3) và **t** (vector tịnh tiến 3×1) sao cho:

\[
s \begin{bmatrix} u \\ v \\ 1 \end{bmatrix}
=
\mathbf{K}\,[\mathbf{R}|\mathbf{t}]
\begin{bmatrix} X \\ Y \\ Z \\ 1 \end{bmatrix}
\]

Trong đó:
- \(\mathbf{K}\) là **ma trận nội tại camera** (camera intrinsics)
- \(s\) là hệ số tỉ lệ trong phép chiếu phối cảnh

**OpenCV `solvePnP()`** giải bài toán này để trả về:
- `rvec` (rotation vector, dạng Rodrigues)
- `tvec` (translation vector)

---

#### (2) Vì sao chỉ cần ~6 điểm là đủ?
Chỉ cần tối thiểu **4 điểm không đồng phẳng** để giải PnP, nhưng với khuôn mặt:
- dùng **6 điểm đặc trưng** (mũi, cằm, mắt, miệng) giúp ổn định hơn
- giảm nhiễu do landmark rung

**Bộ 6 điểm 2D thường dùng:**
1. Nose tip (đỉnh mũi)
2. Chin (cằm)
3. Left eye outer corner (đuôi mắt trái)
4. Right eye outer corner (đuôi mắt phải)
5. Left mouth corner (khóe miệng trái)
6. Right mouth corner (khóe miệng phải)

**Bộ 6 điểm 3D tương ứng** lấy từ mô hình mặt chuẩn (tọa độ mm/đơn vị tùy chọn).  
Lưu ý: mô hình 3D này chỉ cần **tương đối** (tỉ lệ), vì mục tiêu chính là góc quay.

---

#### (3) Camera intrinsics (K) và distCoeffs
**Chuyên sâu & thực tế:**
- Lý tưởng nhất: dùng **calibration** để có K và distortion chính xác.
- Thực tế (realtime, webcam): thường xấp xỉ:

\[
f \approx \text{image\_width}
\]
\[
c_x = \frac{w}{2},\quad c_y = \frac{h}{2}
\]

\[
\mathbf{K} =
\begin{bmatrix}
f & 0 & c_x \\
0 & f & c_y \\
0 & 0 & 1
\end{bmatrix}
\]

`distCoeffs` có thể set về 0 nếu không có calibration (chấp nhận sai số nhỏ).

---

#### (4) Từ rvec → yaw/pitch/roll
`rvec` phải đổi sang ma trận quay:
- `R = Rodrigues(rvec)`

Sau đó suy ra Euler angles. Có nhiều quy ước trục (XYZ, ZYX…), phải chọn thống nhất.
Thông dụng trong vision:
- yaw/pitch/roll lấy từ decomposition của R.

**Lưu ý quan trọng:**
- Góc có thể bị “nhảy” nếu gần điểm suy biến (gimbal lock).
- Nên lọc nhiễu (EMA / OneEuro / Kalman) để ổn định góc theo thời gian.

---

#### (5) Vì sao Dlib/MediaPipe hay dùng solvePnP?
Vì pipeline điển hình:
1. Detect face
2. Extract landmarks (2D)
3. Define face model (3D)
4. Run solvePnP → pose

Ưu điểm:
- dựa trên hình học → dễ giải thích
- chạy realtime tốt
- không cần training pose estimator riêng

---

### 3.5.2 Phát hiện cử động đầu realtime bằng theo dõi mũi (nhẹ – nhanh)

Trong realtime, nếu chỉ cần biết **có cử động hay không** (movement detection), ta có thể tránh solvePnP mỗi frame bằng cách:

#### (1) Tại sao dùng “tọa độ mũi”?
Mũi là điểm:
- gần trung tâm khuôn mặt
- ít bị che khuất hơn miệng
- thay đổi rõ khi đầu quay/dịch

Nếu đầu chuyển động (xoay hoặc tịnh tiến), tọa độ mũi 2D sẽ đổi đáng kể theo thời gian.

---

#### (2) Chuẩn hóa tọa độ để ngưỡng có ý nghĩa
Nên dùng tọa độ chuẩn hóa (0→1) theo kích thước ảnh:

\[
x = \frac{u}{w},\quad y = \frac{v}{h}
\]

Khi đó ngưỡng như `0.04` trở nên “độc lập độ phân giải”.

---

#### (3) Định nghĩa “movement” giữa 2 frame
Có 2 cách hay dùng:

**Cách A — L1 distance (nhanh, ổn):**
\[
movement = |x_t - x_{t-1}| + |y_t - y_{t-1}|
\]

**Cách B — Euclidean distance (đúng hình học hơn):**
\[
movement = \sqrt{(x_t - x_{t-1})^2 + (y_t - y_{t-1})^2}
\]

Khuyến nghị dùng **Euclidean** nếu không lo hiệu năng.

---

#### (4) Ngưỡng `0.04` nghĩa là gì?
Nếu tọa độ normalized:
- `0.04` ≈ dịch chuyển 4% chiều rộng/chiều cao ảnh
- ví dụ ảnh 640px: 0.04 * 640 ≈ 25.6px (khá rõ)

Vì landmark có nhiễu tự nhiên (jitter), nếu ngưỡng quá nhỏ sẽ báo false.

---

#### (5) Giảm nhiễu: lọc + cửa sổ thời gian
**Vấn đề:** 1 frame có thể bị rung → false positive.

Cách xử lý chuyên sâu:

**(a) Lọc mũi bằng EMA**
\[
p_t = \alpha \cdot p_t^{raw} + (1-\alpha)\cdot p_{t-1}
\]
với \(\alpha\) ~ 0.2–0.4.

**(b) Dùng cửa sổ N frame**
Thay vì so với frame ngay trước, so với frame cách N bước:
- N = 3–5 giúp bỏ rung nhỏ.

\[
movement = \|p_t - p_{t-N}\|
\]

**(c) Điều kiện “K frame liên tiếp”**
Chỉ xác nhận head movement nếu vượt ngưỡng liên tiếp K lần (K=2 hoặc 3).

---

### 3.5.3 Khi nào nên dùng solvePnP vs tracking mũi?

#### Dùng solvePnP khi:
- cần phân biệt **yaw/pitch/roll**
- cần định lượng góc (ví dụ yaw > 25°)
- cần robust khi đầu quay mạnh hoặc người tiến gần camera

#### Dùng tracking mũi khi:
- chỉ cần phát hiện “có di chuyển”
- yêu cầu realtime rất nhẹ (mobile / low-power)
- muốn tín hiệu nhanh, ít phụ thuộc camera calibration

---

### 3.5.4 Gợi ý thực tế triển khai (recommendations)

1. Nếu bài toán là **phát hiện gian lận / mất tập trung**:
   - dùng solvePnP để lấy yaw/pitch (chính)
   - dùng movement mũi để xác nhận “có chuyển động nhanh”

2. Nếu bài toán là **lọc frame ổn định** (trước khi nhận diện):
   - chỉ cần movement mũi + EMA + K liên tiếp

3. Ngưỡng `0.04` không “chuẩn tuyệt đối”.
   - Nên tune theo:
     - độ phân giải camera
     - độ rung landmark (thiết bị)
     - FPS (FPS cao → movement/frame nhỏ hơn)

---

### 3.5.5 Tóm tắt
- `solvePnP` dùng cặp điểm **2D landmark** và **3D face model** để suy ra **R,t** → chuyển thành **yaw/pitch/roll**.
- Trong realtime, để phát hiện nhanh **cử động đầu**, có thể theo dõi **tọa độ mũi**:
  - chuẩn hóa tọa độ
  - tính movement theo khoảng cách giữa các frame
  - nếu `movement > 0.04` (hoặc ngưỡng đã tune) → kết luận có cử động đầu
  - nên áp dụng lọc (EMA) + cửa sổ frame để giảm false positive
