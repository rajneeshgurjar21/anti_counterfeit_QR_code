"""
Print-and-Scan (P&S) Channel and Multi-Camera Simulator
======================================================
Accurately models physical degradation channels across diverse mobile cameras:

1. 1st Generation Print & Multi-Camera Capture (GENUINE):
   - Phone A (Flagship / Ultra-Sharp, e.g. iPhone / Pixel Pro): High MTF, crisp micro-dots.
   - Phone B (Aggressive ISP Noise Reduction, e.g. Samsung / Xiaomi): Bilateral/wavelet smoothing.
   - Phone C (Distance / Sub-sampled Capture): QR code occupies portion of frame on realistic background.
   - Phone D (Angular & Lighting Gradients): 15-20 deg perspective tilt + shadow falloff.
   - Phone E (Budget Camera / Lens Softness): Optical PSF softening and slight contrast drop.

2. 2nd Generation Reprint / Photocopy Attack (COUNTERFEIT):
   - 1st print + optical scan/photo by counterfeiter
   - Resampling / Bayer demosaicing artifacts
   - Secondary printer dot gain, ink bleeding, and high-frequency destruction
   - Micro-void obliteration and toner clumping
   - Inspected by any consumer camera (Phone A through E)
"""

import numpy as np
import cv2
from PIL import Image

PHONE_PROFILES = {
    "phone_a": {
        "name": "Phone A (Flagship / Ultra-Sharp)",
        "blur_sigma": 0.50,
        "blur_ksize": 3,
        "dot_gain": 0.10,
        "sensor_noise_sigma": 1.2,
        "isp_smoothing": False,
        "scale": 1.0,
        "contrast_factor": 1.05,
    },
    "phone_b": {
        "name": "Phone B (Aggressive Noise Reduction)",
        "blur_sigma": 0.85,
        "blur_ksize": 3,
        "dot_gain": 0.15,
        "sensor_noise_sigma": 2.8,
        "isp_smoothing": True,  # Bilateral filter simulates camera ISP de-noising
        "scale": 1.0,
        "contrast_factor": 0.98,
    },
    "phone_c": {
        "name": "Phone C (Distance Capture / Sub-sampled)",
        "blur_sigma": 1.05,
        "blur_ksize": 5,
        "dot_gain": 0.14,
        "sensor_noise_sigma": 2.4,
        "isp_smoothing": False,
        "scale": 0.72,  # QR code is smaller in sensor frame
        "contrast_factor": 0.95,
    },
    "phone_d": {
        "name": "Phone D (Challenging Lighting & Moderate Tilt)",
        "blur_sigma": 0.75,
        "blur_ksize": 3,
        "dot_gain": 0.14,
        "sensor_noise_sigma": 3.0,
        "isp_smoothing": False,
        "scale": 0.90,
        "tilt_deg": 14.0,
        "shadow_gradient": True,
        "contrast_factor": 0.92,
    },
    "phone_e": {
        "name": "Phone E (Budget Camera / Lens Softness)",
        "blur_sigma": 1.22,
        "blur_ksize": 5,
        "dot_gain": 0.18,
        "sensor_noise_sigma": 3.8,
        "isp_smoothing": True,
        "scale": 0.85,
        "contrast_factor": 0.90,
    },
}


def apply_dot_gain(img_gray: np.ndarray, gain_factor: float = 0.18) -> np.ndarray:
    """
    Simulates physical ink spread (dot gain) on paper fibers.
    Dark dots expand slightly into surrounding paper.
    """
    norm = img_gray.astype(np.float32) / 255.0
    gained = np.power(norm, 1.0 + gain_factor)
    return np.clip(gained * 255.0, 0, 255).astype(np.uint8)


def apply_perspective_tilt(cv_img: np.ndarray, angle_deg: float = 12.0) -> np.ndarray:
    """Applies a realistic camera perspective pitch/tilt."""
    h, w = cv_img.shape[:2]
    rad = np.radians(angle_deg)
    shift = int(w * 0.12 * np.sin(rad))
    
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    dst = np.array([
        [shift, int(h * 0.05)], 
        [w - shift, int(h * 0.02)], 
        [w - int(shift * 0.3), h - int(h * 0.04)], 
        [int(shift * 0.3), h]
    ], dtype=np.float32)
    
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(cv_img, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))


def add_realistic_background(qr_img: np.ndarray, bg_size_mult: float = 1.4) -> np.ndarray:
    """
    Places the QR code in the middle of a wider realistic desk/table background.
    This simulates real-world mobile captures where the QR code occupies 30-60% of the frame.
    """
    h, w = qr_img.shape[:2]
    bg_w = int(w * bg_size_mult)
    bg_h = int(h * bg_size_mult)
    
    # Realistic slightly textured desk/surface (light neutral gray-beige with gentle gradient)
    y_coords, x_coords = np.mgrid[0:bg_h, 0:bg_w]
    bg_base = 230 + 12 * np.sin(x_coords / 40.0) * np.cos(y_coords / 50.0)
    bg_noise = np.random.normal(0, 1.5, (bg_h, bg_w))
    bg_gray = np.clip(bg_base + bg_noise, 210, 248).astype(np.uint8)
    
    if len(qr_img.shape) == 3:
        bg = cv2.cvtColor(bg_gray, cv2.COLOR_GRAY2BGR)
    else:
        bg = bg_gray
        
    ox = (bg_w - w) // 2
    oy = (bg_h - h) // 2
    bg[oy:oy+h, ox:ox+w] = qr_img
    return bg


