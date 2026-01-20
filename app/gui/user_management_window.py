import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from database.db_manager import DatabaseManager
from core.face_encoder import FaceEncoder

class UserManagementWindow(tk.Toplevel):
    def __init__(self, parent, on_close):
        super().__init__(parent)
        self.on_close_callback = on_close
        
        self.title("Quản Lý Danh Sách Sinh Viên")
        self.geometry("900x600")
        
        self.db = DatabaseManager()
        self.encoder = FaceEncoder() # Cần để xóa vector khuôn mặt
        
        self.create_ui()
        self.load_data()
        
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def create_ui(self):
        # 1. Toolbar (Thanh công cụ)
        toolbar = tk.Frame(self, bg="#ecf0f1", height=50)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        
        btn_config = {"padx": 10, "pady": 5, "side": tk.LEFT}
        
        tk.Button(toolbar, text="🔙 Quay lại", command=self.on_window_close, bg="#7f8c8d", fg="white").pack(**btn_config)
        tk.Button(toolbar, text="🔄 Làm mới", command=self.load_data, bg="#3498db", fg="white").pack(**btn_config)
        tk.Button(toolbar, text="✏️ Sửa thông tin", command=self.edit_student, bg="#f39c12", fg="white").pack(**btn_config)
        tk.Button(toolbar, text="🗑️ Xóa Sinh viên", command=self.delete_student, bg="#e74c3c", fg="white").pack(**btn_config)
        
        tk.Button(toolbar, text="📊 Xuất Excel", command=self.export_data, bg="#27ae60", fg="white").pack(side=tk.RIGHT, padx=10, pady=5)

        # 2. Table (Bảng dữ liệu)
        # Cấu hình các cột cho Sinh viên
        columns = ("id", "name", "class", "created_at")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        
        # Định nghĩa tiêu đề
        self.tree.heading("id", text="Mã Sinh Viên (MSSV)")
        self.tree.heading("name", text="Họ và Tên")
        self.tree.heading("class", text="Lớp Hành Chính")
        self.tree.heading("created_at", text="Ngày Đăng Ký")
        
        # Định nghĩa kích thước cột
        self.tree.column("id", width=150, anchor="center")
        self.tree.column("name", width=250)
        self.tree.column("class", width=150, anchor="center")
        self.tree.column("created_at", width=200, anchor="center")
        
        # Thêm thanh cuộn (Scrollbar)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def load_data(self):
        """Lấy dữ liệu từ DB và đổ vào bảng"""
        # Xóa dữ liệu cũ trên bảng
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Lấy danh sách mới
        students = self.db.get_all_students()
        
        for s in students:
            self.tree.insert("", tk.END, values=(
                s['student_id'], 
                s['name'], 
                s['class_name'], 
                s['created_at']
            ))

    def delete_student(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Chú ý", "Vui lòng chọn sinh viên cần xóa!")
            return
            
        # Lấy dữ liệu dòng đang chọn
        item = self.tree.item(selected[0])
        student_id = item['values'][0]
        student_name = item['values'][1]
        
        confirm = messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa sinh viên:\n{student_name} ({student_id})?\n\nDữ liệu điểm danh và khuôn mặt cũng sẽ bị xóa.")
        
        if confirm:
            # 1. Xóa trong DB
            if self.db.delete_student(str(student_id)):
                # 2. Xóa Vector khuôn mặt trong file cache
                self.encoder.remove_encoding(str(student_id))
                
                # 3. Load lại bảng
                self.load_data()
                messagebox.showinfo("Thành công", "Đã xóa sinh viên khỏi hệ thống.")
            else:
                messagebox.showerror("Lỗi", "Không thể xóa dữ liệu trong Database.")

    def edit_student(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Chú ý", "Vui lòng chọn sinh viên cần sửa!")
            return
            
        item = self.tree.item(selected[0])
        current_id = str(item['values'][0])
        current_name = item['values'][1]
        current_class = item['values'][2]
        
        # Hộp thoại sửa tên
        new_name = simpledialog.askstring("Sửa thông tin", f"Họ tên ({current_id}):", initialvalue=current_name)
        if new_name is None: return # Người dùng bấm Cancel
        
        # Hộp thoại sửa lớp
        new_class = simpledialog.askstring("Sửa thông tin", f"Lớp ({current_id}):", initialvalue=current_class)
        if new_class is None: return # Người dùng bấm Cancel
        
        # Cập nhật DB
        if new_name and new_class:
            if self.db.update_student(current_id, new_name, new_class):
                self.load_data()
                messagebox.showinfo("Thành công", "Cập nhật thông tin thành công.")
            else:
                messagebox.showerror("Lỗi", "Cập nhật thất bại.")

    def export_data(self):
        """Xuất file Excel điểm danh"""
        success, path = self.db.export_excel()
        if success:
            messagebox.showinfo("Xuất Excel", f"File đã được lưu thành công tại:\n{path}")
        else:
            messagebox.showerror("Lỗi Xuất File", f"Chi tiết lỗi:\n{path}")

    def on_window_close(self):
        self.destroy()
        self.on_close_callback()