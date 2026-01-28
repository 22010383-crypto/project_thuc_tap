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

    def _safe_convert_image(self, frame):
        """
        Hàm 'Lọc sạch' ảnh đầu vào để chạy được trên mọi OS (Mac/Win/Linux).
        Loại bỏ kênh Alpha, ép kiểu uint8, sắp xếp bộ nhớ liên tục.
        """
        if frame is None: return None, None
        
        # 1. Đảm bảo là mảng numpy
        img = np.array(frame)

        # 2. Xử lý kênh Alpha (Mac webcam hay trả về 4 kênh)
        if len(img.shape) == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        # 3. Ép kiểu uint8 (Bắt buộc cho dlib C++)
        if img.dtype != np.uint8:
            img = img.astype(np.uint8)

        # 4. Tạo bản copy bộ nhớ liên tục (Fix lỗi "Unsupported image type" trên Mac)
        # Đây là bước quan trọng nhất!
        rgb_frame = np.ascontiguousarray(img[:, :, ::-1]) # BGR to RGB
        
        # Tạo bản ảnh xám để detect (nhanh hơn & an toàn hơn)
        gray_frame = np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        
        return rgb_frame, gray_frame

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
        # --- BƯỚC 1: LÀM SẠCH ẢNH ---
        rgb_frame, gray_frame = self._safe_convert_image(frame)
        if rgb_frame is None: return False, "Ảnh lỗi/None"

        try:
            # --- BƯỚC 2: DETECT (Ưu tiên ảnh xám cho nhẹ) ---
            # Dùng ảnh xám (2D) để detect giúp tránh lỗi bộ nhớ 3D trên Mac
            boxes = face_recognition.face_locations(gray_frame, model=Config.DETECTION_MODEL)
            
            # Fallback: Nếu ảnh xám không ra, thử lại bằng ảnh màu
            if not boxes:
                boxes = face_recognition.face_locations(rgb_frame, model=Config.DETECTION_MODEL)

            if not boxes: return False, "Không thấy mặt (Hãy đứng gần hơn)"
            if len(boxes) > 1: return False, "Nhiều người quá (Chỉ đứng 1 mình)"

            # --- BƯỚC 3: ENCODE (Bắt buộc dùng ảnh màu) ---
            encodings = face_recognition.face_encodings(rgb_frame, boxes, num_jitters=1)
            
            if not encodings: return False, "Ảnh mờ/Lỗi encode"
            
            new_encoding = encodings[0]
            
            # --- BƯỚC 4: LƯU ---
            is_dup, dup_id = self.is_face_registered(new_encoding)
            if is_dup:
                if dup_id == user_id: 
                    idx = self.known_ids.index(user_id)
                    self.known_encodings[idx] = new_encoding
                    self.save_database()
                    return True, "Cập nhật ảnh mới thành công"
                return False, f"Đã trùng với ID: {dup_id}"

            self.known_encodings.append(new_encoding)
            self.known_ids.append(user_id)
            self.save_database()
            return True, "Đăng ký thành công"

        except Exception as e:
            # In lỗi chi tiết ra terminal để debug
            print(f"[FATAL ERROR] Add Face: {e}")
            return False, "Lỗi hệ thống (Xem log)"

    def encode(self, frame, face_locations):
        # Hàm dùng cho luồng điểm danh (Attendance)
        rgb_frame, _ = self._safe_convert_image(frame)
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