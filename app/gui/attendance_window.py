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
from core.liveness_detector import ActionLivenessDetector
from utils.video_stream import VideoStream
from utils.image_utils import cv2_to_pil
import logging
import numpy as np

logger = logging.getLogger(__name__)

# --- POPUP CẤU HÌNH ---
class AttendanceConfigDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Cấu hình")
        self.geometry("400x250")
        self.result = None
        self.transient(parent)
        self.grab_set()
        
        tk.Label(self, text="THIẾT LẬP PHIÊN", font=("Arial", 14, "bold"), fg="#2980b9").pack(pady=20)
        
        f = tk.Frame(self); f.pack(pady=5)
        tk.Label(f, text="Thời gian (phút):").pack(side=tk.LEFT)
        self.e_min = tk.Entry(f, width=10); self.e_min.insert(0, "45"); self.e_min.pack(side=tk.LEFT, padx=5)
        
        self.live_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Yêu cầu Liveness (Chống giả mạo)", 
                       var=self.live_var, fg="#c0392b", font=("Arial", 10, "bold")).pack(pady=15)
        
        tk.Button(self, text="BẮT ĐẦU", command=self.submit, bg="green", fg="white", width=15).pack(pady=10)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def submit(self):
        try:
            self.result = {"duration": int(self.e_min.get()), "liveness": self.live_var.get()}
            self.destroy()
        except: messagebox.showerror("Lỗi", "Số phút sai")
    def on_cancel(self): self.destroy()

