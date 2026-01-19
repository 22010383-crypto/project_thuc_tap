import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from app.config import Config

def setup_logger(name="FaceApp"):
    log_dir = os.path.dirname(Config.LOG_PATH)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG) # Bắt tất cả mọi level lỗi

    if logger.hasHandlers():
        return logger

    # Format log chi tiết: Thời gian - Tên Module - Mức độ - Nội dung
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )

    file_handler = RotatingFileHandler(
        Config.LOG_PATH, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger