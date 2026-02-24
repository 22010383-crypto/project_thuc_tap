"""
Real-time Face Recognition Engine - Zero-lag Architecture
"""
import cv2
import numpy as np
import face_recognition
from threading import Thread, Lock
from collections import deque
import time
import logging

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False
    print("⚠️ MediaPipe not found. Blink detection disabled. Using texture-only mode.")

logger = logging.getLogger(__name__)


class SharedFrameBuffer:
    """Lock-free double buffering"""
    def __init__(self):
        self.buffers = [None, None]
        self.write_idx = 0
        self.read_idx = 1
        self.lock = Lock()
    
    def write(self, frame):
        with self.lock:
            self.buffers[self.write_idx] = frame.copy()
            self.write_idx, self.read_idx = self.read_idx, self.write_idx
    
    def read(self):
        return self.buffers[self.read_idx]


class FastTextureAnalyzer:
    """Texture analysis: real skin has high local variance, screen/photo is smoother"""
    
    @staticmethod
    def analyze(face_gray):
        h, w = face_gray.shape
        if h < 32 or w < 32:
            return 0.0
        
        small = cv2.resize(face_gray, (64, 64))
        
        # Sobel gradient magnitude
        grad_x = cv2.Sobel(small, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(small, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(grad_x**2 + grad_y**2)
        
        # Real face: std(grad) high. Screen/photo: low.
        local_std = grad_mag.std()
        texture_score = min(local_std / 45.0, 1.0)
        
        # Per-block variance (real face has non-uniform texture)
        block_size = 16
        blocks = []
        for i in range(0, 64 - block_size + 1, block_size):
            for j in range(0, 64 - block_size + 1, block_size):
                block = small[i:i+block_size, j:j+block_size]
                blocks.append(block.var())
        block_var_std = np.std(blocks) if blocks else 0
        block_score = min(block_var_std / 400.0, 1.0)
        
        return texture_score * 0.65 + block_score * 0.35


class FastFrequencyAnalyzer:
    """Fast DCT-based frequency analysis"""
    
    @staticmethod
    def analyze(face_gray):
        h, w = face_gray.shape
        if h < 32 or w < 32:
            return 0.5
        
        small = cv2.resize(face_gray, (64, 64)).astype(np.float32)
        dct = cv2.dct(small)
        mid_h, mid_w = 32, 32
        low = np.abs(dct[:mid_h, :mid_w]).sum()
        high = np.abs(dct[mid_h:, mid_w:]).sum()
        ratio = high / (low + 1e-6)
        
        return min(ratio * 20.0, 1.0)


class RealtimeAntiSpoof:
    """Combined fast anti-spoofing with blink & head movement"""
    
    # MediaPipe landmarks
    LEFT_EYE = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE = [362, 385, 387, 263, 373, 380]
    
    def __init__(self):
        self.texture_analyzer = FastTextureAnalyzer()
        self.freq_analyzer = FastFrequencyAnalyzer()
        self.has_mediapipe = HAS_MEDIAPIPE
        
        # MediaPipe Face Mesh (if available)
        if self.has_mediapipe:
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        else:
            self.face_mesh = None
        
        # Tracking state per person
        self.person_states = {}
        self.cache = {}
        self.cache_timeout = 1.5
    
    def _calculate_ear(self, landmarks, eye_indices):
        """Calculate Eye Aspect Ratio"""
        points = [landmarks[i] for i in eye_indices]
        
        # Vertical distances
        v1 = np.linalg.norm(np.array([points[1].x - points[5].x, points[1].y - points[5].y]))
        v2 = np.linalg.norm(np.array([points[2].x - points[4].x, points[2].y - points[4].y]))
        
        # Horizontal distance
        h = np.linalg.norm(np.array([points[0].x - points[3].x, points[0].y - points[3].y]))
        
        ear = (v1 + v2) / (2.0 * h + 1e-6)
        return ear
    
    def _init_person_state(self, person_id):
        """Initialize tracking state for a person"""
        return {
            'ear_history': deque(maxlen=10),
            'blink_count': 0,
            'last_blink': 0,
            'head_positions': deque(maxlen=5),
            'movement_detected': False,
            'frames_checked': 0
        }
    
    def check(self, face_bgr, face_id=None, full_frame=None):
        """
        Check if face is real using:
        1. Blink detection (EAR) - if MediaPipe available
        2. Head movement - if MediaPipe available
        3. Texture analysis (primary when no MediaPipe)
        """
        # Fallback to texture-only if no MediaPipe
        if not self.has_mediapipe or self.face_mesh is None:
            return self._check_texture_only(face_bgr)
        
        # IMPORTANT: Each face_id has independent state
        if not face_id:
            # No ID - use temporary state
            state = self._init_person_state(None)
        else:
            # Get or create state for this person
            if face_id not in self.person_states:
                self.person_states[face_id] = self._init_person_state(face_id)
                logger.info(f"🆕 New tracking state for {face_id}")
            state = self.person_states[face_id]
        
        state['frames_checked'] += 1
        
        # Convert to RGB for MediaPipe
        rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)
        
        blink_detected = False
        movement_detected = False
        
        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            
            # 1. BLINK DETECTION
            left_ear = self._calculate_ear(landmarks, self.LEFT_EYE)
            right_ear = self._calculate_ear(landmarks, self.RIGHT_EYE)
            avg_ear = (left_ear + right_ear) / 2.0
            
            state['ear_history'].append(avg_ear)
            
            # Blink: EAR xuống thấp rồi lên (ngưỡng vừa để dễ detect)
            recent = list(state['ear_history'])[-6:]
            if len(recent) >= 3:
                # Đóng: EAR < 0.25; trước đó mở: > 0.27
                if avg_ear < 0.25 and max(recent[:-1]) > 0.27:
                    current_time = time.time()
                    if current_time - state['last_blink'] > 0.35:
                        state['blink_count'] += 1
                        state['last_blink'] = current_time
                        logger.info(f"BLINK {face_id} count={state['blink_count']}")
            
            # Cử động đầu: chấp nhận thay blink (ngưỡng vừa)
            nose_tip = landmarks[1]
            nose_pos = (nose_tip.x, nose_tip.y)
            state['head_positions'].append(nose_pos)
            if len(state['head_positions']) >= 3:
                positions = list(state['head_positions'])
                movement = max(
                    np.linalg.norm(np.array(positions[i]) - np.array(positions[i-1]))
                    for i in range(1, len(positions))
                )
                if movement > 0.04:
                    state['movement_detected'] = True
        
        # Texture + blur
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = min(lap_var / 100.0, 1.0)
        texture_score = self.texture_analyzer.analyze(gray)
        
        # Nghi màn hình: chỉ khi sáng chói rất nhiều hoặc quá đều
        hsv = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2]
        bright_ratio = np.sum(v > 245) / (v.size + 1e-6)
        uniform_ratio = np.std(v) / (np.mean(v) + 1e-6)
        screen_like = bright_ratio > 0.15 or uniform_ratio < 0.10
        if screen_like:
            texture_score = min(texture_score, 0.38)
        
        # Chấp nhận: 1 lần chớp HOẶC cử động đầu + texture/blur ổn
        has_action = state['blink_count'] >= 1 or state['movement_detected']
        texture_ok = texture_score >= 0.42
        blur_ok = blur_score >= 0.28
        
        is_real = has_action and texture_ok and blur_ok and (not screen_like)
        if not has_action:
            reason = f'Chớp mắt hoặc quay đầu (blink={state["blink_count"]})'
        elif screen_like:
            reason = 'Nghi ảnh màn hình'
        elif not texture_ok:
            reason = f'Texture ({texture_score:.2f})'
        elif not blur_ok:
            reason = f'Mờ ({blur_score:.2f})'
        else:
            reason = 'OK'
        
        final_score = 0.0
        if has_action:
            final_score += 0.5
        if texture_ok:
            final_score += 0.3
        if blur_ok:
            final_score += 0.2
        
        result = {
            'is_real': is_real,
            'score': float(final_score),
            'blur': float(blur_score),
            'texture': float(texture_score),
            'blink_count': state['blink_count'],
            'movement': state['movement_detected'],
            'reason': reason
        }
        
        status = "✓ REAL" if is_real else "✗ FAKE"
        logger.debug(f"{status} {face_id} | Frame={state['frames_checked']} Blinks={state['blink_count']} Move={state['movement_detected']} Tex={texture_score:.2f} Blur={blur_score:.2f} | {reason}")
        
        return result
    
    def _check_texture_only(self, face_bgr):
        """Khi không có MediaPipe: chỉ texture + blur, ngưỡng rất chặt (ảnh màn hình thường fail)"""
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = min(lap_var / 100.0, 1.0)
        texture_score = self.texture_analyzer.analyze(gray)
        
        # Phát hiện màn hình (sáng chói / quá đều)
        hsv = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2]
        bright_ratio = np.sum(v > 240) / (v.size + 1e-6)
        uniform_ratio = np.std(v) / (np.mean(v) + 1e-6)
        screen_like = bright_ratio > 0.08 or uniform_ratio < 0.15
        if screen_like:
            texture_score = min(texture_score, 0.35)
        
        is_real = (not screen_like) and texture_score >= 0.48 and blur_score >= 0.35
        
        final_score = texture_score * 0.6 + blur_score * 0.3
        return {
            'is_real': is_real,
            'score': float(final_score),
            'blur': float(blur_score),
            'texture': float(texture_score),
            'freq': 0.0,
            'blink_count': 0,
            'movement': False,
            'reason': 'Texture-only' if is_real else f'T={texture_score:.2f} B={blur_score:.2f}' + (' | Screen?' if screen_like else '')
        }


