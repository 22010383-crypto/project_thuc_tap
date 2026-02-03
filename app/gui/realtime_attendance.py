"""
Real-time Attendance Window - Ultra-smooth Performance
"""
import tkinter as tk
from tkinter import messagebox
import cv2
import pickle
import time
import os
from datetime import datetime, timedelta
from app.config import Config
from database.db_manager import DatabaseManager
from core.realtime_engine import OptimizedAttendanceSystem
import logging

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)


class RealtimeAttendanceWindow(tk.Toplevel):
    def __init__(self, parent, on_close):
        super().__init__(parent)
        self.on_close_callback = on_close
        self.geometry("1280x800")
        self.title("Điểm danh realtime")
        
        self.system = None
        self.cap = None
        self.running = False
        self.fps_frame_times = []
        self.fps_update_interval = 0.5
        self.last_fps_update = 0.0
        
        self.create_ui()
        self.after(100, self.initialize_system)
        self.protocol("WM_DELETE_WINDOW", self.cleanup)
    
    def create_ui(self):
        # Top bar
        top = tk.Frame(self, bg="#2c3e50", height=50)
        top.pack(side=tk.TOP, fill=tk.X)
        top.pack_propagate(False)
        
        self.lbl_session = tk.Label(top, text="Loading...", bg="#2c3e50", fg="white", font=("Arial", 12))
        self.lbl_session.pack(side=tk.LEFT, padx=20)
        
        self.lbl_fps = tk.Label(top, text="FPS: --", bg="#2c3e50", fg="lime", font=("Arial", 12, "bold"))
        self.lbl_fps.pack(side=tk.LEFT, padx=20)
        
        self.lbl_time = tk.Label(top, text="00:00", bg="#2c3e50", fg="white", font=("Arial", 12))
        self.lbl_time.pack(side=tk.RIGHT, padx=20)
        
        # Canvas
        self.canvas = tk.Canvas(self, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bottom bar
        bottom = tk.Frame(self, bg="#34495e", height=70)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        bottom.pack_propagate(False)
        
        self.lbl_count = tk.Label(bottom, text="Checked in: 0", bg="#34495e", fg="white", font=("Arial", 20, "bold"))
        self.lbl_count.pack(side=tk.LEFT, padx=20)
        
        tk.Button(bottom, text="STOP", command=self.cleanup, bg="red", fg="white", 
                 font=("Arial", 12, "bold"), width=10).pack(side=tk.RIGHT, padx=20, pady=10)
    
    def initialize_system(self):
        try:
            # Load encodings
            if not os.path.exists(Config.ENCODINGS_PATH):
                messagebox.showerror("Lỗi", f"Không tìm thấy file encodings!\nVui lòng đăng ký khuôn mặt trước.")
                self.cleanup()
                return
            
            with open(Config.ENCODINGS_PATH, 'rb') as f:
                data = pickle.load(f)
                encodings = data.get('encodings', [])
                ids = data.get('ids') or data.get('person_ids', [])
            
            if not encodings or not ids:
                messagebox.showerror("Lỗi", "Database trống! Vui lòng đăng ký khuôn mặt trước.")
                self.cleanup()
                return
            
            if not encodings or not ids:
                raise Exception("Chưa có dữ liệu khuôn mặt. Hãy đăng ký trước!")
            
            # Create session
            db = DatabaseManager(cooldown_minutes=0.05)  # 3 second cooldown
            session_id = db.create_session(f"RT_{datetime.now().strftime('%H%M')}")
            self.end_time = datetime.now() + timedelta(minutes=45)
            
            # Initialize system
            self.system = OptimizedAttendanceSystem(encodings, ids, db, session_id)
            self.system.start()
            
            # Open camera
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            self.lbl_session.config(text=f"Session #{session_id} - Real-time Mode")
            
            self.running = True
            self.update_loop()
            self.update_timer()
            
        except Exception as e:
            import traceback
            error_msg = f"Init failed: {e}\n\n{traceback.format_exc()}"
            messagebox.showerror("Lỗi", error_msg)
            self.cleanup()
    
    def update_loop(self):
        if not self.running:
            return
        
        t0 = time.perf_counter()
        ret, frame = self.cap.read()
        
        if ret:
            self.system.put_frame(frame)
            display = self.system.get_display_frame(frame)
            
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            
            if w > 1 and h > 1:
                resized = cv2.resize(display, (w, h))
                img_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                
                if HAS_PIL:
                    img_pil = Image.fromarray(img_rgb)
                    self.photo = ImageTk.PhotoImage(img_pil)
                else:
                    height, width = img_rgb.shape[:2]
                    ppm_header = f'P6 {width} {height} 255 '.encode()
                    ppm_data = ppm_header + img_rgb.tobytes()
                    self.photo = tk.PhotoImage(width=width, height=height, data=ppm_data, format='PPM')
                
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            
            count = self.system.get_count()
            self.lbl_count.config(text=f"Checked in: {count}")
            
            # FPS
            elapsed = time.perf_counter() - t0
            self.fps_frame_times.append(elapsed)
            if len(self.fps_frame_times) > 30:
                self.fps_frame_times.pop(0)
            now = time.time()
            if now - self.last_fps_update >= self.fps_update_interval:
                avg_frame = sum(self.fps_frame_times) / len(self.fps_frame_times) if self.fps_frame_times else 0.033
                fps = 1.0 / avg_frame if avg_frame > 0 else 0
                self.lbl_fps.config(text=f"FPS: {fps:.1f}")
                self.last_fps_update = now
        
        self.after(16, self.update_loop)
    
    def update_timer(self):
        if not self.running:
            return
        
        remaining = self.end_time - datetime.now()
        
        if remaining.total_seconds() <= 0:
            self.cleanup()
            return
        
        m = int(remaining.total_seconds() // 60)
        s = int(remaining.total_seconds() % 60)
        self.lbl_time.config(text=f"{m:02d}:{s:02d}")
        
        self.after(1000, self.update_timer)
    
    def cleanup(self):
        self.running = False
        
        if self.system:
            self.system.stop()
        
        if self.cap:
            self.cap.release()
        
        self.destroy()
        
        if self.on_close_callback:
            self.on_close_callback()