def simulate_phone_capture(
    img: Image.Image,
    phone_model: str = "phone_a",
    add_background: bool = False,
    override_blur: float = None,
) -> Image.Image:
    """
    Simulates a 1st-generation genuine original print captured by a specific mobile phone.
    Accurately models camera ISP, optical point-spread function (PSF), sensor noise, and perspective.
    """
    profile = PHONE_PROFILES.get(phone_model, PHONE_PROFILES["phone_a"]).copy()
    if override_blur is not None:
        profile["blur_sigma"] = override_blur
        
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    orig_h, orig_w = gray.shape
    
    # 1. Physical 1st Generation printer dot gain (ink absorption on paper)
    gained = apply_dot_gain(gray, gain_factor=profile["dot_gain"])
    
    # 2. Distance scaling / sensor pixel sub-sampling
    scale = profile.get("scale", 1.0)
    if scale < 0.98:
        scaled_w = int(orig_w * scale)
        scaled_h = int(orig_h * scale)
        downsampled = cv2.resize(gained, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
        # Resampled back to canvas (representing camera viewfinder/sensor grid)
        gained = cv2.resize(downsampled, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        
    # 3. Camera optical point spread function (lens blur)
    blur_sigma = profile["blur_sigma"]
    blur_ksize = profile["blur_ksize"]
    blurred = cv2.GaussianBlur(gained, (blur_ksize, blur_ksize), blur_sigma)
    
    # 4. Smartphone camera ISP noise reduction (bilateral filter)
    if profile.get("isp_smoothing", False):
        # Bilateral filter preserves major step edges while smoothing fine micro-textures
        blurred = cv2.bilateralFilter(blurred, d=5, sigmaColor=18, sigmaSpace=5)
        
    # 5. Sensor noise accumulation
    noise_sigma = profile.get("sensor_noise_sigma", 2.0)
    noise = np.random.normal(0, noise_sigma, blurred.shape).astype(np.float32)
    noisy = np.clip(blurred.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    
    # 6. Lighting gradient / shadows
    h, w = noisy.shape
    if profile.get("shadow_gradient", False):
        y, x = np.mgrid[0:h, 0:w]
        grad = 1.0 - 0.12 * ((x - w * 0.2)**2 + (y - h * 0.3)**2) / (w**2 + h**2)
        noisy = np.clip(noisy.astype(np.float32) * grad, 0, 255).astype(np.uint8)
    else:
        # Subtle vignette
        y, x = np.mgrid[0:h, 0:w]
        grad = 1.0 - 0.04 * ((x - w/2)**2 + (y - h/2)**2) / ((w/2)**2 + (h/2)**2)
        noisy = np.clip(noisy.astype(np.float32) * grad, 0, 255).astype(np.uint8)
        
    # 7. Perspective angle tilt if modeled
    tilt = profile.get("tilt_deg", 0.0)
    if tilt > 0.5:
        noisy = apply_perspective_tilt(noisy, angle_deg=tilt)
        
    # 8. Contrast adjustment
    contrast = profile.get("contrast_factor", 1.0)
    if abs(contrast - 1.0) > 0.01:
        mean_c = float(np.mean(noisy))
        adjusted = mean_c + contrast * (noisy.astype(np.float32) - mean_c)
        noisy = np.clip(adjusted, 0, 255).astype(np.uint8)
        
    # 9. Optional realistic background placement
    if add_background:
        noisy = add_realistic_background(noisy, bg_size_mult=1.35)
        
    return Image.fromarray(cv2.cvtColor(noisy, cv2.COLOR_GRAY2RGB))


def simulate_counterfeit_reprint(
    img: Image.Image,
    scan_scale: float = 0.85,
    rescan_blur: float = 1.8,
    reprint_gain: float = 0.35,
    reprint_blur: float = 2.4,
    noise_sigma: float = 4.5,
) -> Image.Image:
    """
    Simulates a 2nd generation counterfeit copy (reprinted / photocopied).
    The micro-dot pattern is severely degraded due to consecutive print-and-scan cycles.
    """
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # --- PHASE 1: Counterfeiter captures genuine print ---
    p1 = cv2.GaussianBlur(gray, (5, 5), rescan_blur)
    low_w = int(w * scan_scale)
    low_h = int(h * scan_scale)
    digitized = cv2.resize(p1, (low_w, low_h), interpolation=cv2.INTER_LINEAR)
    resampled = cv2.resize(digitized, (w, h), interpolation=cv2.INTER_LINEAR)
    
    # --- PHASE 2: Counterfeiter reprints on consumer printer ---
    p2 = apply_dot_gain(resampled, gain_factor=reprint_gain)
    p2_bleed = cv2.GaussianBlur(p2, (7, 7), reprint_blur)
    
    # --- PHASE 3: Mobile inspection of the counterfeit label ---
    noise = np.random.normal(0, noise_sigma, p2_bleed.shape).astype(np.float32)
    fake_captured = np.clip(p2_bleed.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    
    return Image.fromarray(cv2.cvtColor(fake_captured, cv2.COLOR_GRAY2RGB))


def simulate_counterfeit_reprint_captured(
    img: Image.Image,
    phone_model: str = "phone_a",
    add_background: bool = False,
) -> Image.Image:
    """
    Simulates a counterfeit 2nd-generation reprint photographed by a specific consumer phone.
    """
    reprinted = simulate_counterfeit_reprint(img)
    # The consumer now photographs the counterfeit physical label using their phone
    return simulate_phone_capture(reprinted, phone_model=phone_model, add_background=add_background)


# Backward-compatible alias
def simulate_genuine_scan(
    img: Image.Image, 
    blur_ksize: int = 3, 
    blur_sigma: float = 0.6, 
    dot_gain: float = 0.12,
    sensor_noise_sigma: float = 2.0,
    illumination_gradient: bool = True
) -> Image.Image:
    """Backward-compatible default genuine simulation."""
    return simulate_phone_capture(img, phone_model="phone_a", override_blur=blur_sigma)
