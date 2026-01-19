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
                print(f"✅ Đã load {len(self.known_encodings)} khuôn mặt vào bộ nhớ.")
            except Exception as e:
                print(f"⚠️ Lỗi đọc file encoding: {e}")
                self.known_encodings = []
                self.known_ids = []
    def is_face_registered(self, encoding):
        """
        Kiểm tra xem vector này đã tồn tại trong DB chưa.
        Trả về: (IsDuplicate: bool, MatchedID: str)
        """
        if not self.known_encodings:
            return False, None
            
        # Tính khoảng cách với TẤT CẢ khuôn mặt đang có
        distances = face_recognition.face_distance(self.known_encodings, encoding)
        min_dist = np.min(distances)
        
        if min_dist < Config.MATCH_TOLERANCE:
            index = np.argmin(distances)
            return True, self.known_ids[index]
            
        return False, None
    
    def save_database(self):
        """Lưu danh sách vector xuống file"""
        data = {
            "encodings": self.known_encodings,
            "ids": self.known_ids
        }
        os.makedirs(os.path.dirname(Config.ENCODINGS_PATH), exist_ok=True)
        with open(Config.ENCODINGS_PATH, "wb") as f:
            pickle.dump(data, f)
        print("💾 Đã lưu dữ liệu Vector xuống ổ cứng.")

    def encode(self, frame, face_locations):
        """
        Mã hóa khuôn mặt từ frame và tọa độ.
        Sửa lỗi: Thêm np.ascontiguousarray
        """
        # Chuyển BGR -> RGB và sắp xếp lại bộ nhớ cho liên tục
        rgb_frame = np.ascontiguousarray(frame[:, :, ::-1])
        
        try:
            encodings = face_recognition.face_encodings(rgb_frame, face_locations, num_jitters=1)
            return encodings
        except Exception as e:
            print(f"❌ Lỗi khi encode: {e}")
            return []

    def add_face(self, frame, user_id):
        rgb_frame = np.ascontiguousarray(frame[:, :, ::-1])
        boxes = face_recognition.face_locations(rgb_frame, model=Config.DETECTION_MODEL)
        
        if not boxes:
            return False, "Không tìm thấy khuôn mặt!"
        if len(boxes) > 1:
            return False, "Chỉ được đứng 1 mình!"

        try:
            encodings = face_recognition.face_encodings(rgb_frame, boxes, num_jitters=1)
            if not encodings:
                return False, "Ảnh không rõ nét."
            
            new_encoding = encodings[0]
            
            # 1. Kiểm tra trùng lặp trước khi lưu
            is_dup, dup_id = self.is_face_registered(new_encoding)
            if is_dup:
                return False, f"Người này đã có trong hệ thống!\n(ID trùng: {dup_id})"

            # 2. Lưu nếu không trùng
            self.known_encodings.append(new_encoding)
            self.known_ids.append(user_id)
            self.save_database()
            return True, "Thành công"
            
        except Exception as e:
            return False, str(e)
    
    def remove_encoding(self, user_id):
        # Lọc bỏ các vector của user_id này (dùng list comprehension)
        # Lưu ý: 1 user có thể có nhiều ảnh mẫu nếu bạn nâng cấp sau này
        # Ở đây giả sử 1 user 1 vector
        indices_to_keep = [i for i, uid in enumerate(self.known_ids) if uid != user_id]
        
        self.known_encodings = [self.known_encodings[i] for i in indices_to_keep]
        self.known_ids = [self.known_ids[i] for i in indices_to_keep]
        
        self.save_database()