"""
High-Performance Multi-Threading Video System
=============================================
Architecture:
- Thread 1: Capture frames (bufferless, drop old frames)
- Thread 2: AI Worker (face detection + recognition + liveness)
- Thread 3: UI Display (cv2.imshow or Tkinter)

Optimized for: High FPS, Low latency
"""

import cv2
import numpy as np
import threading
import queue
import time
import logging
from typing import Optional, Dict, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FrameData:
    """Container for frame + metadata"""
    frame: np.ndarray
    frame_id: int
    timestamp: float


@dataclass
class ProcessedResult:
    """Container for AI processing results"""
    frame_id: int
    faces: list  # List of face locations
    encodings: list  # Face encodings
    matches: list  # Recognition results
    liveness: list  # Liveness results
    timestamp: float


class BufferlessVideoCapture:
    """
    Thread 1: Capture frames without buffering.
    Always provides the most recent frame.
    """
    
    def __init__(self, src: int = 0, width: int = 640, height: int = 480, fps: int = 30):
        """
        Initialize video capture.
        
        Args:
            src: Camera index
            width, height: Resolution
            fps: Target FPS
        """
        logger.info(f"🎥 Initializing BufferlessVideoCapture (src={src}, {width}x{height}@{fps}fps)")
        
        self.cap = cv2.VideoCapture(src)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer
        
        if not self.cap.isOpened():
            raise RuntimeError("❌ Cannot open camera")
        
        # Queue with maxsize=1 to drop old frames
        self.frame_queue = queue.Queue(maxsize=1)
        self.stopped = False
        self.frame_counter = 0
        self.thread = None
        
        # FPS tracking
        self.fps = 0.0
        self._fps_start = time.time()
        self._fps_counter = 0
        
        logger.info("✅ BufferlessVideoCapture initialized")
    
    def start(self):
        """Start capture thread."""
        logger.info("▶️  Starting capture thread...")
        self.thread = threading.Thread(target=self._capture_loop, daemon=True, name="CaptureThread")
        self.thread.start()
        return self
    
    def _capture_loop(self):
        """Main capture loop (Thread 1)."""
        logger.info("🎬 Capture thread started")
        
        while not self.stopped:
            ret, frame = self.cap.read()
            
            if not ret:
                logger.error("❌ Failed to read frame")
                self.stop()
                break
            
            self.frame_counter += 1
            
            # Drop old frame if queue is full
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            
            # Put new frame
            frame_data = FrameData(
                frame=frame,
                frame_id=self.frame_counter,
                timestamp=time.time()
            )
            self.frame_queue.put(frame_data)
            
            # Update FPS
            self._fps_counter += 1
            if self._fps_counter >= 30:
                elapsed = time.time() - self._fps_start
                self.fps = self._fps_counter / elapsed
                self._fps_counter = 0
                self._fps_start = time.time()
        
        logger.info("🛑 Capture thread stopped")
    
    def read(self) -> Optional[FrameData]:
        """
        Get latest frame (non-blocking).
        
        Returns:
            FrameData or None
        """
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None
    
    def stop(self):
        """Stop capture thread."""
        logger.info("⏹️  Stopping capture thread...")
        self.stopped = True
        if self.thread:
            self.thread.join(timeout=1.0)
        self.cap.release()
        logger.info("✅ Capture thread stopped")
    
    def get_fps(self) -> float:
        """Get current capture FPS."""
        return self.fps


