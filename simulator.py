"""
Print-and-Scan (P&S) Channel and Reprint Simulator
===================================================
Accurately models physical degradation channels:
1. 1st Generation Print & Optical Capture (GENUINE):
   - Printer modulation transfer function (MTF) & dot gain
   - High-res camera capture with fine micro-dot retention
   
2. 2nd Generation Reprint / Photocopy Attack (COUNTERFEIT):
   - 1st print + optical scan/photo by counterfeiter
   - Resampling / Bayer demosaicing artifacts
   - Secondary printer dot gain, ink bleeding, and high-frequency loss
   - Irreversible destruction of micro-dot entropy
"""

import numpy as np
import cv2
from PIL import Image

def apply_dot_gain(img_gray: np.ndarray, gain_factor: float = 0.18) -> np.ndarray:
    """
    Simulates physical ink spread (dot gain) on paper fibers.
    Dark dots expand slightly into surrounding paper.
    """
    # Non-linear darkness expansion
    norm = img_gray.astype(np.float32) / 255.0
    # Power curve simulates dot gain in halftoning
    gained = np.power(norm, 1.0 + gain_factor)
    return np.clip(gained * 255.0, 0, 255).astype(np.uint8)

def simulate_genuine_scan(
    img: Image.Image, 
    blur_ksize: int = 3, 
    blur_sigma: float = 0.6, 
    dot_gain: float = 0.12,
    sensor_noise_sigma: float = 2.0,
    illumination_gradient: bool = True
) -> Image.Image:
    """
    Simulates a 1st generation original print captured by a smartphone camera.
    Retains crisp micro-dot fidelity while including realistic physical optics.
    """
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # 1. 1st Generation printer dot gain
    gained = apply_dot_gain(gray, gain_factor=dot_gain)
    
    # 2. Camera lens optical point spread function (PSF) - mild blur
    blurred = cv2.GaussianBlur(gained, (blur_ksize, blur_ksize), blur_sigma)
    
    # 3. Camera sensor Gaussian noise
    noise = np.random.normal(0, sensor_noise_sigma, blurred.shape).astype(np.float32)
    captured = np.clip(blurred.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    
    # 4. Subtle lighting variation across the image
    if illumination_gradient:
        h, w = captured.shape
        y, x = np.mgrid[0:h, 0:w]
        grad = 1.0 - 0.05 * ((x - w/2)**2 + (y - h/2)**2) / ((w/2)**2 + (h/2)**2)
        captured = np.clip(captured.astype(np.float32) * grad, 0, 255).astype(np.uint8)
        
    return Image.fromarray(cv2.cvtColor(captured, cv2.COLOR_GRAY2RGB))


def simulate_counterfeit_reprint(
    img: Image.Image,
    scan_scale: float = 0.85,          # Optical downsampling by counterfeiter's scanner/camera
    rescan_blur: float = 1.8,          # Counterfeiter capture lens blur
    reprint_gain: float = 0.35,        # 2nd generation ink spread / dot bleeding
    reprint_blur: float = 2.4,         # 2nd printer MTF cutoff (destroys micro-dots)
    noise_sigma: float = 4.5           # Double sensor noise accumulation
) -> Image.Image:
    """
    Simulates a 2nd generation counterfeit copy (reprinted / photocopied).
    The micro-dot pattern is severely degraded due to consecutive print-and-scan cycles.
    """
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # --- PHASE 1: Counterfeiter captures genuine print ---
    # 1. Optical blur from camera/scanner
    p1 = cv2.GaussianBlur(gray, (5, 5), rescan_blur)
    # 2. Resampling downscale & upscale (simulates digitizing at consumer DPI)
    low_w = int(w * scan_scale)
    low_h = int(h * scan_scale)
    digitized = cv2.resize(p1, (low_w, low_h), interpolation=cv2.INTER_LINEAR)
    resampled = cv2.resize(digitized, (w, h), interpolation=cv2.INTER_LINEAR)
    
    # --- PHASE 2: Counterfeiter reprints on consumer printer ---
    # 1. Extreme 2nd-generation dot gain (ink merges into gaps)
    p2 = apply_dot_gain(resampled, gain_factor=reprint_gain)
    # 2. Secondary printer mechanical & ink bleeding blur
    p2_bleed = cv2.GaussianBlur(p2, (7, 7), reprint_blur)
    
    # --- PHASE 3: Mobile inspection of the counterfeit label ---
    # Secondary camera optical PSF + sensor noise
    noise = np.random.normal(0, noise_sigma, p2_bleed.shape).astype(np.float32)
    fake_captured = np.clip(p2_bleed.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    
    return Image.fromarray(cv2.cvtColor(fake_captured, cv2.COLOR_GRAY2RGB))
