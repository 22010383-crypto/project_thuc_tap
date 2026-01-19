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
        
        # --- KHỞI TẠO CÁC MODULE ---
        self.db = DatabaseManager()
        self.encoder = FaceEncoder()
        
        # Camera
        self.video = VideoStream(Config.CAMERA_INDEX).start()
        
        # Trạng thái hoạt động
        self.is_running = True
        self.current_frame = None # Biến lưu frame hiện tại để thread khác truy cập
        
        # --- XÂY DỰNG GIAO DIỆN ---
        self.create_ui()
        
        # --- BẮT ĐẦu CAMERA ---
        self.update_camera()
        
        # Xử lý sự kiện khi bấm nút X đóng cửa sổ
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)
        
    def create_ui(self):
        """Tạo layout chia đôi: Trái (Input) - Phải (Camera)"""
        # 1. Panel Trái: Form nhập liệu
        left_panel = tk.Frame(self, width=350, bg="#f5f6fa")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH)
        left_panel.pack_propagate(False) # Giữ cố định chiều rộng

        # Tiêu đề
        tk.Label(left_panel, text="THÔNG TIN SINH VIÊN", 
                 font=("Segoe UI", 16, "bold"), bg="#f5f6fa", fg="#2c3e50").pack(pady=(40, 30))

        self.entry_id = self.create_input_field(left_panel, "Mã Sinh Viên (ID):")
        self.entry_name = self.create_input_field(left_panel, "Họ và Tên:")
        self.entry_dept = self.create_input_field(left_panel, "Phòng Ban:")

        self.btn_capture = tk.Button(left_panel, text="📸 CHỤP & LƯU", 
                                     command=self.start_capture_thread,
                                     font=("Segoe UI", 12, "bold"), 
                                     bg="#2ecc71", fg="white", 
                                     activebackground="#27ae60", activeforeground="white",
                                     relief=tk.FLAT, height=2, cursor="hand2")
        self.btn_capture.pack(fill=tk.X, padx=30, pady=40)

        note_text = ("Lưu ý:\n"
                     "• Nhìn thẳng vào camera\n"
                     "• Giữ khuôn mặt trong khung xanh\n"
                     "• Đảm bảo đủ ánh sáng")
        tk.Label(left_panel, text=note_text, justify=tk.LEFT, 
                 font=("Segoe UI", 10), bg="#f5f6fa", fg="#7f8c8d").pack(side=tk.BOTTOM, pady=30, padx=30, anchor="w")

        # 2. Panel Phải: Camera Feed
        right_panel = tk.Frame(self, bg="black")
        right_panel.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        self.cam_label = tk.Label(right_panel, bg="black")
        self.cam_label.pack(expand=True, fill=tk.BOTH)

    def create_input_field(self, parent, label_text):
        """Hàm helper để tạo ô nhập liệu đẹp hơn"""
        frame = tk.Frame(parent, bg="#f5f6fa")
        frame.pack(fill=tk.X, padx=30, pady=10)
        
        tk.Label(frame, text=label_text, font=("Segoe UI", 11), 
                 bg="#f5f6fa", fg="#34495e").pack(anchor="w")
        
        entry = tk.Entry(frame, font=("Segoe UI", 12), relief=tk.FLAT, bd=1, highlightthickness=1)
        entry.config(highlightbackground="#bdc3c7", highlightcolor="#3498db")
        entry.pack(fill=tk.X, pady=(5, 0), ipady=5)
        return entry

    def update_camera(self):
        """Vòng lặp cập nhật hình ảnh từ camera lên giao diện"""
        if not self.is_running:
            return

        frame = self.video.read()
        if frame is not None:
            # Lưu frame gốc để thread xử lý (tránh bị resize làm giảm chất lượng nhận diện)
            self.current_frame = frame.copy()
            
            # Vẽ khung hướng dẫn lên hình hiển thị (không vẽ lên hình lưu)
            display_frame = frame.copy()
            h, w, _ = display_frame.shape
            
            # Vẽ khung chữ nhật bo góc (hoặc thường) màu xanh
            cv2.rectangle(display_frame, (w//4, h//4), (3*w//4, 3*h//4), (0, 255, 0), 2)
            cv2.putText(display_frame, "GIU MAT TRONG KHUNG", (w//4 + 20, h//4 - 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Chuyển đổi để hiển thị trên Tkinter
            self.photo = cv2_to_pil(display_frame, width=600, height=450)
            self.cam_label.config(image=self.photo)
        
        # Gọi lại sau 10ms (khoảng 100 FPS refresh rate cho UI)
        self.after(10, self.update_camera)

    def start_capture_thread(self):
        """Bắt đầu luồng xử lý đăng ký"""
        # 1. Validate Input (Chạy trên UI Thread)
        user_id = self.entry_id.get().strip()
        name = self.entry_name.get().strip()
        dept = self.entry_dept.get().strip()
        
        if not user_id or not name:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập Mã NV và Họ Tên!")
            return

        # 2. Khóa giao diện
        self.btn_capture.config(state=tk.DISABLED, text="⏳ ĐANG XỬ LÝ...", bg="#95a5a6")
        
        # 3. Chạy Worker Thread
        thread = threading.Thread(target=self.process_capture, args=(user_id, name, dept))
        thread.start()

    def process_capture(self, user_id, name, dept):
        """Hàm chạy ngầm (Background Worker) - Xử lý nặng"""
        try:
            if self.current_frame is None:
                self.schedule_ui_update(False, "Không nhận được tín hiệu Camera!")
                return

            if not self.db.add_user(user_id, name, dept):
                self.schedule_ui_update(False, f"Mã nhân viên '{user_id}' đã tồn tại!")
                return

            success, message = self.encoder.add_face(self.current_frame, user_id)
            
            if success:
                self.schedule_ui_update(True, f"Đăng ký thành công!\nSinh viên: {name}")
            else:
                # ROLLBACK: Nếu AI lỗi (không thấy mặt, mặt mờ...), phải xóa user trong DB
                self.db.delete_user(user_id)
                self.schedule_ui_update(False, f"Lỗi xử lý ảnh: {message}")

        except Exception as e:
            self.schedule_ui_update(False, f"Lỗi hệ thống: {str(e)}")

    def schedule_ui_update(self, success, message):
        """Cầu nối an toàn để Worker gọi update UI trên Main Thread"""
        self.after(0, lambda: self.finish_capture(success, message))

    def finish_capture(self, success, message):
        """Cập nhật giao diện sau khi Worker làm xong"""
        # Mở lại nút bấm
        self.btn_capture.config(state=tk.NORMAL, text="📸 CHỤP & LƯU", bg="#2ecc71")
        
        if success:
            messagebox.showinfo("Thành công", message)
            self.on_window_close() # Đóng cửa sổ đăng ký thành công
        else:
            messagebox.showerror("Thất bại", message)

    def on_window_close(self):
        """Dọn dẹp tài nguyên khi đóng cửa sổ"""
        self.is_running = False
        self.video.stop() # Dừng thread camera
        self.destroy()    # Hủy cửa sổ này
        self.on_close_callback() # Gọi callback để hiện lại Menu chính