class AIWorker:
    """
    Thread 2: AI Processing Worker.
    Processes frames from queue with face detection + recognition + liveness.
    """
    
    def __init__(self, 
                 face_detector,
                 face_encoder,
                 face_matcher,
                 liveness_detector,
                 skip_frames: int = 3,
                 max_queue_size: int = 2):
        """
        Initialize AI Worker.
        
        Args:
            face_detector: Face detection module
            face_encoder: Face encoding module
            face_matcher: Face matching module
            liveness_detector: Liveness detection module
            skip_frames: Process every Nth frame
            max_queue_size: Max input queue size
        """
        logger.info("🤖 Initializing AIWorker...")
        
        self.face_detector = face_detector
        self.face_encoder = face_encoder
        self.face_matcher = face_matcher
        self.liveness_detector = liveness_detector
        
        self.skip_frames = skip_frames
        
        # Input/Output queues
        self.input_queue = queue.Queue(maxsize=max_queue_size)
        self.output_queue = queue.Queue(maxsize=5)
        
        self.stopped = False
        self.thread = None
        
        # FPS tracking
        self.processing_fps = 0.0
        self._fps_start = time.time()
        self._fps_counter = 0
        
        logger.info("✅ AIWorker initialized")
    
    def start(self):
        """Start AI worker thread."""
        logger.info("▶️  Starting AI worker thread...")
        self.thread = threading.Thread(target=self._processing_loop, daemon=True, name="AIWorkerThread")
        self.thread.start()
        return self
    
    def _processing_loop(self):
        """Main processing loop (Thread 2)."""
        logger.info("🧠 AI worker thread started")
        
        frame_skip_counter = 0
        
        while not self.stopped:
            try:
                # Get frame from input queue (blocking with timeout)
                frame_data = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            # Skip frames optimization
            frame_skip_counter += 1
            if frame_skip_counter % self.skip_frames != 0:
                continue
            
            # === AI PROCESSING ===
            start_time = time.time()
            
            frame = frame_data.frame
            
            # 1. Face Detection
            face_locations = self.face_detector.detect(frame)
            
            # 2. Face Encoding
            face_encodings = []
            if len(face_locations) > 0:
                face_encodings = self.face_encoder.encode(frame, face_locations)
            
            # 3. Face Matching
            matches = []
            if len(face_encodings) > 0:
                matches = self.face_matcher.match_faces(face_encodings)
            
            # 4. Liveness Detection
            liveness_results = []
            for face_loc in face_locations:
                liveness = self.liveness_detector.analyze(frame, face_loc)
                liveness_results.append(liveness)
            
            # Create result
            result = ProcessedResult(
                frame_id=frame_data.frame_id,
                faces=face_locations,
                encodings=face_encodings,
                matches=matches,
                liveness=liveness_results,
                timestamp=time.time()
            )
            
            # Put result to output queue (drop old if full)
            if self.output_queue.full():
                try:
                    self.output_queue.get_nowait()
                except queue.Empty:
                    pass
            
            self.output_queue.put(result)
            
            # Update FPS
            self._fps_counter += 1
            if self._fps_counter >= 10:
                elapsed = time.time() - self._fps_start
                self.processing_fps = self._fps_counter / elapsed
                self._fps_counter = 0
                self._fps_start = time.time()
            
            # Log processing time
            processing_time = (time.time() - start_time) * 1000
            if processing_time > 100:  # Log if > 100ms
                logger.warning(f"⚠️  Slow processing: {processing_time:.1f}ms")
        
        logger.info("🛑 AI worker thread stopped")
    
    def put_frame(self, frame_data: FrameData):
        """
        Add frame to processing queue.
        
        Args:
            frame_data: FrameData object
        """
        # Drop old frame if queue is full
        if self.input_queue.full():
            try:
                self.input_queue.get_nowait()
            except queue.Empty:
                pass
        
        try:
            self.input_queue.put_nowait(frame_data)
        except queue.Full:
            pass  # Silently drop
    
    def get_result(self) -> Optional[ProcessedResult]:
        """
        Get latest processing result (non-blocking).
        
        Returns:
            ProcessedResult or None
        """
        try:
            return self.output_queue.get_nowait()
        except queue.Empty:
            return None
    
    def stop(self):
        """Stop AI worker thread."""
        logger.info("⏹️  Stopping AI worker thread...")
        self.stopped = True
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("✅ AI worker thread stopped")
    
    def get_fps(self) -> float:
        """Get AI processing FPS."""
        return self.processing_fps


class UIDisplay:
    """
    Thread 3: UI Display (cv2.imshow or Tkinter).
    Displays video feed with overlays.
    """
    
    def __init__(self, window_name: str = "Face Attendance System", display_mode: str = "opencv"):
        """
        Initialize UI Display.
        
        Args:
            window_name: Window title
            display_mode: 'opencv' or 'tkinter'
        """
        logger.info(f"🖥️  Initializing UIDisplay (mode={display_mode})...")
        
        self.window_name = window_name
        self.display_mode = display_mode
        
        # Latest display data
        self.display_frame = None
        self.display_info = {}
        self.lock = threading.Lock()
        
        self.stopped = False
        self.thread = None
        
        # FPS tracking
        self.display_fps = 0.0
        self._fps_start = time.time()
        self._fps_counter = 0
        
        if display_mode == "opencv":
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        logger.info("✅ UIDisplay initialized")
    
    def start(self):
        """Start display thread."""
        logger.info("▶️  Starting display thread...")
        self.thread = threading.Thread(target=self._display_loop, daemon=True, name="UIThread")
        self.thread.start()
        return self
    
    def _display_loop(self):
        """Main display loop (Thread 3)."""
        logger.info("🖼️  Display thread started")
        
        while not self.stopped:
            with self.lock:
                if self.display_frame is not None:
                    frame_to_show = self.display_frame.copy()
                else:
                    frame_to_show = None
            
            if frame_to_show is not None:
                if self.display_mode == "opencv":
                    cv2.imshow(self.window_name, frame_to_show)
                    
                    # Check for 'q' key
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        logger.info("👋 User pressed 'q', stopping...")
                        self.stopped = True
                        break
                
                # Update FPS
                self._fps_counter += 1
                if self._fps_counter >= 30:
                    elapsed = time.time() - self._fps_start
                    self.display_fps = self._fps_counter / elapsed
                    self._fps_counter = 0
                    self._fps_start = time.time()
            else:
                time.sleep(0.01)
        
        if self.display_mode == "opencv":
            cv2.destroyAllWindows()
        
        logger.info("🛑 Display thread stopped")
    
    def update(self, frame: np.ndarray, info: Dict = None):
        """
        Update display with new frame and info.
        
        Args:
            frame: Frame to display
            info: Additional info to overlay
        """
        with self.lock:
            self.display_frame = frame
            if info:
                self.display_info = info
    
    def stop(self):
        """Stop display thread."""
        logger.info("⏹️  Stopping display thread...")
        self.stopped = True
        if self.thread:
            self.thread.join(timeout=1.0)
        logger.info("✅ Display thread stopped")
    
    def get_fps(self) -> float:
        """Get display FPS."""
        return self.display_fps
    
    def is_stopped(self) -> bool:
        """Check if stopped by user."""
        return self.stopped


