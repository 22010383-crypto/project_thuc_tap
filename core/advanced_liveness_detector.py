import cv2
import numpy as np
import mediapipe as mp
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class LivenessDetector:
    """
    Robust liveness detector using MediaPipe Face Mesh.
    
    Implements:
    1. Active Liveness: Blink Detection (EAR), Head Pose (solvePnP)
    2. Passive Liveness: Blur, Glare, Frequency Analysis (FFT)
    """
    
    # MediaPipe Face Mesh landmark indices
    LEFT_EYE_IDXS = [33, 160, 158, 133, 153, 144]   # Upper and lower eyelids
    RIGHT_EYE_IDXS = [362, 385, 387, 263, 373, 380]
    
    # 3D Face Model for solvePnP (canonical face)
    FACE_3D_MODEL = np.array([
        [0.0, 0.0, 0.0],            # Nose tip
        [0.0, -330.0, -65.0],       # Chin
        [-225.0, 170.0, -135.0],    # Left eye left corner
        [225.0, 170.0, -135.0],     # Right eye right corner
        [-150.0, -150.0, -125.0],   # Left mouth corner
        [150.0, -150.0, -125.0]     # Right mouth corner
    ], dtype=np.float64)
    
    # Landmark indices for solvePnP (MediaPipe 468 landmarks)
    POSE_LANDMARKS = [1, 152, 33, 263, 61, 291]  # Nose, Chin, Left eye, Right eye, Mouth corners
    
    def __init__(self, 
                 ear_threshold: float = 0.25,
                 blink_consec_frames: int = 3,
                 head_pose_threshold: float = 15.0,
                 blur_threshold: float = 100.0,
                 static_image_mode: bool = False):
        """
        Initialize Liveness Detector.
        
        Args:
            ear_threshold: Eye Aspect Ratio below this = closed eye
            blink_consec_frames: Frames required for valid blink
            head_pose_threshold: Degrees for head turn detection
            blur_threshold: Laplacian variance threshold
            static_image_mode: MediaPipe mode (False for video)
        """
        logger.info("🔧 Initializing Advanced LivenessDetector with MediaPipe...")
        
        # MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=static_image_mode,
            max_num_faces=1,
            refine_landmarks=True,  # Include iris landmarks
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Thresholds
        self.EAR_THRESHOLD = ear_threshold
        self.BLINK_CONSEC_FRAMES = blink_consec_frames
        self.HEAD_POSE_THRESHOLD = head_pose_threshold
        self.BLUR_THRESHOLD = blur_threshold
        
        # State tracking
        self.blink_counter = 0
        self.frame_counter = 0
        self.ear_history = []
        
        # Camera matrix cache
        self._camera_matrix_cache = {}
        
        logger.info("✅ LivenessDetector initialized successfully")
    
    def analyze(self, frame: np.ndarray, face_box: Optional[Tuple[int, int, int, int]] = None) -> Dict:
        """
        Main analysis method.
        
        Args:
            frame: BGR image (numpy array)
            face_box: Optional (top, right, bottom, left) for optimization
        
        Returns:
            {
                'is_real': bool,
                'score': float (0-1),
                'action': str,
                'reason': str,
                'details': dict
            }
        """
        if frame is None or frame.size == 0:
            return self._error_result("Invalid frame")
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Extract face region if box provided (optimization)
        if face_box:
            top, right, bottom, left = face_box
            face_region = frame[top:bottom, left:right]
        else:
            face_region = frame
        
        # Process with MediaPipe
        results = self.face_mesh.process(rgb_frame)
        
        if not results.multi_face_landmarks:
            return self._error_result("No face detected by MediaPipe")
        
        landmarks = results.multi_face_landmarks[0]
        
        # === ACTIVE LIVENESS ===
        active_score, active_details = self._check_active_liveness(frame, landmarks)
        
        # === PASSIVE LIVENESS ===
        passive_score, passive_details = self._check_passive_liveness(face_region)
        
        # === AGGREGATE SCORE ===
        # Weighted average (Active 60%, Passive 40%)
        final_score = active_score * 0.6 + passive_score * 0.4
        
        is_real = final_score >= 0.5
        
        # Determine action/reason
        if not is_real:
            if passive_score < 0.3:
                reason = passive_details['reason']
                action = "rejected_passive"
            else:
                reason = active_details['reason']
                action = "rejected_active"
        else:
            reason = "Liveness verified"
            action = "approved"
        
        return {
            'is_real': is_real,
            'score': float(final_score),
            'action': action,
            'reason': reason,
            'details': {
                'active': active_details,
                'passive': passive_details
            }
        }
    
    def _check_active_liveness(self, frame: np.ndarray, landmarks) -> Tuple[float, Dict]:
        """
        Check active liveness (blink + head pose).
        
        Returns:
            (score, details_dict)
        """
        h, w = frame.shape[:2]
        
        # Extract landmark coordinates
        landmark_coords = self._extract_landmark_coords(landmarks, w, h)
        
        # 1. Blink Detection (EAR)
        ear = self._calculate_ear(landmark_coords)
        self.ear_history.append(ear)
        
        blink_detected = False
        if ear < self.EAR_THRESHOLD:
            self.frame_counter += 1
        else:
            if self.frame_counter >= self.BLINK_CONSEC_FRAMES:
                self.blink_counter += 1
                blink_detected = True
            self.frame_counter = 0
        
        # 2. Head Pose Estimation
        yaw, pitch, roll = self._estimate_head_pose(frame, landmark_coords)
        
        # Check if head turned significantly
        head_moved = abs(yaw) > self.HEAD_POSE_THRESHOLD or abs(pitch) > self.HEAD_POSE_THRESHOLD
        
        # 3. EAR Variance (detect static image)
        ear_variance = np.var(self.ear_history[-30:]) if len(self.ear_history) >= 30 else 0.0
        is_dynamic = ear_variance > 0.001
        
        # Scoring
        score = 0.0
        reason_parts = []
        
        if blink_detected or self.blink_counter > 0:
            score += 0.4
        else:
            reason_parts.append("No blink detected")
        
        if head_moved:
            score += 0.3
        else:
            reason_parts.append("Head static")
        
        if is_dynamic:
            score += 0.3
        else:
            reason_parts.append("EAR static (photo/screen)")
        
        reason = "; ".join(reason_parts) if reason_parts else "Active checks passed"
        
        return score, {
            'ear': float(ear),
            'yaw': float(yaw),
            'pitch': float(pitch),
            'roll': float(roll),
            'blink_count': self.blink_counter,
            'ear_variance': float(ear_variance),
            'reason': reason
        }
    
    def _check_passive_liveness(self, face_region: np.ndarray) -> Tuple[float, Dict]:
        """
        Check passive liveness (blur, glare, frequency).
        
        Returns:
            (score, details_dict)
        """
        score = 0.0
        reason_parts = []
        
        gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
        
        # 1. Blur Detection (Laplacian Variance)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if blur_score >= self.BLUR_THRESHOLD:
            score += 0.35
        else:
            reason_parts.append(f"Too blurry (score: {blur_score:.1f})")
        
        # 2. Glare/Reflection Detection (HSV Value channel)
        glare_score = self._detect_glare(face_region)
        
        if glare_score < 0.3:  # Low glare = good
            score += 0.30
        else:
            reason_parts.append(f"Screen glare detected (score: {glare_score:.2f})")
        
        # 3. Frequency Analysis (FFT - detect printed photo)
        freq_score = self._analyze_frequency(gray)
        
        if freq_score >= 0.5:
            score += 0.35
        else:
            reason_parts.append(f"Low high-frequency content (printed?)")
        
        reason = "; ".join(reason_parts) if reason_parts else "Passive checks passed"
        
        return score, {
            'blur_score': float(blur_score),
            'glare_score': float(glare_score),
            'frequency_score': float(freq_score),
            'reason': reason
        }
    
    def _calculate_ear(self, landmarks: np.ndarray) -> float:
        """
        Calculate Eye Aspect Ratio from MediaPipe landmarks.
        
        EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
        """
        def eye_aspect_ratio(eye_points):
            # Vertical distances
            A = np.linalg.norm(eye_points[1] - eye_points[5])
            B = np.linalg.norm(eye_points[2] - eye_points[4])
            # Horizontal distance
            C = np.linalg.norm(eye_points[0] - eye_points[3])
            return (A + B) / (2.0 * C + 1e-6)
        
        left_eye = landmarks[self.LEFT_EYE_IDXS]
        right_eye = landmarks[self.RIGHT_EYE_IDXS]
        
        left_ear = eye_aspect_ratio(left_eye)
        right_ear = eye_aspect_ratio(right_eye)
        
        return (left_ear + right_ear) / 2.0
    
    def _estimate_head_pose(self, frame: np.ndarray, landmarks: np.ndarray) -> Tuple[float, float, float]:
        """
        Estimate head pose (yaw, pitch, roll) using solvePnP.
        
        Returns:
            (yaw, pitch, roll) in degrees
        """
        h, w = frame.shape[:2]
        
        # Get camera matrix
        camera_matrix = self._get_camera_matrix(w, h)
        dist_coeffs = np.zeros((4, 1))
        
        # 2D image points
        image_points = landmarks[self.POSE_LANDMARKS]
        
        # Solve PnP
        success, rotation_vec, _ = cv2.solvePnP(
            self.FACE_3D_MODEL,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        
        if not success:
            return 0.0, 0.0, 0.0
        
        # Convert rotation vector to matrix
        rotation_mat, _ = cv2.Rodrigues(rotation_vec)
        
        # Extract Euler angles
        sy = np.sqrt(rotation_mat[0, 0]**2 + rotation_mat[1, 0]**2)
        
        singular = sy < 1e-6
        
        if not singular:
            pitch = np.arctan2(rotation_mat[2, 1], rotation_mat[2, 2])
            yaw = np.arctan2(-rotation_mat[2, 0], sy)
            roll = np.arctan2(rotation_mat[1, 0], rotation_mat[0, 0])
        else:
            pitch = np.arctan2(-rotation_mat[1, 2], rotation_mat[1, 1])
            yaw = np.arctan2(-rotation_mat[2, 0], sy)
            roll = 0
        
        # Convert to degrees
        return (
            np.degrees(yaw),
            np.degrees(pitch),
            np.degrees(roll)
        )
    
    def _detect_glare(self, face_region: np.ndarray) -> float:
        """
        Detect glare/reflection (common on phone screens).
        
        Returns:
            glare_score (0-1, higher = more glare)
        """
        hsv = cv2.cvtColor(face_region, cv2.COLOR_BGR2HSV)
        value_channel = hsv[:, :, 2]
        
        # Find bright spots
        bright_threshold = 200
        bright_pixels = np.sum(value_channel > bright_threshold)
        total_pixels = value_channel.size
        
        glare_ratio = bright_pixels / total_pixels
        
        return min(glare_ratio * 10, 1.0)  # Normalize
    
    def _analyze_frequency(self, gray_face: np.ndarray) -> float:
        """
        Analyze frequency domain using FFT.
        Real faces have more high-frequency content than printed photos.
        
        Returns:
            freq_score (0-1, higher = more real)
        """
        # Apply FFT
        f_transform = np.fft.fft2(gray_face)
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)
        
        h, w = magnitude.shape
        center_h, center_w = h // 2, w // 2
        
        # Define low-frequency region (center)
        mask_size = 30
        low_freq = magnitude[
            center_h - mask_size:center_h + mask_size,
            center_w - mask_size:center_w + mask_size
        ]
        
        # High-frequency region (outer)
        high_freq_mask = np.ones((h, w), dtype=bool)
        high_freq_mask[
            center_h - mask_size:center_h + mask_size,
            center_w - mask_size:center_w + mask_size
        ] = False
        
        high_freq = magnitude[high_freq_mask]
        
        # Calculate ratio
        hf_mean = high_freq.mean()
        lf_mean = low_freq.mean()
        
        ratio = hf_mean / (lf_mean + 1e-6)
        
        # Normalize (empirical threshold)
        freq_score = min(ratio * 10, 1.0)
        
        return freq_score
    
    def _extract_landmark_coords(self, landmarks, width: int, height: int) -> np.ndarray:
        """
        Extract landmark coordinates as numpy array.
        
        Returns:
            np.ndarray of shape (468, 2)
        """
        coords = []
        for landmark in landmarks.landmark:
            x = landmark.x * width
            y = landmark.y * height
            coords.append([x, y])
        
        return np.array(coords, dtype=np.float64)
    
    def _get_camera_matrix(self, width: int, height: int) -> np.ndarray:
        """
        Get or create camera matrix for given frame size.
        """
        key = (width, height)
        
        if key not in self._camera_matrix_cache:
            focal_length = width
            center = (width / 2, height / 2)
            
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype=np.float64)
            
            self._camera_matrix_cache[key] = camera_matrix
        
        return self._camera_matrix_cache[key]
    
    def _error_result(self, reason: str) -> Dict:
        """Return error result."""
        return {
            'is_real': False,
            'score': 0.0,
            'action': 'error',
            'reason': reason,
            'details': {}
        }
    
    def reset(self):
        """Reset state for new session."""
        self.blink_counter = 0
        self.frame_counter = 0
        self.ear_history.clear()
        logger.debug("🔄 LivenessDetector state reset")
    
    def __del__(self):
        """Cleanup MediaPipe resources."""
        if hasattr(self, 'face_mesh'):
            self.face_mesh.close()
