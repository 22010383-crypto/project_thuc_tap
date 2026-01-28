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

    def _prepare_image_robust(self, frame):
        """
        Chuẩn hóa ảnh thành 2 phiên bản:
        1. Gray (2D): Để detect mặt (Tránh lỗi stride trên Mac)
        2. RGB (3D): Để encode đặc điểm
        """
        if frame is None: return None, None
        
        # 1. Ép kiểu dữ liệu an toàn tuyệt đối
        try:
            # Copy dữ liệu ra vùng nhớ mới để ngắt kết nối với buffer của camera
            img = np.array(frame, copy=True)
            
            # Xử lý kênh Alpha (nếu có)
            if img.shape[-1] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
            # Ép về uint8
            if img.dtype != 'uint8':
                img = img.astype('uint8')

            # 2. Tạo ảnh Xám (Gray) - 2D Array
            # Dlib detect trên ảnh này cực nhanh và không lỗi format
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = np.ascontiguousarray(gray)

            # 3. Tạo ảnh Màu (RGB) - 3D Array
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            rgb = np.ascontiguousarray(rgb)
            
            return rgb, gray
            
        except Exception as e:
            print(f"[PREPARE ERROR] {e}")
            return None, None

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
        # Bước 1: Chuẩn bị 2 phiên bản ảnh
        rgb_frame, gray_frame = self._prepare_image_robust(frame)
        if rgb_frame is None: return False, "Ảnh hỏng/Lỗi camera"

        try:
            # Bước 2: DETECT TRÊN ẢNH XÁM (Quan trọng)
            # Thay vì đưa RGB vào (hay lỗi), ta đưa Gray vào.
            # face_recognition hỗ trợ detect trên ảnh xám.
            boxes = face_recognition.face_locations(gray_frame, model=Config.DETECTION_MODEL)
            
            if not boxes:
                return False, "Không tìm thấy khuôn mặt (Thử đứng nơi sáng hơn)"
            
            if len(boxes) > 1:
                return False, "Phát hiện nhiều người. Vui lòng đứng 1 mình!"

            # Bước 3: ENCODE TRÊN ẢNH MÀU
            # Lúc này đã có tọa độ (boxes) từ ảnh xám, ta áp nó vào ảnh màu để lấy đặc điểm
            encodings = face_recognition.face_encodings(rgb_frame, boxes, num_jitters=1)
            
            if not encodings:
                return False, "Ảnh mờ, không thể mã hóa khuôn mặt."
            
            new_encoding = encodings[0]
            
            # Bước 4: Check trùng & Lưu
            is_dup, dup_id = self.is_face_registered(new_encoding)
            if is_dup:
                if dup_id == user_id: 
                    # Update lại
                    idx = self.known_ids.index(user_id)
                    self.known_encodings[idx] = new_encoding
                    self.save_database()
                    return True, "Cập nhật dữ liệu thành công"
                return False, f"Khuôn mặt này đã thuộc về: {dup_id}"

            self.known_encodings.append(new_encoding)
            self.known_ids.append(user_id)
            self.save_database()
            return True, "Đăng ký thành công!"

        except RuntimeError as re:
            # Nếu vẫn lỗi, ta thử fallback cuối cùng: Encode trên ảnh xám (ít chính xác hơn nhưng không lỗi)
            print(f"[RETRY] Dlib Error on RGB: {re}. Trying Gray encoding...")
            try:
                # Fallback: Detect Gray -> Encode Gray (Chấp nhận giảm độ chính xác chút xíu để không crash)
                boxes = face_recognition.face_locations(gray_frame, model=Config.DETECTION_MODEL)
                # Convert gray back to fake RGB for encoding
                fake_rgb = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2RGB)
                encodings = face_recognition.face_encodings(fake_rgb, boxes)
                if encodings:
                    new_encoding = encodings[0]
                    self.known_encodings.append(new_encoding)
                    self.known_ids.append(user_id)
                    self.save_database()
                    return True, "Đăng ký thành công (Chế độ Grayscale)"
            except Exception as e2:
                return False, f"Lỗi hệ thống nghiêm trọng: {e2}"
                
            return False, "Lỗi không xác định."

        except Exception as e:
            print(f"[ERROR] Add Face General: {e}")
            return False, f"Lỗi: {str(e)}"

    def encode(self, frame, face_locations):
        # Dùng cho luồng điểm danh
        rgb_frame, _ = self._prepare_image_robust(frame)
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