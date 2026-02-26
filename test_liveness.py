"""
Test Script: Advanced Liveness Detector
========================================
Standalone test for liveness detection without full system.
"""

import cv2
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from core.advanced_liveness_detector import LivenessDetector
import face_recognition


def main():
    """Test liveness detector with webcam."""
    logger.info("=" * 60)
    logger.info("Testing Advanced Liveness Detector")
    logger.info("=" * 60)
    
    # Initialize
    detector = LivenessDetector(
        ear_threshold=0.25,
        blink_consec_frames=3,
        head_pose_threshold=15.0,
        blur_threshold=100.0
    )
    
    # Open webcam
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        logger.error("❌ Cannot open camera")
        return
    
    logger.info("✅ Camera opened")
    logger.info("📹 Press 'q' to quit, 'r' to reset detector state")
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        display_frame = frame.copy()
        
        # Simple face detection (HOG)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        
        if len(face_locations) > 0:
            # Get first face
            face_box = face_locations[0]
            top, right, bottom, left = face_box
            
            # Analyze liveness
            result = detector.analyze(frame, face_box)
            
            # Draw bounding box
            if result['is_real']:
                color = (0, 255, 0)  # Green
                status_text = "LIVE"
            else:
                color = (0, 0, 255)  # Red
                status_text = "FAKE"
            
            cv2.rectangle(display_frame, (left, top), (right, bottom), color, 2)
            
            # Draw info
            y_offset = top - 10
            
            # Status
            cv2.putText(display_frame, f"{status_text} ({result['score']:.2f})", 
                       (left, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Active liveness details
            if 'details' in result and 'active' in result['details']:
                active = result['details']['active']
                
                info_lines = [
                    f"EAR: {active.get('ear', 0):.3f}",
                    f"Yaw: {active.get('yaw', 0):.1f}°",
                    f"Pitch: {active.get('pitch', 0):.1f}°",
                    f"Blinks: {active.get('blink_count', 0)}",
                ]
                
                y_pos = bottom + 30
                for line in info_lines:
                    cv2.putText(display_frame, line, (left, y_pos),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    y_pos += 20
            
            # Passive liveness details
            if 'details' in result and 'passive' in result['details']:
                passive = result['details']['passive']
                
                passive_lines = [
                    f"Blur: {passive.get('blur_score', 0):.1f}",
                    f"Glare: {passive.get('glare_score', 0):.2f}",
                    f"Freq: {passive.get('frequency_score', 0):.2f}",
                ]
                
                y_pos = bottom + 30
                x_pos = right + 10
                for line in passive_lines:
                    cv2.putText(display_frame, line, (x_pos, y_pos),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    y_pos += 20
            
            # Reason
            if not result['is_real']:
                cv2.putText(display_frame, f"Reason: {result['reason']}", 
                           (10, display_frame.shape[0] - 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        else:
            cv2.putText(display_frame, "No face detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Instructions
        cv2.putText(display_frame, "Press 'q' to quit, 'r' to reset", (10, display_frame.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        cv2.imshow("Liveness Detector Test", display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            logger.info("👋 Quitting...")
            break
        elif key == ord('r'):
            detector.reset()
            logger.info("🔄 Detector state reset")
    
    cap.release()
    cv2.destroyAllWindows()
    logger.info("✅ Test completed")


if __name__ == "__main__":
    main()
