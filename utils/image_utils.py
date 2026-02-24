import cv2
import numpy as np

try:
    from PIL import Image, ImageTk
    HAS_IMAGETK = True
except ImportError:
    try:
        from PIL import Image
        ImageTk = None
        HAS_IMAGETK = False
    except ImportError:
        Image = None
        ImageTk = None
        HAS_IMAGETK = False

def cv2_to_pil(frame, width=None, height=None):
    """Chuyển đổi frame OpenCV sang ảnh hiển thị được trên Tkinter"""
    if Image is None:
        raise ImportError("PIL not available. Install: pip install --break-system-packages Pillow")
    
    # Convert màu BGR -> RGB
    color_converted = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Tạo đối tượng PIL Image
    pil_image = Image.fromarray(color_converted)
    
    # Resize nếu cần
    if width and height:
        pil_image = pil_image.resize((width, height), Image.Resampling.LANCZOS)
    
    # Return PIL Image if no ImageTk
    if not HAS_IMAGETK or ImageTk is None:
        return pil_image
        
    # Chuyển sang ImageTk
    return ImageTk.PhotoImage(pil_image)
