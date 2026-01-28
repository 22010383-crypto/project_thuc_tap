import tkinter as tk
from tkinter import messagebox
import cv2
import threading
import queue
import time
from datetime import datetime, timedelta
from app.config import Config
from database.db_manager import DatabaseManager
from core.face_detector import FaceDetector
from core.face_encoder import FaceEncoder
from core.face_matcher import FaceMatcher
from utils.video_stream import VideoStream
from utils.image_utils import cv2_to_pil
import logging

# Lấy logger từ root logger đã setup
logger = logging.getLogger(__name__)
logger.info("📦 Module attendance_window imported")

# --- POPUP CẤU HÌNH ---
class AttendanceConfigDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Cấu hình Điểm Danh")
        self.geometry("400x250")
        self.result = None
        self.transient(parent)
        self.grab_set()
        
        tk.Label(self, text="THIẾT LẬP PHIÊN ĐIỂM DANH", font=("Arial", 14, "bold"), fg="#2980b9").pack(pady=20)
        
        f = tk.Frame(self); f.pack(pady=5)
        tk.Label(f, text="Thời gian (phút):").pack(side=tk.LEFT)
        self.e_min = tk.Entry(f, width=10); self.e_min.insert(0, "45"); self.e_min.pack(side=tk.LEFT, padx=5)
        
        # Checkbox Liveness
        self.live_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Yêu cầu Chớp mắt / Quay đầu (Anti-Spoofing)", 
                       var=self.live_var, fg="#c0392b", font=("Arial", 10, "bold")).pack(pady=15)
        
        tk.Button(self, text="BẮT ĐẦU", command=self.submit, bg="green", fg="white", width=15).pack(pady=10)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def submit(self):
        try:
            self.result = {"duration": int(self.e_min.get()), "liveness": self.live_var.get()}
            logger.info(f"✅ Cấu hình điểm danh: {self.result}")
            self.destroy()
        except:
            messagebox.showerror("Lỗi", "Nhập sai số phút")
            
    def on_cancel(self):
        logger.info("❌ Hủy cấu hình")
        self.destroy()