class ThreadedVideoSystem:
    """
    Main orchestrator for 3-thread video system.
    """
    
    def __init__(self, face_detector, face_encoder, face_matcher, liveness_detector, 
                 camera_src: int = 0, width: int = 640, height: int = 480):
        """
        Initialize complete threaded system.
        """
        logger.info("🚀 Initializing ThreadedVideoSystem...")
        
        # Initialize 3 threads
        self.capture = BufferlessVideoCapture(src=camera_src, width=width, height=height)
        self.ai_worker = AIWorker(
            face_detector=face_detector,
            face_encoder=face_encoder,
            face_matcher=face_matcher,
            liveness_detector=liveness_detector,
            skip_frames=3
        )
        self.ui_display = UIDisplay()
        
        # Cache for rendering
        self.last_result = None
        
        logger.info("✅ ThreadedVideoSystem initialized")
    
    def start(self):
        """Start all threads."""
        logger.info("🎬 Starting all threads...")
        
        self.capture.start()
        time.sleep(0.1)  # Let capture warm up
        
        self.ai_worker.start()
        self.ui_display.start()
        
        logger.info("✅ All threads started successfully")
        return self
    
    def run(self, on_result_callback: Optional[Callable] = None):
        """
        Main orchestration loop.
        
        Args:
            on_result_callback: Callback function(result) when face detected
        """
        logger.info("🔄 Starting main orchestration loop...")
        
        try:
            while not self.ui_display.is_stopped():
                # 1. Get frame from capture
                frame_data = self.capture.read()
                
                if frame_data is not None:
                    # 2. Send to AI worker
                    self.ai_worker.put_frame(frame_data)
                    
                    # 3. Get AI result (if available)
                    result = self.ai_worker.get_result()
                    
                    if result is not None:
                        self.last_result = result
                        
                        # Callback for attendance logic
                        if on_result_callback and len(result.matches) > 0:
                            on_result_callback(result)
                    
                    # 4. Render and update UI
                    display_frame = self._render_frame(frame_data.frame, self.last_result)
                    self.ui_display.update(display_frame)
                
                time.sleep(0.001)  # Small sleep to prevent CPU spinning
        
        except KeyboardInterrupt:
            logger.info("⚠️  KeyboardInterrupt received")
        finally:
            self.stop()
    
    def _render_frame(self, frame: np.ndarray, result: Optional[ProcessedResult]) -> np.ndarray:
        """
        Render frame with bounding boxes and info.
        """
        display_frame = frame.copy()
        
        if result is not None:
            # Draw each face
            for i, face_loc in enumerate(result.faces):
                top, right, bottom, left = face_loc
                
                # Get match info
                match_info = result.matches[i] if i < len(result.matches) else None
                liveness_info = result.liveness[i] if i < len(result.liveness) else None
                
                # Color based on liveness
                if liveness_info and liveness_info.get('is_real', False):
                    color = (0, 255, 0)  # Green
                    status = "LIVE"
                else:
                    color = (0, 0, 255)  # Red
                    status = "FAKE"
                
                # Draw box
                cv2.rectangle(display_frame, (left, top), (right, bottom), color, 2)
                
                # Draw label
                if match_info:
                    person_id, confidence = match_info
                    label = f"{person_id} ({confidence:.2f}) - {status}"
                else:
                    label = f"Unknown - {status}"
                
                cv2.rectangle(display_frame, (left, bottom), (right, bottom + 30), color, -1)
                cv2.putText(display_frame, label, (left + 5, bottom + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Draw FPS
        capture_fps = self.capture.get_fps()
        ai_fps = self.ai_worker.get_fps()
        display_fps = self.ui_display.get_fps()
        
        cv2.putText(display_frame, f"Capture: {capture_fps:.1f} FPS", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(display_frame, f"AI: {ai_fps:.1f} FPS", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(display_frame, f"Display: {display_fps:.1f} FPS", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return display_frame
    
    def stop(self):
        """Stop all threads."""
        logger.info("🛑 Stopping all threads...")
        
        self.ui_display.stop()
        self.ai_worker.stop()
        self.capture.stop()
        
        logger.info("✅ All threads stopped successfully")