class RealtimeRecognitionEngine:
    """Main recognition engine - optimized for speed"""
    
    def __init__(self, known_encodings, known_ids, use_antispoof=True):
        self.known_encodings = np.array(known_encodings) if len(known_encodings) > 0 else np.array([])
        self.known_ids = list(known_ids)
        self.use_antispoof = use_antispoof
        
        if use_antispoof:
            self.antispoof = RealtimeAntiSpoof()
        
        self.tolerance = 0.45
        self.frame_counter = 0
        self.skip_frames = 2
        self.last_results = []
        
        logger.info(f"Engine initialized: {len(self.known_ids)} faces, antispoof={use_antispoof}")
    
    def process_frame(self, frame, already_checked_in=None):
        """
        Main processing. already_checked_in: set of person_id đã điểm danh → skip antispoof, chỉ hiển thị OK.
        """
        self.frame_counter += 1
        
        if self.frame_counter % self.skip_frames != 0:
            return self.last_results
        
        if len(self.known_encodings) == 0:
            return []
        
        already_checked_in = already_checked_in or set()
        
        small_frame = cv2.resize(frame, (0, 0), fx=0.4, fy=0.4)
        rgb_small = np.ascontiguousarray(small_frame[:, :, ::-1])
        
        face_locations = face_recognition.face_locations(rgb_small, model='hog')
        
        if not face_locations:
            self.last_results = []
            return []
        
        face_encodings = face_recognition.face_encodings(rgb_small, face_locations, num_jitters=1)
        
        results = []
        scale = 2.5
        
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            top, right, bottom, left = int(top*scale), int(right*scale), int(bottom*scale), int(left*scale)
            
            person_id = None
            confidence = 0.0
            
            if len(self.known_encodings) > 0:
                matches = face_recognition.compare_faces(self.known_encodings, face_encoding, tolerance=self.tolerance)
                face_distances = face_recognition.face_distance(self.known_encodings, face_encoding)
                
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        person_id = self.known_ids[best_match_index]
                        confidence = 1.0 - face_distances[best_match_index]
            
            # Đã điểm danh trong phiên → không chạy antispoof, chỉ hiển thị "Đã điểm danh"
            if person_id and str(person_id) in already_checked_in:
                antispoof_result = {
                    'is_real': True, 'score': 1.0, 'blink_count': 0, 'movement': True,
                    'reason': 'Checked', 'blur': 1.0, 'texture': 1.0
                }
            elif self.use_antispoof and person_id:
                face_roi = frame[top:bottom, left:right]
                if face_roi.size > 0:
                    antispoof_result = self.antispoof.check(face_roi, str(person_id), frame)
                else:
                    antispoof_result = {'is_real': False, 'score': 0.0, 'blink_count': 0, 'movement': False, 'reason': 'No ROI', 'blur': 0.0, 'texture': 0.0}
            else:
                antispoof_result = {'is_real': True, 'score': 1.0, 'blink_count': 0, 'movement': False, 'reason': 'OK', 'blur': 1.0, 'texture': 1.0}
            
            results.append({
                'box': (top, right, bottom, left),
                'id': person_id,
                'confidence': confidence,
                'antispoof': antispoof_result
            })
        
        self.last_results = results
        return results


