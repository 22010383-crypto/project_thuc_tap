import sqlite3
import pandas as pd  
import os
from datetime import datetime
from app.config import Config
from utils.logger import setup_logger

logger = setup_logger("DB_Manager")

class DatabaseManager:
    def __init__(self):
        self.db_path = Config.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(Config.EXPORT_DIR, exist_ok=True) # Tạo folder export
        self.init_db()

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        try:
            conn = self.get_conn()
            schema = """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS attendance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_str TEXT NOT NULL,
                status TEXT DEFAULT 'Present',
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
            conn.executescript(schema)
            conn.commit()
            conn.close()
            logger.info("Khởi tạo CSDL thành công.")
        except Exception as e:
            logger.error(f"Failed to init DB: {e}") 

    def add_user(self, user_id, name, department):
        conn = self.get_conn()
        try:
            conn.execute("INSERT INTO users (id, name, department) VALUES (?, ?, ?)",
                         (user_id, name, department))
            conn.commit()
            logger.info(f"Added new user: {name} ({user_id})")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"User ID {user_id} already exists.")
            return False
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
        finally:
            conn.close()

    def log_attendance(self, user_id):
        conn = self.get_conn()
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        
        try:
            conn.execute(
                "INSERT INTO attendance_logs (user_id, checkin_time, date_str) VALUES (?, ?, ?)",
                (user_id, now, date_str)
            )
            conn.commit()
            logger.info(f"Attendance logged for {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error logging attendance for {user_id}: {e}")
            return False
        finally:
            conn.close()

    def get_last_checkin(self, user_id):
        """Lấy lần điểm danh gần nhất để tính cooldown"""
        conn = self.get_conn()
        cursor = conn.execute(
            "SELECT checkin_time FROM attendance_logs WHERE user_id = ? ORDER BY checkin_time DESC LIMIT 1",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return datetime.fromisoformat(row['checkin_time'])
        return None
    
    def get_all_users(self):
        """Lấy danh sách tất cả sinh viên"""
        conn = self.get_conn()
        try:
            cursor = conn.execute("SELECT * FROM users ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_user(self, user_id):
        """Xóa sinh viên và log liên quan"""
        conn = self.get_conn()
        try:
            conn.execute("DELETE FROM attendance_logs WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            logger.info(f"Deleted user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False
        finally:
            conn.close()

    def update_user(self, user_id, name, department):
        """Cập nhật thông tin sinh viên"""
        conn = self.get_conn()
        try:
            conn.execute("UPDATE users SET name = ?, department = ? WHERE id = ?", 
                         (name, department, user_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return False
        finally:
            conn.close()

    def export_attendance_to_excel(self):
        """Xuất dữ liệu điểm danh ra Excel"""
        conn = self.get_conn()
        try:
            query = """
            SELECT a.id, a.user_id, u.name, u.department, a.checkin_time, a.status 
            FROM attendance_logs a
            JOIN users u ON a.user_id = u.id
            ORDER BY a.checkin_time DESC
            """
            df = pd.read_sql_query(query, conn)
            
            # Tạo tên file theo thời gian
            filename = f"Attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = os.path.join(Config.EXPORT_DIR, filename)
            
            df.to_excel(filepath, index=False)
            logger.info(f"Exported report to {filepath}")
            return True, filepath
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False, str(e)
        finally:
            conn.close()