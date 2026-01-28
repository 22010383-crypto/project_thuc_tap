import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from app.config import Config

def setup_logger(name="FaceApp"):
    """
    Setup logger với output ra BOTH console và file
    """
    # Tạo thư mục logs nếu chưa có
    log_dir = os.path.dirname(Config.LOG_PATH)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Bắt tất cả level

    # Tránh duplicate handlers
    if logger.hasHandlers():
        return logger

    # Format log với emoji và màu sắc
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%H:%M:%S'
    )

    # 1. File Handler (lưu full log)
    file_handler = RotatingFileHandler(
        Config.LOG_PATH, 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3, 
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # 2. Console Handler (hiển thị real-time)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)  # Chỉ hiện INFO trở lên

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def setup_all_loggers():
    """
    Setup logging cho TẤT CẢ modules trong app
    Gọi hàm này 1 lần duy nhất khi khởi động
    """
    # Root logger (bắt tất cả)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Tạo thư mục logs
    log_dir = os.path.dirname(Config.LOG_PATH)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Xóa handlers cũ (nếu có)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Format chung
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s | %(name)-25s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # File Handler
    file_handler = RotatingFileHandler(
        Config.LOG_PATH,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Console Handler với màu
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Tắt logging của thư viện bên ngoài (giảm nhiễu)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    
    print("=" * 80)
    print("✅ LOGGING SYSTEM INITIALIZED")
    print(f"📁 Log file: {Config.LOG_PATH}")
    print("=" * 80)
    
    return root_logger