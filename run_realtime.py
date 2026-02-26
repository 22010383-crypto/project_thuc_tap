#!/usr/bin/env python3
"""
Quick launch - Real-time Attendance System
"""
import sys
import os
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.gui.realtime_attendance import RealtimeAttendanceWindow
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    root = tk.Tk()
    root.withdraw()
    
    def on_close():
        root.quit()
    
    RealtimeAttendanceWindow(root, on_close)
    
    root.mainloop()

if __name__ == "__main__":
    main()
