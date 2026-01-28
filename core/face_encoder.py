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
        if os.path.exists(Config.ENCODINGS_PATH):
            try:
                with open(Config.ENCODINGS_PATH, "rb") as f:
                    data = pickle.load(f)
                    self.known_encodings = data.get("encodings", [])
                    self.known_ids = data.get("ids", [])
                print(f"[INFO] Đã load {len(self.known_encodings)} khuôn mặt.")
            except Exception as e:
                print(f"[ERROR] Lỗi đọc DB: {e}")
                self.known_encodings = []
                self.known_ids = []
        else:
            os.makedirs(os.path.dirname(Config.ENCODINGS_PATH), exist_ok=True)

    def save_database(self):
        data = {"encodings": self.known_encodings, "ids": self.known_ids}
        try:
            with open(Config.ENCODINGS_PATH, "wb") as f:
                pickle.dump(data, f)
            print("[INFO] Saved DB.")
        except Exception as e:
            print(f"[ERROR] Save failed: {e}")

    def _prepare_image(self, frame):
        """
        Hàm xử lý ảnh 'bất khả chiến bại' cho macOS.
        Đảm bảo 100% ảnh là uint8, RGB và C-Contiguous.
        """
        if frame is None: return None
        
        # 1. Đảm bảo là numpy array
        if not isinstance(frame, np.ndarray):
            frame = np.array(frame)

        # 2. Xóa kênh Alpha (nếu có) - Mac camera đôi khi trả về BGRA
        if frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        # 3. Ép kiểu uint8 (0-255) - Quan trọng nhất
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)

        # 4. Chuyển BGR -> RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 5. Ép bộ nhớ liên tục (C-Contiguous) - Fix lỗi RuntimeError dlib
        # Đây là bước quan trọng mà code trước có thể chưa xử lý triệt để
        rgb_frame = np.ascontiguousarray(rgb_frame)
        
        return rgb_frame

    def is_face_registered(self, encoding):
        if not self.known_encodings: return False, None
        try:
            distances = face_recognition.face_distance(self.known_encodings, encoding)
            min_dist = np.min(distances)
            if min_dist < Config.MATCH_TOLERANCE:
                return True, self.known_ids[np.argmin(distances)]
        except: pass
        return False, None

    def add_face(self, frame, user_id):
        # Bước 1: Chuẩn bị ảnh thật kỹ
        rgb_frame = self._prepare_image(frame)
        if rgb_frame is None: return False, "Ảnh lỗi"

        try:
            # Bước 2: Detect
            # Dùng model detection chuẩn (hog)
            boxes = face_recognition.face_locations(rgb_frame, model=Config.DETECTION_MODEL)
            
            if not boxes: return False, "Không thấy mặt"
            if len(boxes) > 1: return False, "Nhiều người quá"

            # Bước 3: Encode
            encodings = face_recognition.face_encodings(rgb_frame, boxes, num_jitters=1)
            if not encodings: return False, "Ảnh mờ/Lỗi encode"
            
            new_encoding = encodings[0]
            
            # Bước 4: Check trùng
            is_dup, dup_id = self.is_face_registered(new_encoding)
            if is_dup:
                if dup_id == user_id: # Cập nhật lại chính mình
                    idx = self.known_ids.index(user_id)
                    self.known_encodings[idx] = new_encoding
                    self.save_database()
                    return True, "Cập nhật thành công"
                return False, f"Trùng với ID: {dup_id}"

            # Bước 5: Lưu mới
            self.known_encodings.append(new_encoding)
            self.known_ids.append(user_id)
            self.save_database()
            return True, "Đăng ký thành công"

        except RuntimeError as re:
            # Bắt riêng lỗi này để debug
            print(f"[FATAL ERROR] Dlib Image Type Error: {re}")
            print(f"Debug Info: Shape={rgb_frame.shape}, Dtype={rgb_frame.dtype}, Contiguous={rgb_frame.flags['C_CONTIGUOUS']}")
            return False, "Lỗi hệ thống (Image Type)"
        except Exception as e:
            print(f"[ERROR] Add Face: {e}")
            return False, str(e)

    def encode(self, frame, face_locations):
        rgb_frame = self._prepare_image(frame)
        if rgb_frame is None: return []
        try:
            return face_recognition.face_encodings(rgb_frame, face_locations, num_jitters=1)
        except: return []

    def remove_encoding(self, user_id):
        to_keep = [i for i, uid in enumerate(self.known_ids) if uid != user_id]
        if len(to_keep) == len(self.known_ids): return False
        
        self.known_encodings = [self.known_encodings[i] for i in to_keep]
        self.known_ids = [self.known_ids[i] for i in to_keep]
        self.save_database()
        return True