# --- MÀN HÌNH CHÍNH ---
class AttendanceWindow(tk.Toplevel):
    def __init__(self, parent, on_close):
        super().__init__(parent)
        self.on_close_callback = on_close
        self.geometry("1280x800")
        self.title("Loading...")
        
        self.is_running = False
        self.session_id = None
        
        # Frame buffers
        self.display_frame = None
        self.process_frame = None
        
        # Data
        self.checked_in_session = set()
        self.trackers = {}
        self.result_queue = queue.Queue(maxsize=10)
        self.detected_objects = []
        self.current_count = 0
        self._count_lock = threading.Lock()
        
        self.db = DatabaseManager()
        self.create_ui()
        
        self.after(200, self.start_sequence)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_ui(self):
        main = tk.Frame(self, bg="black"); main.pack(fill=tk.BOTH, expand=True)
        self.cam_label = tk.Label(main, bg="black", text="Đang tải...", fg="white")
        self.cam_label.pack(fill=tk.BOTH, expand=True)
        self.info_panel = tk.Label(main, text="", bg="black", fg="#0F0", font=("Consolas", 14))
        self.info_panel.place(x=20, y=20)
        self.status_bar = tk.Label(main, text="Chờ cấu hình...", bg="#333", fg="white", anchor="w")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def start_sequence(self):
        dlg = AttendanceConfigDialog(self); self.wait_window(dlg)
        if not dlg.result: self.on_close(); return
        
        self.duration = dlg.result['duration'] * 60
        self.use_liveness = dlg.result['liveness']
        self.end_time = datetime.now() + timedelta(seconds=self.duration)
        mode = "LIVENESS" if self.use_liveness else "FAST"
        self.title(f"Điểm Danh - {mode}")
        
        self.session_id = self.db.create_session(f"Auto - {mode}")
        
        try:
            self.video = VideoStream(Config.CAMERA_INDEX).start()
            time.sleep(1.0) # Đợi cam ấm máy
            self.is_running = True
            
            # Start AI Thread
            threading.Thread(target=self.ai_worker, daemon=True, name="AI-Worker").start()
            # Start UI Loop
            self.update_display_loop()
        except Exception as e:
            messagebox.showerror("Lỗi", str(e)); self.on_close()

    def ai_worker(self):
        try:
            det = FaceDetector(); enc = FaceEncoder()
            mat = FaceMatcher(enc); live = ActionLivenessDetector()
        except: return

        scale = Config.RESIZE_SCALE
        last_proc = time.time()
        
        while self.is_running:
            # Throttle: Max 10 FPS cho AI để tiết kiệm CPU
            if time.time() - last_proc < 0.1: 
                time.sleep(0.01); continue
            last_proc = time.time()
            
            frame_orig = self.process_frame
            if frame_orig is None: continue
            
            # Resize
            try:
                h, w = frame_orig.shape[:2]
                frame_small = cv2.resize(frame_orig, (int(w*scale), int(h*scale)))
                # FIX MAC OS:
                frame_small = np.ascontiguousarray(frame_small)
            except: continue
            
            draw = []
            locs = det.detect(frame_small)
            curr_ids = set()
            
            if locs:
                vecs = enc.encode(frame_small, locs)
                for (ts, rs, bs, ls), vec in zip(locs, vecs):
                    t,r,b,l = int(ts/scale), int(rs/scale), int(bs/scale), int(ls/scale)
                    rect = (t,r,b,l)
                    uid, _ = mat.find_match(vec)
                    
                    color = (0, 255, 255) # Vàng
                    
                    if uid:
                        curr_ids.add(uid)
                        if uid in self.checked_in_session:
                            color = (0, 255, 0)
                        else:
                            if not self.use_liveness:
                                self._do_checkin(uid); color = (0, 255, 0)
                            else:
                                if uid not in self.trackers: 
                                    self.trackers[uid] = {'c':0, 'blink':False, 'turn':False}
                                tr = self.trackers[uid]
                                
                                act = live.analyze_action(frame_orig, rect) # Check ảnh gốc
                                if act['valid']:
                                    if act['ear'] < Config.EYE_AR_THRESH: tr['c'] += 1
                                    else:
                                        if tr['c'] >= Config.EYE_AR_CONSEC_FRAMES: tr['blink'] = True
                                        tr['c'] = 0
                                    
                                    if abs(act['yaw']) > Config.YAW_THRESH: tr['turn'] = True
                                    
                                    if tr['blink'] or tr['turn']:
                                        self._do_checkin(uid); color = (0, 255, 0)
                                        del self.trackers[uid]
                    else: color = (0, 0, 255)
                    draw.append({"rect": rect, "color": color})
            
            # Clean trackers
            for k in list(self.trackers): 
                if k not in curr_ids: del self.trackers[k]
                
            # Send to UI (Drop old if full)
            try: self.result_queue.put_nowait(("DRAW", draw))
            except queue.Full: pass

    def _do_checkin(self, uid):
        if self.db.mark_attendance(self.session_id, uid, "AI"):
            self.checked_in_session.add(uid)
            with self._count_lock: self.current_count = len(self.checked_in_session)
            try: self.result_queue.put_nowait(("COUNT", self.current_count))
            except: pass

    def update_display_loop(self):
        if not self.is_running: return
        
        # 1. Process Queue
        try:
            while True:
                t, d = self.result_queue.get_nowait()
                if t == "DRAW": self.detected_objects = d
                elif t == "COUNT": 
                    with self._count_lock: self.current_count = d
        except queue.Empty: pass
        
        # 2. Timer
        rem = self.end_time - datetime.now()
        if rem.total_seconds() <= 0: self.on_close(); return
        m, s = divmod(int(rem.total_seconds()), 60)
        self.info_panel.config(text=f"Sĩ số: {self.current_count} | Time: {m:02d}:{s:02d}")
        
        # 3. Read & Show Frame
        frame = self.video.read()
        if frame is not None:
            self.process_frame = frame.copy() # Cho AI
            disp = frame.copy()
            
            for o in self.detected_objects:
                t,r,b,l = o["rect"]
                cv2.rectangle(disp, (l,t), (r,b), o["color"], 3)
            
            self.cam_label.config(image=cv2_to_pil(disp, width=1280, height=720))
            
        self.after(20, self.update_display_loop)

    def on_close(self):
        self.is_running = False
        if self.session_id: self.db.close_session(self.session_id)
        if hasattr(self, 'video') and self.video: self.video.stop()
        self.destroy()
        self.on_close_callback()