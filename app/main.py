import tkinter as tk
from tkinter import messagebox
import sys
import traceback
import logging
import platform # Để check hệ điều hành

# QUAN TRỌNG: Setup logging TRƯỚC KHI import bất kỳ module nào
from utils.logger import setup_all_loggers
setup_all_loggers()

# Import các màn hình con
from app.gui.register_window import RegisterWindow
from app.gui.attendance_window import AttendanceWindow
from app.gui.user_management_window import UserManagementWindow

# --- CẤU HÌNH GIAO DIỆN ĐA NỀN TẢNG ---
# Kiểm tra xem có phải macOS không
IS_MACOS = sys.platform.startswith("darwin")
if IS_MACOS:
    try:
        from tkmacosx import Button as MacButton
    except ImportError:
        print("⚠️ Cảnh báo: Chưa cài tkmacosx. Giao diện trên Mac có thể bị lỗi màu.")
        IS_MACOS = False

logger = logging.getLogger(__name__)

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FACE ATTENDANCE SYSTEM PRO")
        
        # Cấu hình kích thước và căn giữa
        w, h = 800, 550
        self.geometry(f"{w}x{h}")
        self.center_window(w, h)
        
        self.configure(bg="#2c3e50")
        self.resizable(False, False)
        
        logger.info("="*60)
        logger.info(f"🚀 MAIN APP STARTED on {platform.system()} {platform.release()}")
        logger.info("="*60)
        
        # --- PHÍM TẮT HỆ THỐNG ---
        self.bind_all("<Control-q>", self.force_quit)
        self.bind_all("<Escape>", lambda e: logger.info("ESC pressed"))
        
        self.report_callback_exception = self.show_error
        
        self.create_ui()
        logger.info("✅ Main window initialized")

    def center_window(self, w, h):
        """Hàm căn giữa cửa sổ ứng dụng"""
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.geometry('%dx%d+%d+%d' % (w, h, x, y))

    def create_ui(self):
        # Header
        tk.Label(
            self, 
            text="HỆ THỐNG ĐIỂM DANH AI", 
            font=("Segoe UI", 28, "bold"), 
            bg="#2c3e50", 
            fg="white"
        ).pack(pady=(40, 30))
        
        btn_frame = tk.Frame(self, bg="#2c3e50")
        btn_frame.pack(pady=10)
        
        # --- Helper tạo nút thông minh (Tự thích ứng OS) ---
        def create_btn(text, cmd, color):
            # Cấu hình chung
            opts = {
                "text": text, 
                "command": cmd, 
                "bg": color, 
                "fg": "white",
                "font": ("Segoe UI", 14, "bold"),
                "cursor": "hand2"
            }
            
            if IS_MACOS:
                # Cấu hình riêng cho Mac (Dùng tkmacosx)
                # Mac dùng pixel cho width, cần borderless để hiện màu
                return MacButton(
                    btn_frame, 
                    height=50, 
                    width=280, 
                    borderless=True, 
                    activebackground=color,
                    **opts
                )
            else:
                # Cấu hình riêng cho Windows/Linux (Dùng tk chuẩn)
                # Windows dùng text units cho width
                return tk.Button(
                    btn_frame, 
                    width=25, 
                    relief=tk.FLAT, 
                    activebackground="#34495e", 
                    activeforeground="white",
                    **opts
                )

        # Tạo các nút
        create_btn("👤 ĐĂNG KÝ MỚI", self.open_register, "#3498db").pack(pady=10)
        create_btn("📋 QUẢN LÝ SINH VIÊN", self.open_management, "#e67e22").pack(pady=10)
        create_btn("📷 BẮT ĐẦU ĐIỂM DANH", self.open_attendance, "#27ae60").pack(pady=10)
        create_btn("❌ THOÁT", self.quit_app, "#c0392b").pack(pady=10)
        
        # Footer
        tk.Label(
            self, 
            text="Phím tắt: [ESC] Quay lại | [Ctrl+Q] Thoát ngay", 
            bg="#2c3e50", 
            fg="#95a5a6",
            font=("Segoe UI", 10)
        ).pack(side=tk.BOTTOM, pady=20)

    def force_quit(self, event=None):
        logger.warning("⚠️ FORCE QUIT by user (Ctrl+Q)")
        self.destroy()
        sys.exit(0)

    def show_error(self, exc_type, exc_value, exc_traceback):
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical(f"❌ UNCAUGHT EXCEPTION:\n{error_msg}")
        messagebox.showerror(
            "Lỗi Hệ Thống", 
            f"Lỗi: {exc_value}\n\nXem file log để biết thêm chi tiết."
        )

    def open_register(self):
        logger.info("📝 Opening Register Window")
        self.withdraw()
        try:
            RegisterWindow(self, on_close=self.show_menu)
        except Exception as e:
            logger.error(f"❌ Error opening Register: {e}", exc_info=True)
            self.show_menu()

    def open_management(self):
        logger.info("📋 Opening User Management Window")
        self.withdraw()
        try:
            UserManagementWindow(self, on_close=self.show_menu)
        except Exception as e:
            logger.error(f"❌ Error opening Management: {e}", exc_info=True)
            self.show_menu()

    def open_attendance(self):
        logger.info("📷 Opening Attendance Window")
        self.withdraw()
        try:
            AttendanceWindow(self, on_close=self.show_menu)
        except Exception as e:
            logger.error(f"❌ Error opening Attendance: {e}", exc_info=True)
            messagebox.showerror("Lỗi", f"Không thể mở điểm danh: {e}")
            self.show_menu()

    def show_menu(self):
        logger.info("🔙 Returning to main menu")
        self.deiconify()

    def quit_app(self):
        if messagebox.askokcancel("Thoát", "Bạn có chắc muốn thoát chương trình?"):
            logger.info("👋 App closed by user")
            self.destroy()


def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.critical(
        "💥 SYSTEM LEVEL EXCEPTION:", 
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    print(f"\n{'='*80}")
    print(f"💥 CRITICAL ERROR: {exc_value}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    # Set global exception handler
    sys.excepthook = handle_exception
    
    try:
        logger.info("🎬 Starting MainApp...")
        app = MainApp()
        logger.info("🔄 Entering mainloop...")
        app.mainloop()
    except Exception as e:
        logger.critical(f"💥 Fatal error in main: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("🏁 Application terminated")