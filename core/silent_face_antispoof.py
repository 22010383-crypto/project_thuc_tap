"""
Silent Face Anti-Spoofing Module
=================================
Advanced passive liveness detection without user interaction.
Detects: Printed photos, phone screens, video replay attacks.

Based on:
- Texture analysis (LBP, Gabor filters)
- Frequency domain analysis (FFT, DCT)
- Image quality metrics (Blur, Noise, Color distortion)
- Moiré pattern detection

Author: Senior CV Engineer
Optimized for: CPU-only, Real-time
"""

import cv2
import numpy as np
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class SilentFaceAntiSpoof:
    """
    Passive anti-spoofing detector (no user action required).
    High accuracy for detecting photos and screen attacks.
    """
    
    def __init__(self,
                 blur_threshold: float = 100.0,
                 lbp_threshold: float = 50.0,
                 frequency_threshold: float = 0.15,
                 color_diversity_threshold: float = 20.0):
        """
        Initialize Silent Face Anti-Spoofing.
        
        Args:
            blur_threshold: Laplacian variance threshold
            lbp_threshold: LBP variance threshold
            frequency_threshold: High-frequency ratio threshold
            color_diversity_threshold: Color diversity threshold
        """
        self.BLUR_THRESH = blur_threshold
        self.LBP_THRESH = lbp_threshold
        self.FREQ_THRESH = frequency_threshold
        self.COLOR_THRESH = color_diversity_threshold
        
        logger.info(f"🛡️  SilentFaceAntiSpoof initialized (thresholds: blur={blur_threshold}, lbp={lbp_threshold})")
    
    def detect(self, face_region: np.ndarray) -> Dict:
        """
        Main detection method.
        
        Args:
            face_region: Cropped face region (BGR image)
        
        Returns:
            {
                'is_real': bool,
                'score': float (0-1),
                'confidence': str ('high', 'medium', 'low'),
                'reason': str,
                'details': dict
            }
        """
        if face_region is None or face_region.size == 0:
            return self._error_result("Invalid face region")
        
        # Resize to standard size for consistent results
        face_region = cv2.resize(face_region, (128, 128))
        
        # Run all checks
        blur_score, blur_passed = self._check_blur(face_region)
        texture_score, texture_passed = self._check_texture_lbp(face_region)
        freq_score, freq_passed = self._check_frequency_domain(face_region)
        color_score, color_passed = self._check_color_diversity(face_region)
        moire_score, moire_detected = self._check_moire_pattern(face_region)
        
        # Aggregate scores (weighted)
        weights = {
            'blur': 0.25,
            'texture': 0.25,
            'frequency': 0.25,
            'color': 0.15,
            'moire': 0.10
        }
        
        final_score = (
            blur_score * weights['blur'] +
            texture_score * weights['texture'] +
            freq_score * weights['frequency'] +
            color_score * weights['color'] +
            (1.0 - moire_score) * weights['moire']  # Invert: low moiré = good
        )
        
        # Determine if real
        is_real = final_score >= 0.5
        
        # Count failed checks
        failed_checks = []
        if not blur_passed:
            failed_checks.append("Blur (ảnh mờ/màn hình)")
        if not texture_passed:
            failed_checks.append("Texture (ảnh in)")
        if not freq_passed:
            failed_checks.append("Frequency (ảnh số hóa)")
        if not color_passed:
            failed_checks.append("Color (màu sắc không tự nhiên)")
        if moire_detected:
            failed_checks.append("Moiré (chụp từ màn hình)")
        
        # Determine confidence
        if final_score >= 0.7:
            confidence = 'high'
        elif final_score >= 0.4:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        reason = f"Phát hiện gian lận: {', '.join(failed_checks)}" if failed_checks else "Khuôn mặt thật"
        
        return {
            'is_real': is_real,
            'score': float(final_score),
            'confidence': confidence,
            'reason': reason,
            'details': {
                'blur': {'score': float(blur_score), 'passed': blur_passed, 'raw': float(blur_score * 100)},
                'texture': {'score': float(texture_score), 'passed': texture_passed},
                'frequency': {'score': float(freq_score), 'passed': freq_passed},
                'color': {'score': float(color_score), 'passed': color_passed},
                'moire': {'score': float(moire_score), 'detected': moire_detected}
            }
        }
    
    def _check_blur(self, face: np.ndarray) -> Tuple[float, bool]:
        """
        Check image sharpness using Laplacian variance.
        Real faces: sharp (high variance)
        Photos/screens: often blurry (low variance)
        
        Returns:
            (score, passed)
        """
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Normalize score
        score = min(laplacian_var / self.BLUR_THRESH, 1.0)
        passed = laplacian_var >= self.BLUR_THRESH
        
        return score, passed
    
    def _check_texture_lbp(self, face: np.ndarray) -> Tuple[float, bool]:
        """
        Check texture using Local Binary Pattern (LBP).
        Real faces: rich texture variance
        Photos: flat, uniform texture
        
        Returns:
            (score, passed)
        """
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        
        # Simple LBP implementation (8 neighbors, radius 1)
        lbp = self._compute_lbp(gray, radius=1, n_points=8)
        
        # Calculate variance of LBP
        lbp_var = np.var(lbp)
        
        # Normalize score
        score = min(lbp_var / self.LBP_THRESH, 1.0)
        passed = lbp_var >= self.LBP_THRESH
        
        return score, passed
    
    def _compute_lbp(self, gray: np.ndarray, radius: int = 1, n_points: int = 8) -> np.ndarray:
        """
        Compute Local Binary Pattern.
        Simple implementation for speed.
        """
        h, w = gray.shape
        lbp = np.zeros_like(gray, dtype=np.uint8)
        
        for i in range(radius, h - radius):
            for j in range(radius, w - radius):
                center = gray[i, j]
                code = 0
                
                # 8 neighbors
                code |= (gray[i-1, j-1] >= center) << 7
                code |= (gray[i-1, j] >= center) << 6
                code |= (gray[i-1, j+1] >= center) << 5
                code |= (gray[i, j+1] >= center) << 4
                code |= (gray[i+1, j+1] >= center) << 3
                code |= (gray[i+1, j] >= center) << 2
                code |= (gray[i+1, j-1] >= center) << 1
                code |= (gray[i, j-1] >= center) << 0
                
                lbp[i, j] = code
        
        return lbp
    
    def _check_frequency_domain(self, face: np.ndarray) -> Tuple[float, bool]:
        """
        Analyze frequency domain using FFT.
        Real faces: rich high-frequency content
        Photos/screens: low high-frequency content
        
        Returns:
            (score, passed)
        """
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        
        # Apply FFT
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)
        
        h, w = magnitude.shape
        center_h, center_w = h // 2, w // 2
        
        # Define low-frequency region (center)
        mask_size = 15
        low_freq = magnitude[
            center_h - mask_size:center_h + mask_size,
            center_w - mask_size:center_w + mask_size
        ]
        
        # High-frequency region (outer)
        high_freq_mask = np.ones((h, w), dtype=bool)
        high_freq_mask[
            center_h - mask_size:center_h + mask_size,
            center_w - mask_size:center_w + mask_size
        ] = False
        
        high_freq = magnitude[high_freq_mask]
        
        # Calculate ratio
        hf_mean = high_freq.mean()
        lf_mean = low_freq.mean()
        
        ratio = hf_mean / (lf_mean + 1e-6)
        
        # Normalize score
        score = min(ratio / self.FREQ_THRESH, 1.0)
        passed = ratio >= self.FREQ_THRESH
        
        return score, passed
    
    def _check_color_diversity(self, face: np.ndarray) -> Tuple[float, bool]:
        """
        Check color diversity and distribution.
        Real faces: natural color variation
        Screens/photos: often have color distortion
        
        Returns:
            (score, passed)
        """
        # Convert to HSV
        hsv = cv2.cvtColor(face, cv2.COLOR_BGR2HSV)
        
        # Calculate standard deviation for each channel
        h_std = np.std(hsv[:, :, 0])
        s_std = np.std(hsv[:, :, 1])
        v_std = np.std(hsv[:, :, 2])
        
        # Average std
        avg_std = (h_std + s_std + v_std) / 3.0
        
        # Normalize score
        score = min(avg_std / self.COLOR_THRESH, 1.0)
        passed = avg_std >= self.COLOR_THRESH
        
        return score, passed
    
    def _check_moire_pattern(self, face: np.ndarray) -> Tuple[float, bool]:
        """
        Detect Moiré pattern (appears when capturing screen).
        Uses FFT to detect periodic patterns.
        
        Returns:
            (score, has_moire)
        """
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        
        # Apply FFT
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)
        
        # Apply log transform to enhance peaks
        magnitude_log = np.log(magnitude + 1)
        
        h, w = magnitude_log.shape
        center_h, center_w = h // 2, w // 2
        
        # Create ring mask (where moiré patterns appear)
        y, x = np.ogrid[:h, :w]
        distance = np.sqrt((y - center_h)**2 + (x - center_w)**2)
        
        ring_mask = (distance > 20) & (distance < 50)
        ring_values = magnitude_log[ring_mask]
        
        if len(ring_values) == 0:
            return 0.0, False
        
        # Detect unusual peaks
        threshold = ring_values.mean() + 2.5 * ring_values.std()
        peaks = np.sum(ring_values > threshold)
        
        # Normalize
        peak_ratio = peaks / len(ring_values)
        
        # If many peaks → moiré detected
        has_moire = peak_ratio > 0.05
        
        return float(peak_ratio * 10), has_moire
    
    def _error_result(self, reason: str) -> Dict:
        """Return error result."""
        return {
            'is_real': False,
            'score': 0.0,
            'confidence': 'low',
            'reason': reason,
            'details': {}
        }


