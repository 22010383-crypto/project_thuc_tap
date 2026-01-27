import cv2
import face_recognition
from app.config import Config

class FaceDetector:
    def __init__(self):
        self.model = Config.DETECTION_MODEL  # 'hog'
        self.scale = Config.RESIZE_SCALE

    def detect(self, frame):
        """
        Input: Frame ảnh gốc (kích thước lớn)
        Output: List các tọa độ khuôn mặt [(top, right, bottom, left), ...] đã scale về kích thước gốc
        """
        # 1. Resize ảnh nhỏ lại để CPU xử lý nhanh hơn
        small_frame = cv2.resize(frame, (0, 0), fx=self.scale, fy=self.scale)
        
        # 2. Chuyển hệ màu BGR (OpenCV) -> RGB (dlib/face_recognition)
        rgb_small_frame = small_frame[:, :, ::-1] # Hoặc cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # 3. Chạy thuật toán HOG để tìm vị trí khuôn mặt
        # HOG hoạt động dựa trên việc phân tích các cạnh và hướng của điểm ảnh
        face_locations_small = face_recognition.face_locations(rgb_small_frame, model=self.model)

        # 4. Tính lại tọa độ cho ảnh gốc (vì nãy đã resize nhỏ đi)
        face_locations = []
        inv_scale = 1 / self.scale
        for (top, right, bottom, left) in face_locations_small:
            top = int(top * inv_scale)
            right = int(right * inv_scale)
            bottom = int(bottom * inv_scale)
            left = int(left * inv_scale)
            face_locations.append((top, right, bottom, left))

        return face_locations