# --- MÀN HÌNH CHÍNH ---
class AttendanceWindow(tk.Toplevel):
    def __init__(self, parent, on_close):
        super().__init__(parent)
        self.on_close_callback = on_close
        self.geometry("1280x800")
        self.title("Khởi tạo hệ thống...")
        
        self.is_running = False
        
        # CRITICAL: Tách riêng frame hiển thị và frame xử lý
        self.display_frame = None  # Frame để hiển thị (cập nhật NGAY)
        self.process_frame = None  # Frame để AI xử lý (có thể chậm)
        
        # Dữ liệu phiên
        self.checked_in_session = set()
        self.trackers = {}
        
        # Queue cho kết quả AI (nhẹ hơn nhiều)
        self.result_queue = queue.Queue(maxsize=10)  # Tăng size để đảm bảo không mất data
        self.detected_objects = []
        self.current_count = 0
        
        # Lock để đồng bộ count
        import threading
        self._count_lock = threading.Lock()
        
        logger.debug(f"📊 Initial count: {self.current_count}")
        
        # Session ID
        self.session_id = None
        
        self.db = DatabaseManager()
        self.create_ui()
        
        logger.info("🚀 AttendanceWindow khởi tạo")
        
        # Khởi động an toàn
        self.after(200, self.start_sequence)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_ui(self):
        main = tk.Frame(self, bg="black")
        main.pack(fill=tk.BOTH, expand=True)
        
        self.cam_label = tk.Label(main, bg="black", text="Đang tải...", fg="white")
        self.cam_label.pack(fill=tk.BOTH, expand=True)
        
        self.info_panel = tk.Label(main, text="", bg="black", fg="#00ff00", font=("Consolas", 14))
        self.info_panel.place(x=20, y=20)
        
        self.status_bar = tk.Label(main, text="Chờ cấu hình...", bg="#333", fg="white", anchor="w")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def start_sequence(self):
        logger.info("⚙️ Bắt đầu cấu hình điểm danh...")
        
        dlg = AttendanceConfigDialog(self)
        self.wait_window(dlg)
        
        if not dlg.result:
            logger.warning("⚠️ Không có cấu hình, đóng cửa sổ")
            self.on_close()
            return
        
        self.duration = dlg.result['duration'] * 60
        self.use_liveness = dlg.result['liveness']
        self.end_time = datetime.now() + timedelta(seconds=self.duration)
        
        mode = "YÊU CẦU HÀNH ĐỘNG" if self.use_liveness else "QUÉT NHANH"
        self.title(f"Điểm Danh - {mode}")
        
        # Tạo session trong DB
        self.session_id = self.db.create_session(f"Attendance - {mode}")
        logger.info(f"📋 Session ID: {self.session_id}, Chế độ: {mode}, Thời lượng: {self.duration}s")
        
        try:
            logger.info("📷 Khởi động camera...")
            self.video = VideoStream(Config.CAMERA_INDEX).start()
            time.sleep(1.0)  # Đợi camera ổn định
            
            self.is_running = True
            logger.info("✅ Camera sẵn sàng, bắt đầu AI worker...")
            
            # Khởi động 2 thread riêng biệt
            threading.Thread(target=self.ai_worker, daemon=True, name="AI-Worker").start()
            
            self.update_display_loop()
        except Exception as e:
            logger.error(f"❌ Lỗi khởi động: {e}")
            messagebox.showerror("Lỗi", str(e))
            self.on_close()

    def ai_worker(self):
        """Thread AI - Chạy KHÔNG ĐỒNG BỘ với display"""
        logger.info("🤖 AI Worker thread started")
        
        try:
            logger.info("📦 Đang load models...")
            detector = FaceDetector()
            encoder = FaceEncoder()
            matcher = FaceMatcher(encoder)
            liveness = ActionLivenessDetector()
            logger.info("✅ Tất cả models đã load xong")
        except Exception as e:
            logger.error(f"❌ Model Error: {e}")
            return

        scale = Config.RESIZE_SCALE
        frame_count = 0
        last_process_time = time.time()
        
        # FPS tracking
        fps_start_time = time.time()
        fps_frame_count = 0
        
        logger.info(f"🔄 AI Worker: scale={scale}, liveness={self.use_liveness}")
        
        while self.is_running:
            # Lấy frame mới NHẤT (bỏ qua các frame cũ nếu xử lý chậm)
            frame_orig = self.process_frame
            if frame_orig is None:
                time.sleep(0.01)
                continue
            
            # THROTTLE: Chỉ xử lý AI mỗi 100ms (10 FPS AI, nhưng 30 FPS display)
            now = time.time()
            if now - last_process_time < 0.1:
                time.sleep(0.01)
                continue
            
            last_process_time = now
            frame_count += 1
            fps_frame_count += 1
            
            # Log FPS mỗi 30 frames
            if fps_frame_count >= 30:
                elapsed = time.time() - fps_start_time
                fps = fps_frame_count / elapsed
                logger.info(f"🤖 AI FPS: {fps:.1f} | Tracked: {len(self.trackers)} | Queue: {self.result_queue.qsize()}")
                fps_start_time = time.time()
                fps_frame_count = 0
            
            # Resize để detect nhanh
            try:
                frame_small = cv2.resize(frame_orig, (0, 0), fx=scale, fy=scale)
            except:
                continue
            
            draw_data = []
            
            # 1. Detect Face
            locs_small = detector.detect(frame_small)
            
            current_ids = set()
            
            if locs_small:
                # Encode batch
                encs = encoder.encode(frame_small, locs_small)
                
                for (ts, rs, bs, ls), enc in zip(locs_small, encs):
                    # Mapping về ảnh gốc
                    t, r, b, l = int(ts/scale), int(rs/scale), int(bs/scale), int(ls/scale)
                    rect = (t, r, b, l)
                    
                    # 2. Identify
                    uid, confidence = matcher.find_match(enc)
                    
                    color = (0, 255, 255)  # VÀNG
                    
                    if uid:
                        current_ids.add(uid)
                        
                        # CASE A: Đã điểm danh
                        if uid in self.checked_in_session:
                            color = (0, 255, 0)
                        
                        # CASE B: Chưa điểm danh
                        else:
                            if not self.use_liveness:
                                # Nhanh
                                self._do_checkin(uid)
                                color = (0, 255, 0)
                            else:
                                # Liveness
                                if uid not in self.trackers:
                                    self.trackers[uid] = {
                                        'consec_close': 0,
                                        'has_blinked': False,
                                        'has_turned': False,
                                        'last_check': 0
                                    }
                                
                                tracker = self.trackers[uid]
                                
                                # Throttle liveness check (mỗi 200ms)
                                if now - tracker['last_check'] > 0.2:
                                    tracker['last_check'] = now
                                    
                                    action_data = liveness.analyze_action(frame_orig, rect)
                                    
                                    if action_data['valid']:
                                        ear = action_data['ear']
                                        yaw = action_data['yaw']
                                        
                                        # Check Blink
                                        if ear < Config.EYE_AR_THRESH:
                                            tracker['consec_close'] += 1
                                        else:
                                            if tracker['consec_close'] >= Config.EYE_AR_CONSEC_FRAMES:
                                                logger.info(f"✅ {uid} CHỚP MẮT!")
                                                tracker['has_blinked'] = True
                                            tracker['consec_close'] = 0
                                        
                                        # Check Head Turn
                                        if abs(yaw) > Config.YAW_THRESH:
                                            logger.info(f"✅ {uid} QUAY ĐẦU ({yaw:.1f}°)!")
                                            tracker['has_turned'] = True
                                        
                                        # Điểm danh
                                        if tracker['has_blinked'] or tracker['has_turned']:
                                            logger.info(f"🎉 {uid} ĐẠT YÊU CẦU!")
                                            self._do_checkin(uid)
                                            color = (0, 255, 0)
                                            del self.trackers[uid]
                                        else:
                                            color = (0, 255, 255)
                                    else:
                                        color = (0, 0, 255)
                    else:
                        color = (0, 0, 255)
                    
                    draw_data.append({"rect": rect, "color": color})
            
            # Cleanup trackers (mỗi 20 frames)
            if frame_count % 20 == 0:
                for k in list(self.trackers.keys()):
                    if k not in current_ids:
                        del self.trackers[k]
            
            # Gửi kết quả (non-blocking)
            try:
                self.result_queue.put_nowait(("DRAW", draw_data))
            except queue.Full:
                # Queue đầy, bỏ qua kết quả cũ
                try:
                    self.result_queue.get_nowait()
                    self.result_queue.put_nowait(("DRAW", draw_data))
                except:
                    pass
        
        logger.info("🛑 AI Worker stopped")
    
    def _do_checkin(self, uid):
        """Ghi nhận điểm danh (chạy trong AI thread)"""
        try:
            if self.db.mark_attendance(self.session_id, uid, "ActionVerified"):
                self.checked_in_session.add(uid)
                
                # Thread-safe update count
                with self._count_lock:
                    count = len(self.checked_in_session)
                    self.current_count = count  # Cập nhật trực tiếp
                
                logger.info(f"✅ {uid} điểm danh OK! Tổng: {count}")
                
                # CẬP NHẬT UI COUNT - ƯU TIÊN CAO
                # Thử gửi nhiều lần để đảm bảo UI nhận được
                for attempt in range(3):
                    try:
                        self.result_queue.put_nowait(("COUNT", count))
                        logger.debug(f"✅ Count sent to UI: {count} (attempt {attempt+1})")
                        break
                    except queue.Full:
                        # Xóa item cũ và thử lại
                        try:
                            self.result_queue.get_nowait()
                        except:
                            pass
                        time.sleep(0.01)
                
        except Exception as e:
            logger.error(f"❌ Lỗi điểm danh {uid}: {e}", exc_info=True)

    def update_display_loop(self):
        """Thread chính - Chỉ lo HIỂN THỊ (60 FPS)"""
        if not self.is_running:
            return
        
        # XỬ LÝ KẾT QUẢ TỪ AI (CRITICAL - Đọc TRƯỚC)
        # Đảm bảo xử lý HẾT queue để cập nhật count ngay
        processed_count = 0
        old_count = self.current_count
        
        try:
            while processed_count < 10:  # Tối đa 10 items/frame
                t, d = self.result_queue.get_nowait()
                if t == "DRAW":
                    self.detected_objects = d
                elif t == "COUNT":
                    with self._count_lock:
                        self.current_count = d
                    logger.info(f"📊 UI received count update: {old_count} → {d}")
                processed_count += 1
        except queue.Empty:
            pass
        
        # Timer
        rem = self.end_time - datetime.now()
        if rem.total_seconds() <= 0:
            logger.info("⏰ Hết giờ")
            self.on_close()
            return
            
        m, s = divmod(int(rem.total_seconds()), 60)
        
        # CẬP NHẬT INFO PANEL (với count mới nhất)
        self.info_panel.config(text=f"Sĩ số: {self.current_count} | Còn lại: {m:02d}:{s:02d}")
        
        # ĐỌC FRAME TỪ CAMERA (REAL-TIME)
        frame = self.video.read()
        if frame is not None:
            # Lưu để AI xử lý
            self.process_frame = frame.copy()
            
            # Lưu để hiển thị
            self.display_frame = frame
        
        # VẼ VÀ HIỂN THỊ (frame mới nhất)
        if self.display_frame is not None:
            disp = self.display_frame.copy()
            
            # Vẽ bounding boxes
            for o in self.detected_objects:
                t, r, b, l = o["rect"]
                cv2.rectangle(disp, (l, t), (r, b), o["color"], 3)
            
            # Hiển thị
            self.photo = cv2_to_pil(disp, width=1280, height=720)
            self.cam_label.config(image=self.photo)
        
        # Loop với 60 FPS
        self.after(16, self.update_display_loop)

    def on_close(self):
        logger.info("🚪 Đóng cửa sổ")
        self.is_running = False
        
        if self.session_id:
            self.db.close_session(self.session_id)
        
        if self.video:
            self.video.stop()
        
        self.destroy()
        self.on_close_callback()