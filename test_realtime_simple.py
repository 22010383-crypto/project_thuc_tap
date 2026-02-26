#!/usr/bin/env python3
"""
Simple test - Check if realtime engine works
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pickle
from app.config import Config

print("=" * 60)
print("TESTING REALTIME ENGINE")
print("=" * 60)

# Test 1: Load encodings
print("\n1. Loading encodings...")
try:
    with open(Config.ENCODINGS_PATH, 'rb') as f:
        data = pickle.load(f)
        print(f"   Keys in pickle: {data.keys()}")
        
        encodings = data.get('encodings', [])
        ids = data.get('ids', data.get('person_ids', []))
        
        print(f"   ✓ Encodings: {len(encodings)}")
        print(f"   ✓ IDs: {ids}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

# Test 2: Import engine
print("\n2. Importing realtime engine...")
try:
    from core.realtime_engine import RealtimeRecognitionEngine, RealtimeAntiSpoof
    print("   ✓ Import OK")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Initialize engine
print("\n3. Initializing engine...")
try:
    engine = RealtimeRecognitionEngine(encodings, ids, use_antispoof=True)
    print(f"   ✓ Engine initialized")
    print(f"   - Known faces: {len(engine.known_ids)}")
    print(f"   - Encodings shape: {engine.known_encodings.shape if len(engine.known_encodings) > 0 else 'empty'}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Test with dummy frame
print("\n4. Testing with dummy frame...")
try:
    import numpy as np
    import cv2
    
    # Create dummy frame
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    results = engine.process_frame(dummy_frame)
    print(f"   ✓ Process OK (results: {len(results)})")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Import GUI
print("\n5. Testing GUI import...")
try:
    from app.gui.realtime_attendance import RealtimeAttendanceWindow
    print("   ✓ GUI import OK")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ ALL TESTS PASSED")
print("=" * 60)
print("\nYou can now run: python run_realtime.py")
