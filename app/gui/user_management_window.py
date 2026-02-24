import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from database.db_manager import DatabaseManager
from core.face_encoder import FaceEncoder
import logging

logger = logging.getLogger(__name__)

class UserManagementWindow(tk.Toplevel):
    def __init__(self, parent, on_close):
        super().__init__(parent)
        self.on_close_callback = on_close
        
        self.title("Quản Lý Danh Sách Sinh Viên")
        self.geometry("1000x650")
        self.configure(bg="#ecf0f1")
        
        logger.info("📋 User Management Window opened")
        
        try:
            self.db = DatabaseManager()
            self.encoder = FaceEncoder()
            logger.info("✅ Database and Encoder initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            messagebox.showerror("Lỗi", f"Không thể khởi tạo hệ thống: {e}")
            self.on_window_close()
            return
        
        self.create_ui()
        self.load_data()
        
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def create_ui(self):
        """Tạo giao diện"""
        # === HEADER ===
        header = tk.Frame(self, bg="#34495e", height=60)
        header.pack(fill=tk.X, side=tk.TOP)
        
        tk.Label(
            header,
            text="📋 QUẢN LÝ SINH VIÊN",
            font=("Segoe UI", 18, "bold"),
            bg="#34495e",
            fg="white"
        ).pack(pady=15)
        
        # === TOOLBAR ===
        toolbar = tk.Frame(self, bg="#ecf0f1", height=60)
        toolbar.pack(fill=tk.X, side=tk.TOP, pady=10)
        
        btn_config = {
            "font": ("Segoe UI", 10),
            "relief": tk.FLAT,
            "cursor": "hand2",
            "padx": 15,
            "pady": 8
        }
        
        # Left buttons
        left_frame = tk.Frame(toolbar, bg="#ecf0f1")
        left_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Button(
            left_frame,
            text="🔙 Quay lại",
            command=self.on_window_close,
            bg="#7f8c8d",
            fg="white",
            **btn_config
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            left_frame,
            text="🔄 Làm mới",
            command=self.load_data,
            bg="#3498db",
            fg="white",
            **btn_config
        ).pack(side=tk.LEFT, padx=5)
        
        # Middle buttons
        middle_frame = tk.Frame(toolbar, bg="#ecf0f1")
        middle_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Button(
            middle_frame,
            text="✏️ Sửa thông tin",
            command=self.edit_student,
            bg="#f39c12",
            fg="white",
            **btn_config
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            middle_frame,
            text="🗑️ Xóa Sinh viên",
            command=self.delete_student,
            bg="#e74c3c",
            fg="white",
            **btn_config
        ).pack(side=tk.LEFT, padx=5)
        
        # Right buttons
        right_frame = tk.Frame(toolbar, bg="#ecf0f1")
        right_frame.pack(side=tk.RIGHT, padx=10)
        
        tk.Button(
            right_frame,
            text="📊 Xuất Excel",
            command=self.export_data,
            bg="#27ae60",
            fg="white",
            **btn_config
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            right_frame,
            text="📈 Thống kê",
            command=self.show_statistics,
            bg="#16a085",
            fg="white",
            **btn_config
        ).pack(side=tk.LEFT, padx=5)
        
        # === SEARCH BAR ===
        search_frame = tk.Frame(self, bg="#ecf0f1")
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(
            search_frame,
            text="🔍 Tìm kiếm:",
            bg="#ecf0f1",
            font=("Segoe UI", 10)
        ).pack(side=tk.LEFT, padx=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_changed)
        
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Segoe UI", 10),
            width=30
        )
        self.search_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            search_frame,
            text="❌ Xóa",
            command=self.clear_search,
            bg="#95a5a6",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        # Info label
        self.info_label = tk.Label(
            search_frame,
            text="Tổng: 0 sinh viên",
            bg="#ecf0f1",
            fg="#7f8c8d",
            font=("Segoe UI", 10)
        )
        self.info_label.pack(side=tk.RIGHT, padx=10)
        
        # === TABLE FRAME ===
        table_frame = tk.Frame(self, bg="white")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Style cho Treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="white",
            foreground="black",
            rowheight=30,
            fieldbackground="white",
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 11, "bold"),
            background="#34495e",
            foreground="white"
        )
        style.map("Treeview", background=[("selected", "#3498db")])
        
        # Treeview với các cột
        columns = ("id", "name", "class", "created_at")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        
        # Định nghĩa tiêu đề
        self.tree.heading("id", text="Mã Sinh Viên (MSSV)")
        self.tree.heading("name", text="Họ và Tên")
        self.tree.heading("class", text="Lớp Hành Chính")
        self.tree.heading("created_at", text="Ngày Đăng Ký")
        
        # Định nghĩa kích thước cột
        self.tree.column("id", width=120, anchor="center")
        self.tree.column("name", width=200)
        self.tree.column("class", width=120, anchor="center")
        self.tree.column("created_at", width=150, anchor="center")
        
        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Double-click để sửa
        self.tree.bind("<Double-1>", lambda e: self.edit_student())
        
        # === STATUS BAR ===
        status_bar = tk.Label(
            self,
            text="Sẵn sàng",
            bg="#34495e",
            fg="white",
            anchor="w",
            font=("Segoe UI", 9)
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar = status_bar
        
        logger.info("✅ UI created successfully")

    def load_data(self):
        """Lấy dữ liệu từ DB và đổ vào bảng"""
        logger.info("🔄 Loading student data...")
        
        try:
            # Xóa dữ liệu cũ
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Lấy danh sách mới
            students = self.db.get_all_students()
            logger.info(f"📊 Found {len(students)} students")
            
            for s in students:
                student_id = s['student_id']
                self.tree.insert("", tk.END, values=(
                    student_id,
                    s['name'],
                    s['class_name'],
                    s['created_at'],
                ))
            
            # Cập nhật info label
            self.info_label.config(text=f"Tổng: {len(students)} sinh viên")
            self.status_bar.config(text=f"✅ Đã tải {len(students)} sinh viên")
            
        except Exception as e:
            logger.error(f"❌ Error loading data: {e}")
            messagebox.showerror("Lỗi", f"Không thể tải dữ liệu: {e}")

    def on_search_changed(self, *args):
        """Tự động lọc khi gõ vào ô tìm kiếm"""
        search_text = self.search_var.get().lower().strip()
        
        if not search_text:
            self.load_data()
            return
        
        logger.debug(f"🔍 Searching for: {search_text}")
        
        # Xóa dữ liệu cũ
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Lấy tất cả sinh viên
        students = self.db.get_all_students()
        
        # Lọc theo từ khóa
        filtered = []
        for s in students:
            if (search_text in s['student_id'].lower() or
                search_text in s['name'].lower() or
                search_text in s['class_name'].lower()):
                filtered.append(s)
        
        # Hiển thị kết quả
        for s in filtered:
            student_id = s['student_id']
            
            self.tree.insert("", tk.END, values=(
                student_id,
                s['name'],
                s['class_name'],
                s['created_at'],
            ))
        
        self.info_label.config(text=f"Tìm thấy: {len(filtered)} / {len(students)} sinh viên")

    def clear_search(self):
        """Xóa tìm kiếm"""
        self.search_var.set("")
        self.load_data()

    def search_student(self):
        """Hộp thoại tìm kiếm nâng cao"""
        search = simpledialog.askstring(
            "Tìm kiếm",
            "Nhập MSSV, Tên hoặc Lớp để tìm kiếm:"
        )
        
        if search:
            self.search_var.set(search)

    def delete_student(self):
        """Xóa sinh viên"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Chú ý", "Vui lòng chọn sinh viên cần xóa!")
            return
        
        item = self.tree.item(selected[0])
        student_id = str(item['values'][0])
        student_name = item['values'][1]
        
        logger.info(f"🗑️ Attempting to delete: {student_id} - {student_name}")
        
        confirm = messagebox.askyesno(
            "Xác nhận xóa",
            f"Bạn có chắc muốn xóa sinh viên:\n\n"
            f"📝 {student_name}\n"
            f"🆔 {student_id}\n\n"
            f"⚠️ Cảnh báo: Dữ liệu điểm danh và khuôn mặt cũng sẽ bị xóa vĩnh viễn!"
        )
        
        if confirm:
            try:
                # 1. Xóa trong DB
                if self.db.delete_student(student_id):
                    logger.info(f"✅ Deleted from DB: {student_id}")
                    
                    # 2. Xóa Vector khuôn mặt
                    self.encoder.remove_encoding(student_id)
                    logger.info(f"✅ Deleted face encoding: {student_id}")
                    
                    # 3. Load lại bảng
                    self.load_data()
                    
                    self.status_bar.config(text=f"✅ Đã xóa: {student_name}")
                    messagebox.showinfo("Thành công", f"Đã xóa sinh viên {student_name} khỏi hệ thống.")
                else:
                    logger.error(f"❌ Failed to delete from DB: {student_id}")
                    messagebox.showerror("Lỗi", "Không thể xóa dữ liệu trong Database.")
            except Exception as e:
                logger.error(f"❌ Delete error: {e}", exc_info=True)
                messagebox.showerror("Lỗi", f"Lỗi khi xóa: {e}")

    def edit_student(self):
        """Sửa thông tin sinh viên"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Chú ý", "Vui lòng chọn sinh viên cần sửa!")
            return
        
        item = self.tree.item(selected[0])
        current_id = str(item['values'][0])
        current_name = item['values'][1]
        current_class = item['values'][2]
        
        logger.info(f"✏️ Editing: {current_id}")
        
        # Tạo dialog sửa
        edit_dialog = tk.Toplevel(self)
        edit_dialog.title(f"Sửa thông tin - {current_id}")
        edit_dialog.geometry("400x250")
        edit_dialog.transient(self)
        edit_dialog.grab_set()
        
        # MSSV (Read-only)
        tk.Label(edit_dialog, text="Mã Sinh Viên:", font=("Segoe UI", 10)).pack(pady=5)
        id_entry = tk.Entry(edit_dialog, font=("Segoe UI", 10), width=30)
        id_entry.insert(0, current_id)
        id_entry.config(state="readonly")
        id_entry.pack(pady=5)
        
        # Tên
        tk.Label(edit_dialog, text="Họ và Tên:", font=("Segoe UI", 10)).pack(pady=5)
        name_entry = tk.Entry(edit_dialog, font=("Segoe UI", 10), width=30)
        name_entry.insert(0, current_name)
        name_entry.pack(pady=5)
        
        # Lớp
        tk.Label(edit_dialog, text="Lớp:", font=("Segoe UI", 10)).pack(pady=5)
        class_entry = tk.Entry(edit_dialog, font=("Segoe UI", 10), width=30)
        class_entry.insert(0, current_class)
        class_entry.pack(pady=5)
        
        def save_changes():
            new_name = name_entry.get().strip()
            new_class = class_entry.get().strip()
            
            if not new_name or not new_class:
                messagebox.showwarning("Cảnh báo", "Vui lòng điền đầy đủ thông tin!")
                return
            
            try:
                if self.db.update_student(current_id, new_name, new_class):
                    logger.info(f"✅ Updated: {current_id}")
                    self.load_data()
                    self.status_bar.config(text=f"✅ Đã cập nhật: {new_name}")
                    edit_dialog.destroy()
                    messagebox.showinfo("Thành công", "Cập nhật thông tin thành công!")
                else:
                    messagebox.showerror("Lỗi", "Cập nhật thất bại!")
            except Exception as e:
                logger.error(f"❌ Update error: {e}")
                messagebox.showerror("Lỗi", f"Lỗi: {e}")
        
        # Buttons
        btn_frame = tk.Frame(edit_dialog)
        btn_frame.pack(pady=20)
        
        tk.Button(
            btn_frame,
            text="💾 Lưu",
            command=save_changes,
            bg="#27ae60",
            fg="white",
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="❌ Hủy",
            command=edit_dialog.destroy,
            bg="#e74c3c",
            fg="white",
            width=10
        ).pack(side=tk.LEFT, padx=5)

    def export_data(self):
        """Xuất file Excel điểm danh"""
        logger.info("📊 Exporting to Excel...")
        
        try:
            success, path = self.db.export_excel()
            if success:
                logger.info(f"✅ Exported to: {path}")
                self.status_bar.config(text=f"✅ Đã xuất file: {path}")
                messagebox.showinfo(
                    "Xuất Excel thành công",
                    f"File đã được lưu tại:\n\n{path}\n\nBạn có thể mở file này bằng Excel."
                )
            else:
                logger.error(f"❌ Export failed: {path}")
                messagebox.showerror("Lỗi Xuất File", f"Chi tiết lỗi:\n{path}")
        except Exception as e:
            logger.error(f"❌ Export exception: {e}")
            messagebox.showerror("Lỗi", f"Không thể xuất file: {e}")

    def show_statistics(self):
        """Hiển thị thống kê"""
        logger.info("📈 Showing statistics...")
        
        try:
            students = self.db.get_all_students()
  
            
            total = len(students)
            
            # Thống kê theo lớp
            classes = {}
            for s in students:
                cls = s['class_name']
                classes[cls] = classes.get(cls, 0) + 1
            
            # Tạo dialog thống kê
            stats_window = tk.Toplevel(self)
            stats_window.title("📈 Thống kê")
            stats_window.geometry("500x400")
            stats_window.transient(self)
            
            tk.Label(
                stats_window,
                text="📊 THỐNG KÊ HỆ THỐNG",
                font=("Segoe UI", 16, "bold"),
                bg="#34495e",
                fg="white"
            ).pack(fill=tk.X, pady=10)
            
            info_text = f"""
            
📋 TỔNG QUAN:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Tổng số sinh viên:        {total}

👥 THỐNG KÊ THEO LỚP:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            for cls, count in sorted(classes.items()):
                info_text += f"   {cls}:  {count} sinh viên\n"
            
            text_widget = tk.Text(
                stats_window,
                font=("Consolas", 11),
                bg="#ecf0f1",
                wrap=tk.WORD
            )
            text_widget.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            text_widget.insert("1.0", info_text)
            text_widget.config(state="disabled")
            
            tk.Button(
                stats_window,
                text="✅ Đóng",
                command=stats_window.destroy,
                bg="#3498db",
                fg="white",
                font=("Segoe UI", 10),
                width=15
            ).pack(pady=10)
            
        except Exception as e:
            logger.error(f"❌ Statistics error: {e}")
            messagebox.showerror("Lỗi", f"Không thể tạo thống kê: {e}")

    def on_window_close(self):
        """Đóng cửa sổ"""
        logger.info("🔙 Closing User Management Window")
        self.destroy()
        self.on_close_callback()