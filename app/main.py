import tkinter as tk
from tkinter import messagebox
import sys
import traceback
from app.gui.register_window import RegisterWindow
from utils.logger import setup_logger

logger = setup_logger("MainApp")

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FACE ATTENDANCE SYSTEM")
        self.geometry("800x500")
        self.configure(bg="#2c3e50")
        self.resizable(False, False)
        
        self.report_callback_exception = self.show_error

        logger.info("App Started")
        
        tk.Label(self, text="HỆ THỐNG ĐIỂM DANH AI", font=("Segoe UI", 28, "bold"), bg="#2c3e50", fg="white").pack(pady=50)
        
        btn_frame = tk.Frame(self, bg="#2c3e50")
        btn_frame.pack(pady=10)
        
        btn_style = {"font": ("Segoe UI", 14), "width": 25, "fg": "white", "relief": tk.FLAT, "cursor": "hand2"}

        tk.Button(btn_frame, text="👤 ĐĂNG KÝ MỚI", command=self.open_register, bg="#3498db", **btn_style).pack(pady=10)
        tk.Button(btn_frame, text="❌ THOÁT", command=self.quit_app, bg="#c0392b", **btn_style).pack(pady=10)

    def show_error(self, exc_type, exc_value, exc_traceback):
        """
        Hàm này sẽ được gọi tự động mỗi khi có Crash/Error.
        """
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical(f"Uncaught Exception:\n{error_msg}")

        messagebox.showerror(
            "Đã xảy ra lỗi hệ thống",
            f"Đã có lỗi không mong muốn xảy ra!\n\nChi tiết: {exc_value}\n\nVui lòng kiểm tra file 'logs/app.log' hoặc liên hệ admin."
        )

    def open_register(self):
        self.withdraw()
        RegisterWindow(self, on_close=self.show_menu)

    def show_menu(self):
        self.deiconify()

    def quit_app(self):
        if messagebox.askokcancel("Thoát", "Bạn có chắc muốn thoát chương trình?"):
            logger.info("App Closed by User")
            self.destroy()

def handle_exception(exc_type, exc_value, exc_traceback):
    """Bắt các lỗi khởi động, lỗi import thư viện..."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical("Uncaught Exception (System Level):", exc_info=(exc_type, exc_value, exc_traceback))
    
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Lỗi Khởi Động", f"Không thể khởi chạy ứng dụng:\n{exc_value}")
        root.destroy()
    except:
        print("CRITICAL ERROR: Xem log để biết chi tiết.")

if __name__ == "__main__":
    sys.excepthook = handle_exception
    app = MainApp()