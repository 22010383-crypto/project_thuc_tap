import cv2
import numpy as np
import dlib
from scipy.spatial import distance as dist
import os
from app.config import Config
import logging

# Sử dụng root logger đã được setup
logger = logging.getLogger(__name__)
logger.info("📦 Module liveness_detector imported")

class ActionLivenessDetector:
    def __init__(self):
        logger.info("🔧 Khởi tạo ActionLivenessDetector...")
        
        if not os.path.exists(Config.SHAPE_PREDICTOR_PATH):
            logger.error(f"❌ Không tìm thấy file {Config.SHAPE_PREDICTOR_PATH}")
            self.predictor = None
        else:
            logger.info(f"✅ Đang load shape predictor từ {Config.SHAPE_PREDICTOR_PATH}")
            self.predictor = dlib.shape_predictor(Config.SHAPE_PREDICTOR_PATH)
            logger.info("✅ Shape predictor loaded thành công")
            
        # Mô hình 3D chuẩn của khuôn mặt người (dùng để tính góc quay)
        self.model_points = np.array([
            (0.0, 0.0, 0.0),             # Mũi (Nose tip)
            (0.0, -330.0, -65.0),        # Cằm (Chin)
            (-225.0, 170.0, -135.0),     # Mắt trái (Left eye left corner)
            (225.0, 170.0, -135.0),      # Mắt phải (Right eye right corner)
            (-150.0, -150.0, -125.0),    # Miệng trái (Left Mouth corner)
            (150.0, -150.0, -125.0)      # Miệng phải (Right mouth corner)
        ], dtype=np.float64)
        
        # Cache camera matrix để tránh tính lại mỗi frame
        self._camera_matrix_cache = {}

    def get_landmarks(self, frame, face_rect):
        """Lấy 68 điểm landmarks từ dlib"""
        if self.predictor is None:
            return None
        
        try:
            # Chuyển đổi tọa độ (top, right, bottom, left) sang dlib rectangle
            top, right, bottom, left = face_rect
            rect = dlib.rectangle(left, top, right, bottom)
            
            # Chuyển sang grayscale chỉ 1 lần
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            
            shape = self.predictor(gray, rect)
            return shape
        except Exception as e:
            logger.debug(f"⚠️ Lỗi get_landmarks: {e}")
            return None

    def calculate_ear(self, shape):
        """
        Thuật toán tính tỷ lệ mở mắt (EAR) - Optimized.
        Công thức: (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        """
        try:
            # Lấy tọa độ điểm landmarks - chỉ lấy điểm cần thiết
            def get_points(indices):
                return np.array([[shape.part(i).x, shape.part(i).y] for i in indices])
            
            # Mắt trái: điểm 42-47, Mắt phải: điểm 36-41
            left_eye = get_points(range(42, 48))
            right_eye = get_points(range(36, 42))

            def eye_ratio(eye):
                # Khoảng cách dọc (mí trên - mí dưới)
                A = dist.euclidean(eye[1], eye[5])
                B = dist.euclidean(eye[2], eye[4])
                # Khoảng cách ngang (khóe mắt)
                C = dist.euclidean(eye[0], eye[3])
                return (A + B) / (2.0 * C)

            ear = (eye_ratio(left_eye) + eye_ratio(right_eye)) / 2.0
            return ear
        except Exception as e:
            logger.debug(f"⚠️ Lỗi calculate_ear: {e}")
            return 1.0

    def _get_camera_matrix(self, frame_shape):
        """Cache camera matrix để tránh tính lại"""
        shape_key = (frame_shape[1], frame_shape[0])  # (width, height)
        
        if shape_key not in self._camera_matrix_cache:
            focal_length = frame_shape[1]
            center = (frame_shape[1] / 2, frame_shape[0] / 2)
            
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype=np.float64)
            
            self._camera_matrix_cache[shape_key] = camera_matrix
            logger.debug(f"📐 Cached camera matrix for {shape_key}")
        
        return self._camera_matrix_cache[shape_key]

    def calculate_pose(self, frame, shape):
        """
        Thuật toán tính góc quay đầu (Yaw) dùng PnP - Optimized
        """
        try:
            # Lấy điểm landmarks cần thiết
            image_points = np.array([
                [shape.part(30).x, shape.part(30).y],  # Mũi
                [shape.part(8).x, shape.part(8).y],    # Cằm
                [shape.part(36).x, shape.part(36).y],  # Mắt trái
                [shape.part(45).x, shape.part(45).y],  # Mắt phải
                [shape.part(48).x, shape.part(48).y],  # Miệng trái
                [shape.part(54).x, shape.part(54).y]   # Miệng phải
            ], dtype=np.float64)

            # Sử dụng camera matrix đã cache
            camera_matrix = self._get_camera_matrix(frame.shape)
            dist_coeffs = np.zeros((4, 1), dtype=np.float64)

            # Giải bài toán PnP với SOLVEPNP_ITERATIVE (nhanh hơn)
            success, rotation_vector, _ = cv2.solvePnP(
                self.model_points,
                image_points,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE
            )
            
            if not success:
                return 0.0
            
            # Chuyển vector xoay sang ma trận rotation
            rmat, _ = cv2.Rodrigues(rotation_vector)
            
            # Tính góc Yaw từ rotation matrix (nhanh hơn RQDecomp3x3)
            # Yaw = atan2(r21, r11)
            yaw = np.arctan2(rmat[2, 0], rmat[0, 0]) * 180.0 / np.pi
            
            # Giới hạn Yaw trong khoảng [-90, 90]
            yaw = np.clip(yaw, -90, 90)
            
            return yaw
            
        except Exception as e:
            logger.debug(f"⚠️ Lỗi calculate_pose: {e}")
            return 0.0

    def analyze_action(self, frame, face_rect):
        """
        Trả về dữ liệu hành động để lớp logic xử lý - Optimized
        """
        shape = self.get_landmarks(frame, face_rect)
        if shape is None:
            return {"valid": False, "ear": 1.0, "yaw": 0.0}

        ear = self.calculate_ear(shape)
        yaw = self.calculate_pose(frame, shape)
        
        return {
            "valid": True,
            "ear": ear,
            "yaw": yaw
        }