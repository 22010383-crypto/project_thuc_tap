import cv2
import numpy as np
import dlib
from scipy.spatial import distance as dist
import os
from app.config import Config
import logging

logger = logging.getLogger(__name__)

class ActionLivenessDetector:
    def __init__(self):
        if not os.path.exists(Config.SHAPE_PREDICTOR_PATH):
            logger.error(f"❌ Không tìm thấy file {Config.SHAPE_PREDICTOR_PATH}")
            self.predictor = None
        else:
            self.predictor = dlib.shape_predictor(Config.SHAPE_PREDICTOR_PATH)
            
        # Mô hình 3D chuẩn (Generic Face Model)
        self.model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip
            (0.0, -330.0, -65.0),        # Chin
            (-225.0, 170.0, -135.0),     # Left eye left corner
            (225.0, 170.0, -135.0),      # Right eye right corner
            (-150.0, -150.0, -125.0),    # Left Mouth corner
            (150.0, -150.0, -125.0)      # Right mouth corner
        ], dtype=np.float64)
        
        self._camera_matrix_cache = {}

    def _safe_gray(self, frame):
        """
        Chuyển ảnh xám an toàn cho Dlib (Fix lỗi macOS Memory Stride)
        """
        try:
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            # QUAN TRỌNG: Ép bộ nhớ liên tục
            return np.ascontiguousarray(gray)
        except Exception:
            return None

    def get_landmarks(self, frame, face_rect):
        """Lấy 68 điểm landmarks"""
        if self.predictor is None: return None
        
        try:
            # Convert coord (top, right, bottom, left) -> dlib.rectangle
            t, r, b, l = face_rect
            rect = dlib.rectangle(l, t, r, b)
            
            gray = self._safe_gray(frame)
            if gray is None: return None
            
            return self.predictor(gray, rect)
        except: return None

    def calculate_ear(self, shape):
        """Tính tỷ lệ mở mắt (EAR)"""
        pts = np.array([[shape.part(i).x, shape.part(i).y] for i in range(68)])
        
        # Mắt trái (42-47), Mắt phải (36-41)
        left_eye = pts[42:48]
        right_eye = pts[36:42]

        def eye_ratio(e):
            A = dist.euclidean(e[1], e[5])
            B = dist.euclidean(e[2], e[4])
            C = dist.euclidean(e[0], e[3])
            return (A + B) / (2.0 * C)

        return (eye_ratio(left_eye) + eye_ratio(right_eye)) / 2.0

    def calculate_pose(self, frame, shape):
        """Tính góc quay đầu (Yaw) """
        try:
            image_points = np.array([
                (shape.part(30).x, shape.part(30).y),     # Nose
                (shape.part(8).x, shape.part(8).y),       # Chin
                (shape.part(36).x, shape.part(36).y),     # Left Eye
                (shape.part(45).x, shape.part(45).y),     # Right Eye
                (shape.part(48).x, shape.part(48).y),     # Left Mouth
                (shape.part(54).x, shape.part(54).y)      # Right Mouth
            ], dtype=np.float64)

            # Camera Matrix (Cache)
            h, w = frame.shape[:2]
            if (w, h) not in self._camera_matrix_cache:
                focal_length = w
                center = (w / 2, h / 2)
                self._camera_matrix_cache[(w, h)] = np.array([
                    [focal_length, 0, center[0]],
                    [0, focal_length, center[1]],
                    [0, 0, 1]], dtype=np.float64)
            
            camera_matrix = self._camera_matrix_cache[(w, h)]
            dist_coeffs = np.zeros((4, 1))

            success, rot_vec, _ = cv2.solvePnP(self.model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE)
            
            if not success: return 0.0
            
            rmat, _ = cv2.Rodrigues(rot_vec)
            # Tính Yaw: atan2(R[2,0], R[0,0]) -> Xoay trái phải
            yaw = np.arctan2(rmat[2, 0], rmat[0, 0]) * 180.0 / np.pi
            return float(yaw)
        except: return 0.0

    def analyze_action(self, frame, face_rect):
        """API chính gọi từ bên ngoài"""
        shape = self.get_landmarks(frame, face_rect)
        if shape is None: return {"valid": False, "ear": 1.0, "yaw": 0.0}

        ear = self.calculate_ear(shape)
        yaw = self.calculate_pose(frame, shape)
        
        return {"valid": True, "ear": ear, "yaw": yaw}