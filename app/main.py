import tkinter as tk
from tkinter import messagebox
import sys
import traceback
import logging

# QUAN TRỌNG: Setup logging TRƯỚC KHI import bất kỳ module nào
from utils.logger import setup_all_loggers
setup_all_loggers()

# Bây giờ mới import các module khác
from app.gui.register_window import RegisterWindow
from app.gui.attendance_window import AttendanceWindow
from app.gui.user_management_window import UserManagementWindow

logger = logging.getLogger(__name__)

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FACE ATTENDANCE SYSTEM PRO")
        self.geometry("800x500")
        self.configure(bg="#2c3e50")
        self.resizable(False, False)
        
        logger.info("="*60)
        logger.info("🚀 MAIN APP STARTED")
        logger.info("="*60)
        
        # --- PHÍM TẮT HỆ THỐNG ---
        self.bind_all("<Control-q>", self.force_quit)
        self.bind_all("<Escape>", lambda e: logger.info("ESC pressed"))
        
        self.report_callback_exception = self.show_error
        
        # UI Header
        tk.Label(
            self, 
            text="HỆ THỐNG ĐIỂM DANH AI", 
            font=("Segoe UI", 28, "bold"), 
            bg="#2c3e50", 
            fg="white"
        ).pack(pady=50)
        
        btn_frame = tk.Frame(self, bg="#2c3e50")
        btn_frame.pack(pady=10)
        
        btn_style = {
            "font": ("Segoe UI", 14), 
            "width": 25, 
            "fg": "white", 
            "relief": tk.FLAT, 
            "cursor": "hand2"
        }

        tk.Button(
            btn_frame, 
            text="👤 ĐĂNG KÝ MỚI", 
            command=self.open_register, 
            bg="#3498db", 
            **btn_style
        ).pack(pady=10)
        
        tk.Button(
            btn_frame, 
            text="📋 QUẢN LÝ SINH VIÊN", 
            command=self.open_management, 
            bg="#e67e22", 
            **btn_style
        ).pack(pady=10)
        
        tk.Button(
            btn_frame, 
            text="📷 BẮT ĐẦU ĐIỂM DANH", 
            command=self.open_attendance, 
            bg="#27ae60", 
            **btn_style
        ).pack(pady=10)
        
        tk.Button(
            btn_frame, 
            text="❌ THOÁT", 
            command=self.quit_app, 
            bg="#c0392b", 
            **btn_style
        ).pack(pady=10)
        
        # Hướng dẫn
        tk.Label(
            self, 
            text="Phím tắt: [ESC] Quay lại | [Ctrl+Q] Thoát ngay", 
            bg="#2c3e50", 
            fg="#7f8c8d"
        ).pack(side=tk.BOTTOM, pady=10)
        
        logger.info("✅ Main window initialized")

    def force_quit(self, event=None):
        """Thoát cưỡng bức"""
        logger.warning("⚠️ FORCE QUIT by user (Ctrl+Q)")
        self.destroy()
        sys.exit(0)

    def show_error(self, exc_type, exc_value, exc_traceback):
        """Xử lý lỗi toàn cục"""
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