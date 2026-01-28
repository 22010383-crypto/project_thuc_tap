import face_recognition
import pickle
import os
import cv2
import numpy as np
from app.config import Config

class FaceEncoder:
    def __init__(self):
        self.known_encodings = []
        self.known_ids = []
        self.load_database()

    def load_database(self):
        """Load danh sách vector từ file lên RAM"""
        if os.path.exists(Config.ENCODINGS_PATH):
            try:
                with open(Config.ENCODINGS_PATH, "rb") as f:
                    data = pickle.load(f)
                    self.known_encodings = data.get("encodings", [])
                    self.known_ids = data.get("ids", [])
                print(f"[INFO] Đã load {len(self.known_encodings)} khuôn mặt vào bộ nhớ.")
            except Exception as e:
                print(f"[ERROR] Lỗi đọc file encoding: {e}")
                # Reset nếu file lỗi để tránh crash app
                self.known_encodings = []
                self.known_ids = []
        else:
            # Tạo thư mục chứa file nếu chưa có
            os.makedirs(os.path.dirname(Config.ENCODINGS_PATH), exist_ok=True)

    def save_database(self):
        """Lưu danh sách vector xuống file"""
        data = {
            "encodings": self.known_encodings,
            "ids": self.known_ids
        }
        try:
            with open(Config.ENCODINGS_PATH, "wb") as f:
                pickle.dump(data, f)
            print("[INFO] Đã lưu dữ liệu Vector xuống ổ cứng.")
        except Exception as e:
            print(f"[ERROR] Không thể lưu file: {e}")

    def _prepare_image(self, frame):
        """
        Chuẩn hóa ảnh đầu vào để tránh lỗi trên macOS/Linux.
        Chuyển BGR -> RGB và ép kiểu uint8.
        """
        if frame is None: return None
        
        # 1. Ép kiểu uint8 (Bắt buộc cho dlib)
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
            
        # 2. Chuyển BGR (OpenCV) -> RGB (face_recognition)
        rgb_frame = frame[:, :, ::-1]
        
        # 3. Sắp xếp bộ nhớ liên tục (Tăng tốc độ C++)
        return np.ascontiguousarray(rgb_frame)

    def is_face_registered(self, encoding):
        """
        Kiểm tra xem vector này đã tồn tại trong DB chưa.
        Trả về: (IsDuplicate: bool, MatchedID: str)
        """
        if not self.known_encodings:
            return False, None
            
        # Tính khoảng cách Euclidean với TẤT CẢ khuôn mặt đang có
        # distances càng nhỏ -> càng giống
        try:
            distances = face_recognition.face_distance(self.known_encodings, encoding)
            min_dist = np.min(distances)
            
            # Nếu khoảng cách nhỏ hơn ngưỡng (VD: 0.4) -> Là cùng 1 người
            if min_dist < Config.MATCH_TOLERANCE:
                index = np.argmin(distances)
                return True, self.known_ids[index]
        except Exception as e:
            print(f"[WARNING] Lỗi so sánh vector: {e}")
            
        return False, None

    def encode(self, frame, face_locations):
        """
        Mã hóa danh sách các khuôn mặt đã detect được.
        Dùng cho luồng điểm danh (Attendance Loop).
        """
        rgb_frame = self._prepare_image(frame)
        if rgb_frame is None: return []
        
        try:
            # num_jitters=1: Lấy mẫu 1 lần (Nhanh). Tăng lên 10 nếu muốn chính xác hơn nhưng chậm.
            encodings = face_recognition.face_encodings(rgb_frame, face_locations, num_jitters=1)
            return encodings
        except Exception as e:
            print(f"[ERROR] Lỗi khi encode: {e}")
            return []

    def add_face(self, frame, user_id):
        """
        Quy trình thêm khuôn mặt mới (Dùng cho Đăng ký).
        1. Detect -> 2. Encode -> 3. Check Trùng -> 4. Lưu
        """
        rgb_frame = self._prepare_image(frame)
        if rgb_frame is None: return False, "Ảnh bị lỗi"

        # 1. Detect
        # Dùng model từ Config (hog nhanh hơn, cnn chính xác hơn)
        boxes = face_recognition.face_locations(rgb_frame, model=Config.DETECTION_MODEL)
        
        if not boxes:
            return False, "Không tìm thấy khuôn mặt nào!"
        if len(boxes) > 1:
            return False, "Phát hiện nhiều người. Vui lòng chỉ đứng 1 mình!"

        try:
            # 2. Encode
            encodings = face_recognition.face_encodings(rgb_frame, boxes, num_jitters=1)
            if not encodings:
                return False, "Ảnh không rõ nét để mã hóa."
            
            new_encoding = encodings[0]
            
            # 3. Kiểm tra trùng lặp (Logic quan trọng)
            is_dup, dup_id = self.is_face_registered(new_encoding)
            if is_dup:
                # Nếu trùng ID cũ -> Cập nhật lại vector mới (cho chính xác hơn)
                if dup_id == user_id:
                    idx = self.known_ids.index(user_id)
                    self.known_encodings[idx] = new_encoding
                    self.save_database()
                    return True, "Cập nhật dữ liệu khuôn mặt thành công!"
                else:
                    # Nếu trùng mặt người khác -> Báo lỗi
                    return False, f"Khuôn mặt này đã được đăng ký bởi: {dup_id}"

            # 4. Lưu mới nếu không trùng
            self.known_encodings.append(new_encoding)
            self.known_ids.append(user_id)
            self.save_database()
            return True, "Đăng ký thành công"
            
        except Exception as e:
            print(f"[ERROR] Add face exception: {e}")
            return False, "Lỗi hệ thống khi xử lý ảnh."
    
    def remove_encoding(self, user_id):
        """Xóa vector khuôn mặt của user_id khỏi bộ nhớ và file"""
        # Tạo danh sách mới chỉ giữ lại những người KHÔNG phải user_id này
        indices_to_keep = []
        found = False
        
        for i, uid in enumerate(self.known_ids):
            if uid != user_id:
                indices_to_keep.append(i)
            else:
                found = True
        
        if not found:
            return False # Không tìm thấy ID để xóa
            
        # Cập nhật lại list bằng cách lọc
        self.known_encodings = [self.known_encodings[i] for i in indices_to_keep]
        self.known_ids = [self.known_ids[i] for i in indices_to_keep]
        
        # Lưu xuống file ngay lập tức
        self.save_database()
        print(f"[INFO] Đã xóa vector khuôn mặt của: {user_id}")
        return True