class SmoothRenderer:
    """Smooth rendering with interpolation"""
    
    def __init__(self):
        self.last_boxes = {}
        self.smooth_factor = 0.6
    
    def smooth_box(self, person_id, new_box):
        if person_id not in self.last_boxes:
            self.last_boxes[person_id] = new_box
            return new_box
        
        old_box = self.last_boxes[person_id]
        smooth_box = tuple(
            int(old * self.smooth_factor + new * (1 - self.smooth_factor))
            for old, new in zip(old_box, new_box)
        )
        
        self.last_boxes[person_id] = smooth_box
        return smooth_box
    
    def render(self, frame, results, checked_in_ids=None):
        checked_in_ids = checked_in_ids or set()
        for result in results:
            box = result['box']
            person_id = result['id']
            antispoof = result['antispoof']
            
            if person_id:
                box = self.smooth_box(person_id, box)
                pid_str = str(person_id)
                # Xanh: đã điểm danh thành công. Đỏ: chưa nhận diện / không phải người thật
                if pid_str in checked_in_ids:
                    color = (0, 255, 0)  # Xanh lá
                elif antispoof['is_real']:
                    color = (0, 255, 0)  # Xanh lá (đạt liveness, chưa check-in)
                else:
                    color = (0, 0, 255)  # Đỏ (fake / chưa đạt)
            else:
                color = (0, 0, 255)  # Đỏ (không nhận diện)
            
            top, right, bottom, left = box
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        
        return frame


