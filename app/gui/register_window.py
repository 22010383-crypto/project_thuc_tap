import tkinter as tk
from tkinter import messagebox
import cv2
import threading
from app.config import Config
from database.db_manager import DatabaseManager
from core.face_encoder import FaceEncoder
from utils.video_stream import VideoStream
from utils.image_utils import cv2_to_pil

class RegisterWindow(tk.Toplevel):
    def __init__(self, parent, on_close):
        super().__init__(parent)
        self.on_close_callback = on_close
        self.title("Đăng Ký Sinh Viên Mới")
        self.geometry("950x600")
        self.resizable(False, False)
        
        self.db = DatabaseManager()
        self.encoder = FaceEncoder()
        self.video = VideoStream(Config.CAMERA_INDEX).start()
        
        self.is_running = True
        self.current_frame = None
        
        self.create_ui()
        self.update_camera()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_ui(self):
        left = tk.Frame(self, width=350, bg="#ecf0f1")
        left.pack(side=tk.LEFT, fill=tk.BOTH, ipadx=10)
        
        tk.Label(left, text="NHẬP THÔNG TIN", font=("Arial", 16, "bold"), bg="#ecf0f1").pack(pady=30)
        
        self.e_id = self.mk_entry(left, "Mã Sinh Viên (MSSV):")
        self.e_name = self.mk_entry(left, "Họ và Tên:")
        self.e_class = self.mk_entry(left, "Lớp Hành Chính:")
        
        self.btn = tk.Button(left, text="CHỤP & LƯU", command=self.do_capture, 
                             bg="#2ecc71", fg="white", font=("Arial", 12, "bold"), height=2)
        self.btn.pack(fill=tk.X, padx=30, pady=40)
        
        right = tk.Frame(self, bg="black")
        right.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        self.cam_lbl = tk.Label(right, bg="black")
        self.cam_lbl.pack(expand=True, fill=tk.BOTH)

    def mk_entry(self, p, txt):
        tk.Label(p, text=txt, bg="#ecf0f1", anchor="w").pack(fill=tk.X, padx=30, pady=(10,0))
        e = tk.Entry(p, font=("Arial", 12)); e.pack(fill=tk.X, padx=30, pady=5)
        return e

    def update_camera(self):
        if not self.is_running: return
        frame = self.video.read()
        if frame is not None:
            self.current_frame = frame.copy()
            # Vẽ khung xanh hướng dẫn
            disp = frame.copy()
            h, w, _ = disp.shape
            cv2.rectangle(disp, (w//4, h//6), (3*w//4, 5*h//6), (0,255,0), 2)
            self.photo = cv2_to_pil(disp, width=600, height=450)
            self.cam_lbl.config(image=self.photo)
        self.after(20, self.update_camera)

    def do_capture(self):
        sid = self.e_id.get().strip()
        name = self.e_name.get().strip()
        cls = self.e_class.get().strip()
        if not sid or not name: return messagebox.showwarning("Thiếu tin", "Nhập đủ MSSV và Tên")
        
        self.btn.config(state="disabled", text="Đang xử lý...")
        threading.Thread(target=self.save, args=(sid, name, cls)).start()

    def save(self, sid, name, cls):
        if self.current_frame is None: return
        
        # 1. Lưu DB
        if not self.db.add_student(sid, name, cls):
            self.done(False, "MSSV đã tồn tại!")
            return
            
        # 2. Lưu Vector AI
        ok, msg = self.encoder.add_face(self.current_frame, sid)
        if ok: self.done(True, f"Đã lưu sinh viên: {sid}")
        else:
            self.db.delete_student(sid) # Rollback
            self.done(False, msg)

    def done(self, ok, msg):
        self.after(0, lambda: [messagebox.showinfo("OK", msg) if ok else messagebox.showerror("Lỗi", msg), 
                               self.on_close() if ok else self.btn.config(state="normal", text="CHỤP & LƯU")])

    def on_close(self):
        self.is_running = False
        self.video.stop()
        self.destroy()
        self.on_close_callback()