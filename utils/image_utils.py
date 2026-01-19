import cv2
from PIL import Image, ImageTk

def cv2_to_pil(frame, width=None, height=None):
    """Chuyển đổi frame OpenCV sang ảnh hiển thị được trên Tkinter"""
    # Convert màu BGR -> RGB
    color_converted = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Tạo đối tượng PIL Image
    pil_image = Image.fromarray(color_converted)
    
    # Resize nếu cần
    if width and height:
        pil_image = pil_image.resize((width, height), Image.Resampling.LANCZOS)
        
    # Chuyển sang ImageTk
    return ImageTk.PhotoImage(pil_image)