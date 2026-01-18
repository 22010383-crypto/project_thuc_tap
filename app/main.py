import tkinter as tk
from tkinter import messagebox
from utils.logger import setup_logger

logger = setup_logger("MainApp")

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FACE ATTENDANCE SYSTEM PRO")
        self.geometry("800x500")
        self.configure(bg="#2c3e50")
        self.resizable(False, False)
        
        logger.info("App Started")
        
        # UI Header
        tk.Label(self, text="HỆ THỐNG ĐIỂM DANH AI", font=("Segoe UI", 28, "bold"), bg="#2c3e50", fg="white").pack(pady=50)
        
        btn_frame = tk.Frame(self, bg="#2c3e50")
        btn_frame.pack(pady=10)
        
        # Định nghĩa style chung cho nút
        btn_style = {"font": ("Segoe UI", 14), "width": 25, "fg": "white", "relief": tk.FLAT, "cursor": "hand2"}
        # Nút Thoát
        tk.Button(btn_frame, text="❌ THOÁT", command=self.quit_app, bg="#c0392b", **btn_style).pack(pady=10)

        tk.Label(self, text="Version 2.1 - Single Task Mode", bg="#2c3e50", fg="#95a5a6").pack(side=tk.BOTTOM, pady=20)

    def show_menu(self):
        """Hàm này được gọi khi cửa sổ con đóng lại"""
        self.deiconify()  # Hiện lại menu chính
        logger.info("Returned to Main Menu")

    def quit_app(self):
        if messagebox.askokcancel("Thoát", "Bạn có chắc muốn thoát chương trình?"):
            logger.info("App Closed by User")
            self.destroy()

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()