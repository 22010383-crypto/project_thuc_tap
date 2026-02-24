import os

class Config:
    # --- PATHS ---
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    DB_PATH = os.path.join(DATA_DIR, "database", "attendance.db")
    ENCODINGS_PATH = os.path.join(DATA_DIR, "encodings", "face_encodings.pkl")
    EXPORT_DIR = os.path.join(BASE_DIR, "exports")
    
    MODELS_DIR = os.path.join(BASE_DIR, "models")
    SHAPE_PREDICTOR_PATH = os.path.join(MODELS_DIR, "shape_predictor_68_face_landmarks.dat")
    
    # LOG PATH
    LOG_PATH = os.path.join(BASE_DIR, "logs", "app.log")
    
    # --- CAMERA ---
    CAMERA_INDEX = 0 
    FRAME_WIDTH = 1280 
    FRAME_HEIGHT = 720
    FPS = 30
    
    # --- PERFORMANCE ---
    # Giảm xuống 0.4 hoặc 0.3 nếu máy yếu
    RESIZE_SCALE = 0.5 
    
    # --- AI CORE ---
    DETECTION_MODEL = "hog"  # hoặc "cnn" nếu có GPU
    MATCH_TOLERANCE = 0.45 
    
    # --- ACTIVE LIVENESS (HÀNH ĐỘNG) ---
    # 1. CHỚP MẮT (Eye Aspect Ratio - EAR)
    # Nếu EAR < 0.23: Mắt đang nhắm
    EYE_AR_THRESH = 0.23
    # Số frame liên tiếp nhắm mắt
    EYE_AR_CONSEC_FRAMES = 2
    
    # 2. QUAY ĐẦU (Head Pose)
    # Góc quay trái/phải tối thiểu
    YAW_THRESH = 20.0  # độ
    
    @classmethod
    def ensure_dirs(cls):
        """Tạo tất cả thư mục cần thiết"""
        dirs = [
            cls.DATA_DIR,
            os.path.dirname(cls.DB_PATH),
            os.path.dirname(cls.ENCODINGS_PATH),
            cls.EXPORT_DIR,
            cls.MODELS_DIR,
            os.path.dirname(cls.LOG_PATH)
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

# Tự động tạo thư mục khi import
Config.ensure_dirs()