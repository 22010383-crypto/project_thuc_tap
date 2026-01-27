import face_recognition
import numpy as np
from app.config import Config

class FaceMatcher:
    def __init__(self, encoder):
        # Matcher cần dữ liệu vector từ Encoder đang giữ trong RAM
        self.encoder = encoder

    def find_match(self, unknown_encoding):
        """
        So sánh vector lạ với toàn bộ vector trong DB.
        Sử dụng toán học để tính khoảng cách.
        """
        # Nếu DB rỗng
        if not self.encoder.known_encodings:
            return None, 1.0

        # Tính khoảng cách Euclidean giữa vector lạ và TẤT CẢ vector đã biết
        # Hàm này trả về một mảng khoảng cách: [0.4, 0.8, 0.2, ...]
        distances = face_recognition.face_distance(self.encoder.known_encodings, unknown_encoding)
        
        # Tìm khoảng cách nhỏ nhất (người giống nhất)
        best_match_index = np.argmin(distances)
        best_distance = distances[best_match_index]

        # Kiểm tra ngưỡng chấp nhận
        if best_distance < Config.MATCH_TOLERANCE:
            user_id = self.encoder.known_ids[best_match_index]
            confidence = 1.0 - best_distance # Độ tin cậy (tham khảo)
            return user_id, confidence
        
        return None, best_distance