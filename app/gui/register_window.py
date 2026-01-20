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
        self.title("Đăng Ký Sinh Viên (Yêu cầu Chớp mắt)")
        self.geometry("950x650")
        
        self.db = DatabaseManager()
        self.encoder = FaceEncoder()
        
        self.video = VideoStream(Config.CAMERA_INDEX).start()
        self.is_running = True
        self.current_frame = None
        self.is_capturing = False 
        self.consec_closed = 0  
        
        self.create_ui()
        self.update_camera()
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def create_ui(self):
        left = tk.Frame(self, width=350, bg="#f5f6fa"); left.pack(side=tk.LEFT, fill=tk.BOTH)
        tk.Label(left, text="THÊM MỚI SINH VIÊN", font=("Segoe UI", 16, "bold"), bg="#f5f6fa").pack(pady=20)
        
        self.e_id = self.mk_input(left, "MSSV:")
        self.e_name = self.mk_input(left, "Họ Tên:")
        self.e_cls = self.mk_input(left, "Lớp:")
        
        self.btn = tk.Button(left, text="📸 BẮT ĐẦU CHỤP", command=self.prepare_capture, 
                             bg="#3498db", fg="white", font=("Segoe UI", 12, "bold"), height=2)
        self.btn.pack(fill=tk.X, padx=30, pady=40)
        
        self.lbl_status = tk.Label(left, text="...", bg="#f5f6fa", fg="gray")
        self.lbl_status.pack(side=tk.BOTTOM, pady=20)
        
        right = tk.Frame(self, bg="black"); right.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        self.cam = tk.Label(right, bg="black"); self.cam.pack(expand=True, fill=tk.BOTH)

    def mk_input(self, p, txt):
        tk.Label(p, text=txt, bg="#f5f6fa").pack(anchor="w", padx=30)
        e = tk.Entry(p, font=("Segoe UI", 11)); e.pack(fill=tk.X, padx=30, pady=(0,10))
        return e

    def update_camera(self):
        if not self.is_running: return
        frame = self.video.read()
        if frame is not None:
            self.current_frame = frame.copy()
            disp = frame.copy()
            
            # Logic Liveness Registration
            if self.is_capturing:
                locs = self.detector.detect(frame)
                if locs:
                    # Lấy action của khuôn mặt đầu tiên
                    state = self.liveness.detect_actions(frame, locs[0])
                    
                    if state["blink"]:
                        self.consec_closed += 1
                    else:
                        if self.consec_closed >= 2: # Đã nhắm đủ lâu và mở ra
                            # -> CHỤP NGAY
                            self.is_capturing = False
                            self.lbl_status.config(text="Đã phát hiện người thật! Đang lưu...", fg="green")
                            threading.Thread(target=self.save_data).start()
                        self.consec_closed = 0
                        
                    cv2.putText(disp, "HAY CHOP MAT!", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                else:
                    self.lbl_status.config(text="Không thấy mặt đâu!", fg="red")
            
            h, w, _ = disp.shape
            cv2.rectangle(disp, (w//4, h//4), (3*w//4, 3*h//4), (0, 255, 0), 2)
            self.cam.config(image=cv2_to_pil(disp, width=600, height=450))
        self.after(10, self.update_camera)

    def prepare_capture(self):
        if not self.e_id.get() or not self.e_name.get():
            messagebox.showwarning("Lỗi", "Nhập thiếu thông tin!")
            return
        self.is_capturing = True
        self.consec_closed = 0
        self.btn.config(state=tk.DISABLED, text="ĐANG ĐỢI CHỚP MẮT...", bg="#e67e22")

    def save_data(self):
        sid = self.e_id.get(); name = self.e_name.get(); cls = self.e_cls.get()
        if not self.db.add_student(sid, name, cls):
            self.end(False, "MSSV trùng!")
            return
        success, msg = self.encoder.add_face(self.current_frame, sid)
        if success: self.end(True, "Đăng ký thành công!")
        else:
            self.db.delete_student(sid)
            self.end(False, msg)

    def end(self, success, msg):
        self.after(0, lambda: self._end_ui(success, msg))

    def _end_ui(self, success, msg):
        self.is_capturing = False
        self.btn.config(state=tk.NORMAL, text="BẮT ĐẦU CHỤP", bg="#3498db")
        if success: messagebox.showinfo("OK", msg); self.on_window_close()
        else: messagebox.showerror("Lỗi", msg)

    def on_window_close(self):
        self.is_running = False
        self.video.stop()
        self.destroy()
        self.on_close_callback()