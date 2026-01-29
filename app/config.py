import os

class Config:
    # --- ĐƯỜNG DẪN HỆ THỐNG ---
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Nơi chứa dữ liệu
    DATA_DIR = os.path.join(BASE_DIR, "data")
    DB_PATH = os.path.join(DATA_DIR, "database", "attendance.db")
    ENCODINGS_PATH = os.path.join(DATA_DIR, "encodings", "face_encodings.pkl")
    EXPORT_DIR = os.path.join(BASE_DIR, "exports") 
    
    # Nơi chứa các file thuật toán bổ trợ  
    MODELS_DIR = os.path.join(BASE_DIR, "models")
    SHAPE_PREDICTOR_PATH = os.path.join(MODELS_DIR, "shape_predictor_68_face_landmarks.dat")
    LOG_PATH = os.path.join(BASE_DIR, "logs", "app.log") 
    
    # --- CẤU HÌNH CAMERA ---
    CAMERA_INDEX = 0      # 0 là webcam mặc định
    FRAME_WIDTH = 640     # 640x480 là chuẩn vàng cho tốc độ thực
    FRAME_HEIGHT = 480
    FPS = 30

    # --- THAM SỐ THUẬT TOÁN (CORE) ---
    DETECTION_MODEL = "hog"  
    RESIZE_SCALE = 0.5       # Resize 50% để AI chạy nhanh
    MATCH_TOLERANCE = 0.45   # Ngưỡng nhận diện (Càng thấp càng khắt khe)
    
    # --- ACTIVE LIVENESS (HÀNH ĐỘNG) ---
    EYE_AR_THRESH = 0.21        # Ngưỡng nhắm mắt
    EYE_AR_CONSEC_FRAMES = 2    # Số frame nhắm liên tiếp
    YAW_THRESH = 18.0           # Góc quay đầu (độ)

    # Tự động tạo thư mục nếu chưa có
    for d in [DATA_DIR, os.path.dirname(DB_PATH), os.path.dirname(ENCODINGS_PATH), EXPORT_DIR, MODELS_DIR, os.path.dirname(LOG_PATH)]:
        os.makedirs(d, exist_ok=True)