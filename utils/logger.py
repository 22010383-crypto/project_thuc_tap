import logging
import os
from logging.handlers import RotatingFileHandler
from app.config import Config

def setup_logger(name="FaceAttendance"):
    # Đảm bảo thư mục logs tồn tại
    log_dir = os.path.dirname(Config.LOG_PATH)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Tránh duplicate log khi gọi hàm nhiều lần
    if logger.hasHandlers():
        return logger

    # 1. Ghi log ra file (Tự động xoay file khi đầy 5MB, giữ lại 3 file cũ)
    file_handler = RotatingFileHandler(Config.LOG_PATH, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # 2. Ghi log ra màn hình Console
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    # Thêm handlers vào logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger