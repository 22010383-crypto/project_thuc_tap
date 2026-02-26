# Euclidean Distance (Khoảng cách Euclid)

## 1. Khái niệm
**Euclidean Distance** (Khoảng cách Euclid) là một thuật toán toán học dùng để đo **khoảng cách hình học** giữa hai điểm (hay hai vector) trong không gian nhiều chiều.  
Trong lĩnh vực **nhận dạng khuôn mặt**, mỗi khuôn mặt được biểu diễn dưới dạng một **vector đặc trưng**, và Euclidean Distance được sử dụng để đo **mức độ giống nhau** giữa hai khuôn mặt đó.

Khoảng cách càng **nhỏ** → hai khuôn mặt càng **giống nhau**  
Khoảng cách càng **lớn** → hai khuôn mặt càng **khác nhau**

---

## 2. Công thức toán học
Cho hai vector:
- \( \mathbf{A} = (a_1, a_2, ..., a_n) \)
- \( \mathbf{B} = (b_1, b_2, ..., b_n) \)

Khoảng cách Euclid giữa hai vector được tính theo công thức:

\[
d(\mathbf{A}, \mathbf{B}) = \sqrt{\sum_{i=1}^{n} (a_i - b_i)^2}
\]

---

## 3. Ứng dụng trong nhận dạng khuôn mặt
Trong hệ thống nhận dạng khuôn mặt:
- Mỗi khuôn mặt được mã hóa thành một **vector embedding** (thường có 128, 256 hoặc 512 chiều)
- Euclidean Distance được dùng để:
  - So sánh khuôn mặt đầu vào với khuôn mặt trong cơ sở dữ liệu
  - Quyết định hai khuôn mặt có thuộc **cùng một người** hay không

### Ngưỡng (Threshold)
Một giá trị **ngưỡng** được đặt ra:
- Nếu `distance < threshold` → Hai khuôn mặt được xem là **giống nhau**
- Nếu `distance ≥ threshold` → Hai khuôn mặt được xem là **khác nhau**

Ngưỡng này phụ thuộc vào mô hình trích xuất đặc trưng và dữ liệu huấn luyện.

---

## 4. Ví dụ minh họa
Giả sử có hai vector khuôn mặt:

\[
\mathbf{A} = (1, 2, 3)
\]
\[
\mathbf{B} = (2, 4, 6)
\]

Khoảng cách Euclid:

\[
d = \sqrt{(1-2)^2 + (2-4)^2 + (3-6)^2} = \sqrt{1 + 4 + 9} = \sqrt{14}
\]

---

## 5. Ưu điểm và hạn chế

### Ưu điểm
- Dễ hiểu, dễ cài đặt
- Tính toán nhanh
- Hiệu quả khi dữ liệu đã được chuẩn hóa

### Hạn chế
- Nhạy cảm với nhiễu (noise)
- Hiệu suất giảm khi số chiều lớn nếu dữ liệu không được chuẩn hóa
- Không xét đến mối quan hệ phi tuyến giữa các đặc trưng

---

## 6. Kết luận
Euclidean Distance là một phương pháp đơn giản nhưng rất hiệu quả để đo độ tương đồng giữa các vector khuôn mặt. Khi kết hợp với các mô hình trích xuất đặc trưng mạnh (như FaceNet, ArcFace), thuật toán này đóng vai trò quan trọng trong các hệ thống nhận dạng khuôn mặt hiện đại.
