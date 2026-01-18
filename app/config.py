import os

class Config:
    # --- ĐƯỜNG DẪN HỆ THỐNG ---
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Nơi chứa dữ liệu
    DATA_DIR = os.path.join(BASE_DIR, "data")
    DB_PATH = os.path.join(DATA_DIR, "database", "attendance.db")
    ENCODINGS_PATH = os.path.join(DATA_DIR, "encodings", "face_encodings.pkl")
    FACES_STORAGE_DIR = os.path.join(DATA_DIR, "faces")
    EXPORT_DIR = os.path.join(BASE_DIR, "exports") # <--- MỚI
    
    # Nơi chứa các file thuật toán bổ trợ (nếu có)
    MODELS_DIR = os.path.join(BASE_DIR, "models")
    SHAPE_PREDICTOR_PATH = os.path.join(MODELS_DIR, "shape_predictor_68_face_landmarks.dat")
    LOG_PATH = os.path.join(BASE_DIR, "logs", "app.log")  # <--- THÊM DÒNG NÀY
    
    # --- CẤU HÌNH CAMERA ---
    CAMERA_INDEX = 0      # 0 là webcam mặc định
    FRAME_WIDTH = 640     # Giảm xuống 640x480 để tối ưu tốc độ CPU
    FRAME_HEIGHT = 480
    FPS = 30

    # --- THAM SỐ THUẬT TOÁN (CORE) ---
    DETECTION_MODEL = "hog"  # "hog" chạy trên CPU, "cnn" cần GPU
    RESIZE_SCALE = 0.5       # Resize ảnh nhỏ đi 50% trước khi xử lý (Tăng tốc gấp 4 lần)
    
    # Ngưỡng so sánh Vector (0.0 -> 1.0)
    # Càng thấp càng chặt chẽ (ít nhận nhầm nhưng khó nhận hơn)
    MATCH_TOLERANCE = 0.5    
    
    # --- CẤU HÌNH ĐIỂM DANH ---
    COOLDOWN_SECONDS = 60    # Thời gian chờ giữa 2 lần điểm danh liên tiếp (tránh spam)