class OptimizedAttendanceSystem:
    """Complete optimized system"""
    
    def __init__(self, known_encodings, known_ids, db_manager, session_id):
        self.engine = RealtimeRecognitionEngine(known_encodings, known_ids, use_antispoof=True)
        self.renderer = SmoothRenderer()
        self.db = db_manager
        self.session_id = session_id
        
        # Track checked-in students (permanent in session)
        self.checked_in = set()
        self.cooldown = {}
        self.cooldown_seconds = 3.0
        
        # Count for UI
        self.check_in_count = 0
        self.count_lock = Lock()
        
        self.frame_buffer = SharedFrameBuffer()
        self.running = False
        self.process_thread = None
        self.latest_results = []
        self.results_lock = Lock()
        
        logger.info(f"OptimizedAttendanceSystem initialized | Session={session_id}")
    
    def start(self):
        self.running = True
        self.process_thread = Thread(target=self._process_loop, daemon=True)
        self.process_thread.start()
        logger.info("Background processing started")
    
    def stop(self):
        self.running = False
        if self.process_thread:
            self.process_thread.join(timeout=1.0)
        logger.info("Background processing stopped")
    
    def _process_loop(self):
        while self.running:
            frame = self.frame_buffer.read()
            
            if frame is None:
                time.sleep(0.001)
                continue
            
            # Truyền checked_in để engine skip antispoof với người đã điểm danh
            checked_in_set = {str(pid) for pid in self.checked_in}
            results = self.engine.process_frame(frame, already_checked_in=checked_in_set)
            
            for result in results:
                person_id = result['id']
                
                if not person_id:
                    continue
                
                person_id_str = str(person_id)
                
                # Đã điểm danh trong phiên → bỏ qua, không ghi DB lại
                if person_id_str in self.checked_in:
                    continue
                
                antispoof = result['antispoof']
                confidence = result['confidence']
                
                # Anti-spoofing check (STRICT)
                if not antispoof['is_real']:
                    logger.warning(f"🚫 {person_id} REJECTED | {antispoof['reason']} | Blinks={antispoof.get('blink_count', 0)}")
                    continue
                
                # Cooldown check (prevent spam)
                now = time.time()
                if person_id in self.cooldown:
                    if now - self.cooldown[person_id] < self.cooldown_seconds:
                        continue
                
                # Ghi DB ngay khi pass antispoof
                try:
                    success, msg = self.db.mark_attendance(
                        self.session_id,
                        person_id_str,
                        method='Realtime',
                        confidence_score=float(confidence),
                        liveness_score=float(antispoof['score']),
                        liveness_details={
                            'blur': antispoof.get('blur', 0),
                            'texture': antispoof.get('texture', 0),
                            'blink_count': antispoof.get('blink_count', 0),
                            'movement': antispoof.get('movement', False),
                            'reason': antispoof.get('reason', '')
                        }
                    )
                    
                    if success:
                        self.checked_in.add(person_id_str)
                        self.cooldown[person_id_str] = now
                        with self.count_lock:
                            self.check_in_count += 1
                        logger.info(f"✅ {person_id_str} CHECKED IN | Live={antispoof['score']:.2f} | Total={self.check_in_count}")
                    else:
                        logger.warning(f"⚠️ {person_id_str} | {msg}")
                except Exception as e:
                    logger.error(f"❌ DB {person_id_str}: {e}")
                    import traceback
                    traceback.print_exc()
            
            with self.results_lock:
                self.latest_results = results
            
            time.sleep(0.001)
    
    def put_frame(self, frame):
        self.frame_buffer.write(frame)
    
    def get_display_frame(self, frame):
        with self.results_lock:
            results = self.latest_results
        checked_in_set = {str(pid) for pid in self.checked_in}
        return self.renderer.render(frame, results, checked_in_ids=checked_in_set)
    
    def get_count(self):
        with self.count_lock:
            return self.check_in_count
