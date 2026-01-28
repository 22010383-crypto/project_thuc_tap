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

    def _force_cleanup(self, frame):
        """
        Hàm này phá hủy cấu trúc bộ nhớ cũ và xây lại từ đầu.
        Bắt buộc dlib phải chấp nhận ảnh này.
        """
        if frame is None: return None
        
        # 1. Đảm bảo input là numpy array
        img = np.array(frame)
        
        # 2. Xử lý kênh Alpha (Mac webcam hay trả về 4 kênh BGRA)
        if len(img.shape) == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
        # 3. Chuyển BGR -> RGB (Face_recognition cần RGB)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # 4. NUCLEAR OPTION: Tạo một mảng hoàn toàn mới, ép kiểu uint8, ép bộ nhớ C-Style
        # order='C' là chìa khóa để fix lỗi stride trên Mac
        clean_frame = np.array(img_rgb, dtype=np.uint8, copy=True, order='C')
        
        # Kiểm tra lần cuối
        if not clean_frame.flags['C_CONTIGUOUS']:
            clean_frame = np.ascontiguousarray(clean_frame, dtype=np.uint8)
            
        return clean_frame

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
        # --- BƯỚC 1: CLEAN UP ẢNH ---
        rgb_frame = self._force_cleanup(frame)
        if rgb_frame is None: return False, "Ảnh lỗi"

        try:
            # --- BƯỚC 2: DETECT ---
            # Thử detect trực tiếp trên ảnh màu đã làm sạch
            boxes = face_recognition.face_locations(rgb_frame, model=Config.DETECTION_MODEL)
            
            # Nếu thất bại, thử convert sang Gray rồi detect (Fallback)
            if not boxes:
                gray = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2GRAY)
                boxes = face_recognition.face_locations(gray, model=Config.DETECTION_MODEL)

            if not boxes: return False, "Không thấy mặt (Đứng gần/Sáng hơn)"
            if len(boxes) > 1: return False, "Nhiều người quá (Chỉ đứng 1 mình)"

            # --- BƯỚC 3: ENCODE ---
            # Lưu ý: Encode luôn cần ảnh màu
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
                    return True, "Cập nhật thành công"
                return False, f"Trùng với ID: {dup_id}"

            self.known_encodings.append(new_encoding)
            self.known_ids.append(user_id)
            self.save_database()
            return True, "Đăng ký thành công"

        except RuntimeError as re:
            # Nếu vẫn lỗi, in thông số ra để kiểm tra
            print(f"[CRITICAL ERROR] Dlib Image Rejection: {re}")
            print(f"Stats: Shape={rgb_frame.shape}, Dtype={rgb_frame.dtype}, C-Contiguous={rgb_frame.flags['C_CONTIGUOUS']}")
            return False, "Lỗi tương thích hệ thống (Xem log)"
        except Exception as e:
            print(f"[ERROR] Add Face General: {e}")
            return False, str(e)

    def encode(self, frame, face_locations):
        # Dùng cho luồng điểm danh
        rgb_frame = self._force_cleanup(frame)
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