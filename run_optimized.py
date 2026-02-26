#!/usr/bin/env python3
"""
Run Optimized Attendance System
================================
Launch the highly optimized version with 25-30 FPS.
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s | %(name)-25s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Check database first
from database.db_manager import DatabaseManager
from app.config import Config

def check_database():
    """Check if database has new columns."""
    import sqlite3
    
    if not os.path.exists(Config.DB_PATH):
        logger.warning("⚠️  No database found, will create new one")
        return True
    
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.execute("PRAGMA table_info(attendance_logs)")
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    
    if 'confidence_score' not in columns:
        logger.error("❌ Database schema outdated!")
        logger.error("Run: python quick_fix.py")
        return False
    
    logger.info("✅ Database schema OK")
    return True

def main():
    """Main entry point."""
    print("\n" + "=" * 70)
    print("🚀 OPTIMIZED FACE ATTENDANCE SYSTEM")
    print("Performance: 25-30 FPS Display | 10-15 FPS AI Processing")
    print("=" * 70 + "\n")
    
    # Check database
    if not check_database():
        print("\n❌ Please fix database first:")
        print("   python quick_fix.py")
        return
    
    # Import GUI
    from app.gui.attendance_window_optimized import AttendanceWindowOptimized
    
    # Create root window (hidden)
    root = tk.Tk()
    root.withdraw()
    
    def on_close():
        logger.info("👋 Application closed")
        root.quit()
    
    # Create attendance window
    try:
        window = AttendanceWindowOptimized(root, on_close)
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to start: {e}")

if __name__ == "__main__":
    main()