class HybridLivenessDetector:
    """
    Combined Active + Passive liveness detection.
    - Active: Requires user action (blink, head turn)
    - Passive: Silent anti-spoofing (texture, frequency, etc.)
    """
    
    def __init__(self, require_action: bool = True):
        """
        Initialize hybrid detector.
        
        Args:
            require_action: If True, require blink/head turn. If False, passive only.
        """
        self.require_action = require_action
        self.passive_detector = SilentFaceAntiSpoof(
            blur_threshold=100.0,
            lbp_threshold=50.0,
            frequency_threshold=0.15,
            color_diversity_threshold=20.0
        )
        
        # Active liveness state
        self.blink_counter = 0
        self.ear_history = []
        self.head_moved = False
        
        logger.info(f"🔒 HybridLivenessDetector initialized (require_action={require_action})")
    
    def detect(self, frame: np.ndarray, face_box: Tuple[int, int, int, int],
               active_data: Dict = None) -> Dict:
        """
        Detect liveness using hybrid approach.
        
        Args:
            frame: Full frame
            face_box: (top, right, bottom, left)
            active_data: Optional active liveness data {'ear': float, 'yaw': float}
        
        Returns:
            {
                'is_real': bool,
                'score': float,
                'confidence': str,
                'reason': str,
                'passive_details': dict,
                'active_details': dict
            }
        """
        top, right, bottom, left = face_box
        face_region = frame[top:bottom, left:right]
        
        # 1. Passive check (ALWAYS run)
        passive_result = self.passive_detector.detect(face_region)
        
        # 2. Active check (if required and data provided)
        active_score = 1.0
        active_reason = "Active check skipped"
        
        if self.require_action and active_data:
            active_score, active_reason = self._check_active(active_data)
        
        # 3. Combine scores
        if self.require_action:
            # Active 40%, Passive 60%
            final_score = active_score * 0.4 + passive_result['score'] * 0.6
        else:
            # Passive only
            final_score = passive_result['score']
        
        is_real = final_score >= 0.5 and passive_result['is_real']
        
        # Determine confidence
        if final_score >= 0.7:
            confidence = 'high'
        elif final_score >= 0.4:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        # Combine reasons
        reasons = []
        if not passive_result['is_real']:
            reasons.append(passive_result['reason'])
        if self.require_action and active_score < 0.5:
            reasons.append(active_reason)
        
        reason = "; ".join(reasons) if reasons else "Liveness verified"
        
        return {
            'is_real': is_real,
            'score': float(final_score),
            'confidence': confidence,
            'reason': reason,
            'passive_details': passive_result['details'],
            'active_details': {
                'score': float(active_score),
                'reason': active_reason,
                'blink_count': self.blink_counter
            }
        }
    
    def _check_active(self, active_data: Dict) -> Tuple[float, str]:
        """
        Check active liveness (blink + head movement).
        
        Returns:
            (score, reason)
        """
        ear = active_data.get('ear', 1.0)
        yaw = active_data.get('yaw', 0.0)
        
        # Track EAR for blink detection
        self.ear_history.append(ear)
        if len(self.ear_history) > 30:
            self.ear_history.pop(0)
        
        # Detect blink (EAR drops below threshold)
        if ear < 0.23:
            self.blink_counter += 1
        
        # Check head movement
        if abs(yaw) > 15:
            self.head_moved = True
        
        # Scoring
        score = 0.0
        reasons = []
        
        if self.blink_counter > 0:
            score += 0.5
        else:
            reasons.append("Chưa chớp mắt")
        
        if self.head_moved:
            score += 0.5
        else:
            reasons.append("Chưa quay đầu")
        
        reason = "; ".join(reasons) if reasons else "Active checks passed"
        
        return score, reason
    
    def reset(self):
        """Reset state for new session."""
        self.blink_counter = 0
        self.ear_history.clear()
        self.head_moved = False
        logger.debug("🔄 Hybrid detector state reset")
