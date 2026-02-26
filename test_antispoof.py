"""
Test Script: Silent Face Anti-Spoofing
======================================
Test anti-spoofing detector with webcam.
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

from core.silent_face_antispoof import SilentFaceAntiSpoof, HybridLivenessDetector
import face_recognition


def test_silent_mode():
    """Test Silent Anti-Spoofing (no user action)."""
    logger.info("=" * 60)
    logger.info("Testing Silent Face Anti-Spoofing")
    logger.info("=" * 60)
    
    # Initialize
    detector = SilentFaceAntiSpoof(
        blur_threshold=100.0,
        lbp_threshold=50.0,
        frequency_threshold=0.15,
        color_diversity_threshold=20.0
    )
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        logger.error("❌ Cannot open camera")
        return
    
    logger.info("✅ Camera opened")
    logger.info("📹 Press 'q' to quit")
    logger.info("=" * 60)
    logger.info("🔬 Test Cases:")
    logger.info("  1. Real face → Should show GREEN")
    logger.info("  2. Phone photo → Should show RED + reason")
    logger.info("  3. Screen replay → Should show RED + Moiré detected")
    logger.info("=" * 60)
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        display_frame = frame.copy()
        
        # Detect face
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        
        if len(face_locations) > 0:
            # Get first face
            top, right, bottom, left = face_locations[0]
            face_region = frame[top:bottom, left:right]
            
            # Anti-spoofing detection
            result = detector.detect(face_region)
            
            # Draw box
            if result['is_real']:
                color = (0, 255, 0)  # Green
                status = f"REAL ({result['score']:.2f})"
            else:
                color = (0, 0, 255)  # Red
                status = f"FAKE ({result['score']:.2f})"
            
            cv2.rectangle(display_frame, (left, top), (right, bottom), color, 2)
            
            # Status text
            cv2.putText(display_frame, status, (left, top - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # Reason (if fake)
            if not result['is_real']:
                y_pos = bottom + 30
                for line in result['reason'].split(';'):
                    cv2.putText(display_frame, line.strip(), (left, y_pos),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                    y_pos += 20
            
            # Detailed scores
            details = result['details']
            info_x = right + 20
            info_y = top
            
            cv2.putText(display_frame, "Checks:", (info_x, info_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            info_y += 25
            
            for check_name, check_data in details.items():
                if isinstance(check_data, dict):
                    passed = check_data.get('passed', False) or not check_data.get('detected', True)
                    icon = "✓" if passed else "✗"
                    score = check_data.get('score', 0.0)
                    
                    check_color = (0, 255, 0) if passed else (0, 0, 255)
                    text = f"{icon} {check_name}: {score:.2f}"
                    
                    cv2.putText(display_frame, text, (info_x, info_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, check_color, 1)
                    info_y += 20
        
        else:
            cv2.putText(display_frame, "No face detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Instructions
        cv2.putText(display_frame, "Press 'q' to quit", (10, display_frame.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        cv2.imshow("Silent Anti-Spoofing Test", display_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    logger.info("✅ Test completed")


def test_hybrid_mode():
    """Test Hybrid mode (action + passive)."""
    logger.info("=" * 60)
    logger.info("Testing Hybrid Liveness Detector")
    logger.info("=" * 60)
    
    detector = HybridLivenessDetector(require_action=True)
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        logger.error("❌ Cannot open camera")
        return
    
    logger.info("✅ Camera opened")
    logger.info("📹 Hybrid mode: Requires blink OR head turn + anti-spoofing")
    logger.info("Press 'q' to quit, 'r' to reset")
    
    from core.liveness_detector import ActionLivenessDetector
    action_detector = ActionLivenessDetector()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        display_frame = frame.copy()
        
        # Detect face
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        
        if len(face_locations) > 0:
            face_box = face_locations[0]
            top, right, bottom, left = face_box
            
            # Get active data
            action_result = action_detector.analyze_action(frame, face_box)
            
            active_data = None
            if action_result['valid']:
                active_data = {
                    'ear': action_result['ear'],
                    'yaw': action_result['yaw']
                }
            
            # Hybrid detection
            result = detector.detect(frame, face_box, active_data)
            
            # Draw
            color = (0, 255, 0) if result['is_real'] else (0, 0, 255)
            cv2.rectangle(display_frame, (left, top), (right, bottom), color, 2)
            
            # Status
            status = f"{result['confidence'].upper()}: {result['score']:.2f}"
            cv2.putText(display_frame, status, (left, top - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Active status
            active_details = result.get('active_details', {})
            blink_count = active_details.get('blink_count', 0)
            
            info_y = bottom + 30
            cv2.putText(display_frame, f"Blinks: {blink_count}", (left, info_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Reason
            if not result['is_real']:
                cv2.putText(display_frame, result['reason'], (left, info_y + 25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        cv2.putText(display_frame, "Press 'q' to quit, 'r' to reset", 
                   (10, display_frame.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        cv2.imshow("Hybrid Liveness Test", display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            detector.reset()
            logger.info("🔄 Detector reset")
    
    cap.release()
    cv2.destroyAllWindows()
    logger.info("✅ Test completed")


def main():
    """Main menu."""
    print("\n" + "=" * 60)
    print("Silent Face Anti-Spoofing Test")
    print("=" * 60)
    print("\n1. Silent Mode (No user action)")
    print("2. Hybrid Mode (Blink/Head turn + Anti-spoofing)")
    print("\nQ. Quit")
    
    choice = input("\nSelect mode (1/2): ").strip()
    
    if choice == '1':
        test_silent_mode()
    elif choice == '2':
        test_hybrid_mode()
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    main()
