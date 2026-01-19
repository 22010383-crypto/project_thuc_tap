import cv2
import threading
import queue
import time

class VideoStream:
    def __init__(self, src=0, width=640, height=480):
        self.src = src
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        # Hàng đợi chỉ chứa 1 frame mới nhất để tránh lag (drop frame cũ)
        self.q = queue.Queue(maxsize=1)
        self.stopped = False

    def start(self):
        t = threading.Thread(target=self.update, daemon=True)
        t.start()
        return self

    def update(self):
        while not self.stopped:
            if not self.q.full():
                ret, frame = self.stream.read()
                if not ret:
                    self.stop()
                    return
                self.q.put(frame)
            else:
                # Nếu queue đầy, chờ một chút để thread chính kịp lấy ra
                time.sleep(0.01)

    def read(self):
        return self.q.get() if not self.q.empty() else None

    def stop(self):
        self.stopped = True
        self.stream.release()