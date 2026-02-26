#!/usr/bin/env python3
"""
Test anti-spoofing thresholds
"""
import cv2
import numpy as np
from core.realtime_engine import RealtimeAntiSpoof
import logging

logging.basicConfig(level=logging.DEBUG)

detector = RealtimeAntiSpoof()

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print("=" * 60)
print("ANTI-SPOOFING TEST")
print("=" * 60)
print("Hướng camera vào:")
print("  1. Mặt thật -> Xem scores")
print("  2. Ảnh điện thoại -> Xem scores")
print("  3. So sánh Texture score (ảnh thường < 0.3)")
print()
print("Press 'q' to quit")
print("=" * 60)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Detect face (simple)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    for (x, y, w, h) in faces:
        face_roi = frame[y:y+h, x:x+w]
        
        if face_roi.size > 0:
            result = detector.check(face_roi)
            
            color = (0, 255, 0) if result['is_real'] else (0, 0, 255)
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            
            # Display scores
            y_offset = y - 10
            cv2.putText(frame, f"Real: {result['is_real']}", (x, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            y_offset -= 20
            cv2.putText(frame, f"Score: {result['score']:.2f}", (x, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y_offset -= 20
            cv2.putText(frame, f"Blur: {result['blur']:.2f}", (x, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y_offset -= 20
            cv2.putText(frame, f"Texture: {result['texture']:.2f}", (x, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y_offset -= 20
            cv2.putText(frame, f"Freq: {result['freq']:.2f}", (x, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Console output
            status = "✓ REAL" if result['is_real'] else "✗ FAKE"
            print(f"{status} | Blur={result['blur']:.2f} Texture={result['texture']:.2f} Freq={result['freq']:.2f} Final={result['score']:.2f}")
    
    cv2.imshow("Anti-spoofing Test", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

print("\nThresholds hiện tại:")
print("  - Final >= 0.60")
print("  - Texture >= 0.35 (ảnh thường < 0.3)")
print("  - Blur >= 0.25")
