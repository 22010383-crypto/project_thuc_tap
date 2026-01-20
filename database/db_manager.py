import sqlite3
import pandas as pd
import os
from datetime import datetime
from app.config import Config

class DatabaseManager:
    def __init__(self):
        self.db_path = Config.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(Config.EXPORT_DIR, exist_ok=True)
        self.init_db()

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_conn()
        
        # Bảng Sinh Viên (Student)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                class_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Bảng Nhật ký (Attendance) - Thêm môn học
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_str TEXT NOT NULL,
                subject TEXT,
                FOREIGN KEY(student_id) REFERENCES students(student_id)
            );
        """)
        conn.commit()
        conn.close()

    def add_student(self, student_id, name, class_name):
        conn = self.get_conn()
        try:
            conn.execute("INSERT INTO students (student_id, name, class_name) VALUES (?, ?, ?)",
                         (student_id, name, class_name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def delete_student(self, student_id):
        conn = self.get_conn()
        try:
            conn.execute("DELETE FROM attendance_logs WHERE student_id = ?", (student_id,))
            conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def log_attendance(self, student_id, subject="General"):
        conn = self.get_conn()
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        try:
            conn.execute(
                "INSERT INTO attendance_logs (student_id, checkin_time, date_str, subject) VALUES (?, ?, ?, ?)",
                (student_id, now, date_str, subject)
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def export_excel(self):
        conn = self.get_conn()
        try:
            query = """
            SELECT a.student_id, s.name, s.class_name, a.subject, a.checkin_time
            FROM attendance_logs a
            JOIN students s ON a.student_id = s.student_id
            ORDER BY a.checkin_time DESC
            """
            df = pd.read_sql_query(query, conn)
            filename = f"Attendance_List_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            path = os.path.join(Config.EXPORT_DIR, filename)
            df.to_excel(path, index=False)
            return True, path
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()
            
    def get_all_students(self):
        """Lấy danh sách toàn bộ sinh viên"""
        conn = self.get_conn()
        try:
            cursor = conn.execute("SELECT * FROM students ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []
        finally:
            conn.close()

    def update_student(self, student_id, name, class_name):
        """Cập nhật thông tin sinh viên"""
        conn = self.get_conn()
        try:
            conn.execute("UPDATE students SET name = ?, class_name = ? WHERE student_id = ?", 
                         (name, class_name, student_id))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()