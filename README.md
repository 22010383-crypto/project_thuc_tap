# KẾ HOẠCH TRIỂN KHAI & BÁO CÁO TIẾN ĐỘ DỰ ÁN
**Đề tài:** Hệ thống Điểm danh bằng Nhận diện Khuôn mặt (Face Recognition Attendance System)
---

### 1. Xác định tính năng của dụ án & Tìm hiểu về công nghệ sử dụng và setup cấu trúc thư mục cho dự án

### 1.1. Chức năng
1. Đầu vào là màn hình

2. Đăng ký mới sinh viên (id, họ tên, lớp)

3. Hình ảnh đầu vào (xử lý ảnh)

4. Quản lý sinh viên (danh sách sinh viên, có tìm kiếm, chỉnh sửa thông tin và xoá)

5. Nhận diện danh tính tự động (bấm vào có màn hình camera)

6. Nhận diện, xác định điểm danh bằng hình ảnh hay face

7. Xuất dữ liệu excel thống tin điểm danh

### 1.2. Xử lý
1.  **Kiến trúc Đa luồng (Multi-threading):** - Tách biệt luồng đọc Camera (IO-bound) và luồng xử lý AI (CPU-bound).
    - Sử dụng mô hình **Producer-Consumer** với `Queue` để giao diện không bao giờ bị đơ (Not Responding).
2.  **Giao diện Modal (Modal UI Logic):**
    - Cơ chế quản lý cửa sổ độc quyền: Chỉ cho phép một tác vụ (Đăng ký/Điểm danh/Quản lý) chạy tại một thời điểm để tối ưu tài nguyên phần cứng.
3.  **Bảo toàn dữ liệu (Data Integrity):**
    - Cơ chế **Rollback**: Tự động xóa dữ liệu rác nếu quá trình đăng ký khuôn mặt thất bại.
    - Cơ chế **Duplicate Check**: So sánh Vector đặc trưng để ngăn chặn đăng ký trùng lặp (1 người 2 ID).

### 1.3 Công nghệ sử dụng
- **Ngôn ngữ:** Python.
- **Core AI:** OpenCV, Face_recognition
- **Giao diện (GUI):** Tkinter
- **Cơ sở dữ liệu:** SQLite.
- **Thư viện khác:** dlib, numpy, pandas.

