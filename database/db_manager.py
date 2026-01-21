import sqlite3
import pandas as pd
import os
from datetime import datetime
from app.config import Config
import logging

# Sử dụng root logger
logger = logging.getLogger(__name__)
logger.info("📦 Module db_manager imported")

class DatabaseManager:
    def __init__(self):
        self.db_path = Config.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(Config.EXPORT_DIR, exist_ok=True)
        self.init_db()
        logger.info(f"✅ DatabaseManager initialized: {self.db_path}")

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_conn()
        # 1. Bảng Sinh Viên
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # 2. Bảng Phiên Học (Session)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_name TEXT NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP
            );
        """)
        # 3. Bảng Nhật Ký (Logs) - Có ràng buộc UNIQUE để tránh trùng
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verification_method TEXT DEFAULT 'Auto',
                FOREIGN KEY(session_id) REFERENCES sessions(session_id),
                FOREIGN KEY(student_id) REFERENCES students(student_id),
                UNIQUE(session_id, student_id)
            );
        """)
        conn.commit()
        conn.close()

    # --- QUẢN LÝ SINH VIÊN ---
    def add_student(self, sid, name, cls):
        conn = self.get_conn()
        try:
            conn.execute("INSERT INTO students (student_id, name, class_name) VALUES (?, ?, ?)", (sid, name, cls))
            conn.commit()
            logger.info(f"✅ Added student: {sid}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"⚠️ Student {sid} already exists")
            return False
        finally:
            conn.close()

    def get_all_students(self):
        conn = self.get_conn()
        res = conn.execute("SELECT * FROM students ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in res]

    def delete_student(self, sid):
        conn = self.get_conn()
        try:
            conn.execute("DELETE FROM attendance_logs WHERE student_id = ?", (sid,))
            conn.execute("DELETE FROM students WHERE student_id = ?", (sid,))
            conn.commit()
            logger.info(f"✅ Deleted student: {sid}")
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting student {sid}: {e}")
            return False
        finally:
            conn.close()

    def update_student(self, sid, name, cls):
        conn = self.get_conn()
        try:
            conn.execute("UPDATE students SET name=?, class_name=? WHERE student_id=?", (name, cls, sid))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    # --- QUẢN LÝ ĐIỂM DANH (SESSION) ---
    def create_session(self, subject):
        """Tạo phiên học mới, trả về Session ID"""
        conn = self.get_conn()
        cursor = conn.execute("INSERT INTO sessions (subject_name) VALUES (?)", (subject,))
        conn.commit()
        session_id = cursor.lastrowid
        conn.close()
        logger.info(f"✅ Created session #{session_id}: {subject}")
        return session_id

    def mark_attendance(self, session_id, student_id, method="Auto"):
        """Điểm danh. Nếu đã có trong phiên này rồi thì trả về False (Bỏ qua)"""
        conn = self.get_conn()
        try:
            conn.execute(
                "INSERT INTO attendance_logs (session_id, student_id, verification_method) VALUES (?, ?, ?)",
                (session_id, student_id, method)
            )
            conn.commit()
            logger.info(f"✅ Attendance marked: Session#{session_id}, Student={student_id}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"⚠️ Student {student_id} already marked in session #{session_id}")
            return False
        finally:
            conn.close()
    
    # THÊM ALIAS để tương thích với code cũ
    def log_attendance(self, student_id, method="Auto", session_id=None):
        """
        Alias method cho mark_attendance để tương thích với code cũ.
        Nếu không truyền session_id, sẽ tự động tạo session mới.
        """
        if session_id is None:
            # Tìm session đang active (chưa end_time)
            conn = self.get_conn()
            result = conn.execute(
                "SELECT session_id FROM sessions WHERE end_time IS NULL ORDER BY start_time DESC LIMIT 1"
            ).fetchone()
            conn.close()
            
            if result:
                session_id = result[0]
                logger.debug(f"📌 Using active session #{session_id}")
            else:
                # Tạo session mới
                session_id = self.create_session("Auto Attendance")
                logger.info(f"📌 Created new auto session #{session_id}")
        
        return self.mark_attendance(session_id, student_id, method)
            
    def close_session(self, session_id):
        conn = self.get_conn()
        conn.execute("UPDATE sessions SET end_time = CURRENT_TIMESTAMP WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        logger.info(f"🔒 Closed session #{session_id}")

    def export_excel(self):
        conn = self.get_conn()
        try:
            query = """
            SELECT s.subject_name, l.checkin_time, st.student_id, st.name, st.class_name
            FROM attendance_logs l
            JOIN sessions s ON l.session_id = s.session_id
            JOIN students st ON l.student_id = st.student_id
            ORDER BY l.checkin_time DESC
            """
            df = pd.read_sql_query(query, conn)
            path = os.path.join(Config.EXPORT_DIR, f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            df.to_excel(path, index=False)
            logger.info(f"📊 Exported to {path}")
            return True, path
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            return False, str(e)
        finally:
            conn.close()