## 1. YÊU CẦU PHẦN CỨNG (HARDWARE)
* **CPU:** Intel Core i5 (Gen 8 trở lên) hoặc AMD Ryzen 5.
* **RAM:** 8 GB trở lên (Để xử lý đa luồng mượt mà).
* **Ổ cứng:** SSD (Giúp tốc độ load Database và ghi file Excel nhanh hơn).
---

## 2. YÊU CẦU PHẦN MỀM (SOFTWARE)
### 2.1 Hệ điều hành (OS)
* **Windows:** Windows 10 hoặc Windows 11 (64-bit).
* **Linux:** Ubuntu 20.04/22.04 LTS 
* **macOS:** macOS Catalina trở lên 

### 2.2 Môi trường Lập trình
* **Python Version:** **3.8.x** đến **3.10.x**.
    * *Khuyên dùng:* **Python 3.10.x**.
---

## 3. CÁC THƯ VIỆN PYTHON (DEPENDENCIES)

Các thư viện chính được liệt kê trong `requirements.txt`. Phiên bản dưới đây là phiên bản ổn định nhất đã được kiểm thử:

| Thư viện | Phiên bản | Mục đích |
| :--- | :--- | :--- |
| **opencv-python** | `4.5+` | Xử lý hình ảnh, đọc camera, vẽ giao diện lên ảnh. |
| **dlib** | `19.24+` | Core thuật toán Machine Learning (HOG, Landmarks). |
| **face_recognition** | `1.3.0` | Wrapper giúp nhận diện khuôn mặt dễ dàng hơn. |
| **numpy** | `1.21+` | Xử lý mảng dữ liệu ảnh và tính toán vector. |
| **Pillow** | `9.0+` | Hỗ trợ hiển thị ảnh trên giao diện Tkinter. |
| **pandas** | `1.3+` | Xử lý dữ liệu bảng để xuất báo cáo. |
| **openpyxl** | `3.0+` | Driver để ghi file Excel (.xlsx). |

---

## 4. DỮ LIỆU ĐIỂM MỐC

Hệ thống yêu cầu một file model đã được train sẵn để phát hiện các điểm mốc trên khuôn mặt (dùng cho chức năng Liveness/Blink Detection).

* **Tên file:** `shape_predictor_68_face_landmarks.dat`
* **Vị trí đặt:** Thư mục `models/` trong dự án.
* **Nguồn tải:** [http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2](http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2) (Cần giải nén sau khi tải). Nếu bị lỗi hoặc tải lâu dùng nguồn sau
[https://raw.githubusercontent.com/davisking/dlib-models/master/shape_predictor_68_face_landmarks.dat.bz2](https://raw.githubusercontent.com/davisking/dlib-models/master/shape_predictor_68_face_landmarks.dat.bz2)

---

🔹 Linux / macOS
python3.10 -m venv venv
source venv/bin/activate

🔹 Windows (PowerShell)
python -m venv venv
venv\Scripts\activate


Sau khi activate, terminal sẽ có:

(venv)

Nâng cấp pip (khuyên dùng)
pip install --upgrade pip setuptools wheel

Cài thư viện từ requirements.txt
pip install -r requirements.txt
