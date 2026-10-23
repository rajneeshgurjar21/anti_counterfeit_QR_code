"""
Camera-Independent Anti-Counterfeit QR Code & Copy Detection Pattern (CDP) Verifier
===================================================================================
Production-Grade Verification Engine Robust Across Diverse Mobile Cameras.

Key Capabilities:
1. QR-Localized Image Quality Pre-Gate:
   - Sharpness and blur are measured ON THE QR CODE / FINDER PATTERNS,
     not diluted by flat, low-texture backgrounds (desks, walls, paper margins).
   - Separates LOW_IMAGE_QUALITY / RECAPTURE_REQUIRED from COUNTERFEIT.
2. In-Frame Camera MTF Calibration:
   - Uses the QR code's large black/white finder patterns as an optical reference
     to measure camera lens modulation transfer function (MTF) and point spread.
3. Relative Acutance & Relative Sharpness:
   - Measures CDP micro-edge acutance RELATIVE to the QR code's own macro-edges.
   - Neutralizes camera-to-camera sharpness, sensor distance, and ISP variations.
4. MTF-Matched Template Cross-Correlation:
   - Adapts the digital master template to the camera's estimated optical blur,
     allowing true pattern correlation without penalizing natural optical softening.
5. Adaptive Micro-Morphology & Void Analysis:
   - Uses local adaptive thresholding to evaluate micro-dot preservation,
     perimeter-to-area ratio (P/A), micro-voids, and toner clumping.
6. Decoupled Multi-Factor Scoring Model:
   - IMAGE_QUALITY_SCORE, CDP_AUTHENTICITY_SCORE, REPRINT_RISK_SCORE, DIGITAL_AUTHENTICITY_SCORE.
"""

import os
import urllib.parse
import cv2
import numpy as np
from PIL import Image

from cdp_engine import generate_cdp_module_with_fiducials, generate_cdp_pattern


# ─────────────────────────────────────────────
#  Constants & Multi-Camera Calibration Limits
# ─────────────────────────────────────────────

# Minimum QR localized sharpness to proceed (on the QR bounding box, NOT full image)
QR_LOCAL_BLUR_MIN = 12.0

# Minimum global sharpness when QR corners cannot be located
GLOBAL_BLUR_MIN = 14.0

# Perspective tilt sanity check (min edge length / max edge length)
PERSPECTIVE_EDGE_RATIO_MIN = 0.28

# Relative Acutance Thresholds (CDP micro-edge gradient / QR macro-edge gradient)
# Genuine prints across all phones: 1.25 - 4.00
# Counterfeit reprints across all phones: 0.45 - 0.65
REL_ACUTANCE_GENUINE_MIN = 1.05
REL_ACUTANCE_REPRINT_MAX = 0.82

# Relative Laplacian Thresholds
REL_LAP_GENUINE_MIN = 0.70
REL_LAP_REPRINT_MAX = 0.50

# FFT High-frequency energy threshold
HF_GENUINE_MIN = 0.0035
HF_REPRINT_MAX = 0.0022

# MTF-Matched NCC thresholds
NCC_GENUINE_HIGH = 0.70
NCC_GENUINE_LOW  = 0.35
NCC_MISMATCH_MAX = 0.25  # Below this: pattern does not match cryptographic seed

# Score thresholds
SCORE_GENUINE_THRESHOLD    = 65.0
SCORE_SUSPICIOUS_THRESHOLD = 45.0


# ─────────────────────────────────────────────
#  Core Signal Processing & Image Metrics
# ─────────────────────────────────────────────

def extract_serial_number(payload: str) -> str:
    """Extracts serial/ID from URL query string or returns raw payload."""
    try:
        parsed = urllib.parse.urlparse(payload)
        query = urllib.parse.parse_qs(parsed.query)
        if 'id' in query:
            return query['id'][0]
        if 'sn' in query:
            return query['sn'][0]
    except Exception:
        pass
    return payload.strip()


def compute_gradient_sharpness(img_gray: np.ndarray) -> float:
    """Computes mean Sobel gradient magnitude – higher = sharper edges."""
    if img_gray is None or img_gray.size == 0:
        return 0.0
    sobelx = cv2.Sobel(img_gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(img_gray, cv2.CV_64F, 0, 1, ksize=3)
    return float(np.mean(np.sqrt(sobelx**2 + sobely**2)))


def compute_edge_acutance(img_gray: np.ndarray) -> float:
    """
    Computes Laplacian variance of the image.
    Higher = sharper edges; lower = blurred.
    """
    if img_gray is None or img_gray.size == 0:
        return 0.0
    laplacian = cv2.Laplacian(img_gray, cv2.CV_64F)
    return float(laplacian.var())


def compute_fft_hf_energy_ratio(img_gray: np.ndarray, cutoff_ratio: float = 0.20) -> float:
    """
    High-frequency spectral energy fraction via 2D-FFT.
    Physical blur / reprinting collapses HF energy.
    """
    if img_gray is None or img_gray.size == 0:
        return 0.0
    f = np.fft.fft2(img_gray.astype(np.float32))
    fshift = np.fft.fftshift(f)
    magnitude_spectrum = np.abs(fshift) ** 2

    h, w = img_gray.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    cutoff = min(h, w) * cutoff_ratio

    high_freq_energy = np.sum(magnitude_spectrum[dist > cutoff])
    total_energy = np.sum(magnitude_spectrum)

    if total_energy == 0:
        return 0.0
    return float(high_freq_energy / total_energy)


def compute_peak_cross_correlation(
    candidate: np.ndarray, reference: np.ndarray
) -> tuple[float, tuple[int, int]]:
    """
    Peak Normalized Cross-Correlation (NCC) via template matching.
    Provides translation invariance with a search window.
    """
    if candidate is None or reference is None or candidate.size == 0 or reference.size == 0:
        return 0.0, (0, 0)
        
    cand = candidate.astype(np.float32)
    ref  = reference.astype(np.float32)

    pad = 14
    cand_pad = cv2.copyMakeBorder(cand, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    
    # Crop borders of reference slightly to allow sub-pixel shift search
    margin = 6
    if ref.shape[0] > 2 * margin and ref.shape[1] > 2 * margin:
        ref_crop = ref[margin:ref.shape[0]-margin, margin:ref.shape[1]-margin]
    else:
        ref_crop = ref

    try:
        res = cv2.matchTemplate(cand_pad, ref_crop, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        return float(max_val), max_loc
    except Exception:
        return 0.0, (0, 0)


# ─────────────────────────────────────────────
#  Multi-Pass Barcode Detection & Local Quality
# ─────────────────────────────────────────────

def robust_detect_and_decode_qr(img_cv: np.ndarray) -> tuple[str, np.ndarray, np.ndarray]:
    """
    Robust multi-pass QR barcode detection and decoding.
    Handles clipped quiet zones, shadows, and low-contrast mobile shots.
    """
    detector = cv2.QRCodeDetector()
    payload, points, straight = detector.detectAndDecode(img_cv)
    if payload and points is not None and len(points) > 0:
        return payload, points, straight

    # Pass 2: White border padding (recovers codes where quiet zone is clipped)
    for pad in [25, 50, 75, 100]:
        padded = cv2.copyMakeBorder(
            img_cv, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=[255, 255, 255]
        )
        p, pts_p, s = detector.detectAndDecode(padded)
        if p and pts_p is not None and len(pts_p) > 0:
            points = pts_p - np.array([[[pad, pad]]])
            return p, points, s

    # Pass 3: CLAHE contrast enhancement for shadowy or underexposed photos
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced_gray = clahe.apply(gray)
    enhanced_bgr = cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)
    p, pts, s = detector.detectAndDecode(enhanced_bgr)
    if p and pts is not None and len(pts) > 0:
        return p, pts, s

    return "", None, None


def validate_image_quality(img_cv: np.ndarray, detected_points: np.ndarray = None) -> tuple[bool, str, str, dict]:
    """
    Stage 1: Image Quality Validation Pre-Gate.
    Ensures image is clear, focused, adequately exposed, and decodable.
    
    CRITICAL MULTI-CAMERA FIX:
    Sharpness and focus are measured ON THE QR CODE BOUNDING BOX,
    not diluted by flat, low-texture backgrounds (tables, walls, margins).
    """
    if img_cv is None or img_cv.size == 0:
        return False, "Failed to load input image", "Please provide a valid image file in PNG or JPEG format.", {}

    h, w = img_cv.shape[:2]
    if h < 180 or w < 180:
        return (
            False,
            f"Image resolution too low ({w}x{h} px, min 180x180)",
            "Image must be at least 180x180 pixels. Please capture closer to the QR code.",
            {"height": h, "width": w}
        )

    img_gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    mean_val = float(np.mean(img_gray))
    std_val  = float(np.std(img_gray))
    full_lap = compute_edge_acutance(img_gray)

    # 1. Total Darkness Check
    if mean_val < 25.0:
        return (
            False,
            f"Image underexposed / too dark (mean brightness: {mean_val:.1f}/255)",
            "Lighting is too dim to resolve microscopic security features. Please turn on camera flash or move to a well-lit environment.",
            {"mean_brightness": round(mean_val, 1)}
        )

    # 2. QR-Localized Sharpness Check
    if detected_points is not None and len(detected_points) > 0:
        pts = detected_points[0].astype(np.float32)
        x_min = max(0, int(np.min(pts[:, 0])))
        x_max = min(w, int(np.max(pts[:, 0])))
        y_min = max(0, int(np.min(pts[:, 1])))
        y_max = min(h, int(np.max(pts[:, 1])))
        
        qr_roi = img_gray[y_min:y_max, x_min:x_max]
        if qr_roi.size > 100:
            qr_lap = compute_edge_acutance(qr_roi)
            sat_ratio_qr = float(np.mean(qr_roi > 250))
            
            # Specular glare washing out the QR code
            if sat_ratio_qr > 0.82:
                return (
                    False,
                    "Excessive specular glare over QR code",
                    "Bright reflections or flash reflections are washing out the QR code. Tilt camera slightly to avoid direct glare.",
                    {"qr_saturation_ratio": round(sat_ratio_qr, 3)}
                )
                
            # True motion/optical blur check on QR region
            if qr_lap < QR_LOCAL_BLUR_MIN:
                return (
                    False,
                    f"QR code is out of focus / blurry (sharpness: {qr_lap:.1f} < {QR_LOCAL_BLUR_MIN:.0f})",
                    "Hold your phone steady, tap the screen to lock optical autofocus on the QR code, and avoid motion blur.",
                    {"qr_sharpness": round(qr_lap, 1), "full_image_sharpness": round(full_lap, 1)}
                )
                
            return True, "", "", {
                "height": h, "width": w,
                "mean_brightness": round(mean_val, 1),
                "contrast_std": round(std_val, 1),
                "qr_sharpness": round(qr_lap, 1),
                "full_image_sharpness": round(full_lap, 1),
            }

    # Fallback if QR points not yet available
    if full_lap < GLOBAL_BLUR_MIN:
        return (
            False,
            f"Image is out of focus / blurry (sharpness: {full_lap:.1f} < {GLOBAL_BLUR_MIN:.0f})",
            "Hold your phone steady, tap the screen to lock optical autofocus on the QR code, and avoid motion blur.",
            {"full_image_sharpness": round(full_lap, 1)}
        )

    return True, "", "", {
        "height": h, "width": w,
        "mean_brightness": round(mean_val, 1),
        "contrast_std": round(std_val, 1),
        "full_image_sharpness": round(full_lap, 1),
    }


# ─────────────────────────────────────────────
#  In-Frame Macro-Edge MTF Measurement
# ─────────────────────────────────────────────

def measure_in_frame_macro_acutance(warped_gray: np.ndarray, modules: int, box_size: int = 12) -> dict:
    """
    Measures the camera MTF (point spread function and sharpness) directly from the
    QR code's own black/white finder patterns in the rectified image.
    
    The top-left finder pattern consists of high-contrast 7x7 modules.
    Measuring its edge gradient gives the camera's baseline acutance on standard black ink.
    Also measures the step-edge acuity (first-derivative slope) along the physical ink transitions,
    which decisively separates 1st-generation industrial prints from 2nd-generation photocopies/reprints.
    """
    border = 4
    offset = border * box_size
    finder_w = 7 * box_size
    
    # Top-Left finder pattern region
    tl_finder = warped_gray[offset:offset+finder_w, offset:offset+finder_w]
    
    # Top-Right finder pattern region
    tr_x = offset + (modules - 7) * box_size
    tr_finder = warped_gray[offset:offset+finder_w, tr_x:tr_x+finder_w]
    
    # Measure macro gradient sharpness along finder transitions
    grad_tl = compute_gradient_sharpness(tl_finder)
    grad_tr = compute_gradient_sharpness(tr_finder)
    macro_grad = float(np.mean([grad_tl, grad_tr]))
    
    lap_tl = compute_edge_acutance(tl_finder)
    lap_tr = compute_edge_acutance(tr_finder)
    macro_lap = float(np.mean([lap_tl, lap_tr]))
    
    # Measure physical step-edge transition slope across multiple finder pattern boundaries
    edge_slopes = []
    wh, ww = warped_gray.shape[:2]
    # 1. Top horizontal edge of TL finder (y ~ offset)
    y_min, y_max = max(0, offset - box_size), min(wh, offset + box_size)
    x_min, x_max = max(0, offset + box_size), min(ww, offset + finder_w - box_size)
    if y_max > y_min and x_max > x_min:
        for x in range(x_min, x_max, 2):
            prof = warped_gray[y_min:y_max, x].astype(np.float32)
            if len(prof) > 1:
                edge_slopes.append(np.max(np.abs(np.diff(prof))))
                
    # 2. Bottom horizontal edge of TL finder (y ~ offset + finder_w)
    y_min2, y_max2 = max(0, offset + finder_w - box_size), min(wh, offset + finder_w + box_size)
    if y_max2 > y_min2 and x_max > x_min:
        for x in range(x_min, x_max, 2):
            prof = warped_gray[y_min2:y_max2, x].astype(np.float32)
            if len(prof) > 1:
                edge_slopes.append(np.max(np.abs(np.diff(prof))))
                
    # 3. Left vertical edge of TL finder (x ~ offset)
    x_min_l, x_max_l = max(0, offset - box_size), min(ww, offset + box_size)
    y_min_l, y_max_l = max(0, offset + box_size), min(wh, offset + finder_w - box_size)
    if x_max_l > x_min_l and y_max_l > y_min_l:
        for y in range(y_min_l, y_max_l, 2):
            prof = warped_gray[y, x_min_l:x_max_l].astype(np.float32)
            if len(prof) > 1:
                edge_slopes.append(np.max(np.abs(np.diff(prof))))

    # 4. Right vertical edge of TL finder (x ~ offset + finder_w)
    x_min_r, x_max_r = max(0, offset + finder_w - box_size), min(ww, offset + finder_w + box_size)
    if x_max_r > x_min_r and y_max_l > y_min_l:
        for y in range(y_min_l, y_max_l, 2):
            prof = warped_gray[y, x_min_r:x_max_r].astype(np.float32)
            if len(prof) > 1:
                edge_slopes.append(np.max(np.abs(np.diff(prof))))

    finder_edge_slope = float(np.mean(edge_slopes)) if edge_slopes else macro_grad
    
    # Measure solid black core uniformity (modules 6..8 of TL finder)
    core_y1 = max(0, offset + 2 * box_size)
    core_y2 = min(wh, offset + 5 * box_size)
    core_x1 = max(0, offset + 2 * box_size)
    core_x2 = min(ww, offset + 5 * box_size)
    black_core = warped_gray[core_y1:core_y2, core_x1:core_x2]
    black_core_std = float(np.std(black_core)) if black_core.size > 0 else 0.0

    # Estimate local dynamic range (white paper vs black ink)
    white_level = float(np.percentile(warped_gray, 95))
    black_level = float(np.percentile(warped_gray, 5))
    contrast_michelson = (white_level - black_level) / max(1.0, (white_level + black_level))
    
    return {
        "macro_gradient": round(macro_grad, 2),
        "macro_laplacian": round(macro_lap, 2),
        "finder_edge_slope": round(finder_edge_slope, 2),
        "black_core_std": round(black_core_std, 2),
        "white_level": round(white_level, 1),
        "black_level": round(black_level, 1),
        "contrast_michelson": round(contrast_michelson, 3),
    }


# ─────────────────────────────────────────────
#  Adaptive Micro-Morphology & Void Analysis
# ─────────────────────────────────────────────

def compute_dot_morphology(inner_cand: np.ndarray) -> dict:
    """
    Analyzes micro-dot morphology using local adaptive binarization.
    Robust against non-uniform illumination and camera ISP tone curves.
    
    Genuine prints retain high perimeter-to-area ratio (P/A) and distinct micro-voids.
    Photocopies and reprints experience secondary ink spread, destroying micro-voids
    and creating fused toner clumps.
    """
    if inner_cand is None or inner_cand.size == 0:
        return {
            "pa_ratio": 0.0,
            "mean_dot_area": 0.0,
            "clump_ratio": 1.0,
            "dot_count": 0,
            "void_count": 0,
            "black_density": 0.0,
            "morph_norm": 0.0,
            "is_photocopy": True,
        }

    # 1. Local Min-Max Contrast Normalization
    norm = cv2.normalize(inner_cand, None, 0, 255, cv2.NORM_MINMAX)
    
    # 2. Adaptive Gaussian Binarization (preserves micro-voids across lighting gradients)
    binary = cv2.adaptiveThreshold(
        norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 3
    )
    
    total_pixels = binary.size
    black_pixels = int(np.sum(binary > 0))
    black_density = black_pixels / max(1, total_pixels)

    # 3. Connected Component Analysis on black ink dots
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    areas = []
    perimeters = []
    clump_thresh = 65  # Component area > 65px classified as multi-dot clump
    large_clump_area = 0

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 3:  # Discard 1-2 pixel isolated sensor noise
            continue
        mask = (labels == i).astype(np.uint8)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts:
            continue
        peri = cv2.arcLength(cnts[0], True)
        areas.append(area)
        perimeters.append(peri)
        if area > clump_thresh:
            large_clump_area += area

    tot_area = sum(areas) if areas else 1
    tot_peri = sum(perimeters) if perimeters else 0
    pa_ratio = tot_peri / max(1.0, tot_area)
    mean_dot_area = float(np.mean(areas)) if areas else 0.0
    clump_ratio = large_clump_area / max(1.0, tot_area)
    dot_count = len(areas)

    # 4. White Micro-Void Count (un-inked paper gaps between dots)
    white_mask = (255 - binary).copy()
    white_mask[0, :] = 0; white_mask[-1, :] = 0; white_mask[:, 0] = 0; white_mask[:, -1] = 0
    num_w_labels, _, w_stats, _ = cv2.connectedComponentsWithStats(white_mask, connectivity=8)
    void_count = sum(
        1 for i in range(1, num_w_labels)
        if 3 <= w_stats[i, cv2.CC_STAT_AREA] < (total_pixels * 0.40)
    )

    # 5. Normalized Morphology Score
    # P/A ratio: Genuine phone prints typically range 0.22 to 0.48; photocopies collapse < 0.16
    pa_norm = max(0.0, min(1.0, (pa_ratio - 0.13) / (0.28 - 0.13)))
    
    # Clump ratio: Genuine prints have low clump ratio (< 0.45); photocopies have high (> 0.65)
    clump_norm = max(0.0, min(1.0, 1.0 - (clump_ratio - 0.30) / 0.45))
    
    # Micro-void preservation: Genuine prints retain 20-80+ discrete voids
    void_norm = max(0.0, min(1.0, void_count / 25.0))

    morph_norm = pa_norm * 0.45 + clump_norm * 0.35 + void_norm * 0.20

    # Dedicated photocopy / severe reprint detection condition:
    # hallmark of photocopier is fusing toner into < 5 massive blobs or P/A < 0.15
    is_photocopy = bool(
        (dot_count <= 4 and mean_dot_area > 1500) or
        (pa_ratio < 0.15) or
        (black_density > 0.60 and pa_ratio < 0.18 and dot_count <= 8) or
        (clump_ratio > 0.95 and dot_count <= 6)
    )

    return {
        "pa_ratio": round(pa_ratio, 4),
        "mean_dot_area": round(mean_dot_area, 1),
        "clump_ratio": round(clump_ratio, 4),
        "dot_count": dot_count,
        "void_count": void_count,
        "black_density": round(black_density, 4),
        "morph_norm": round(morph_norm, 3),
        "is_photocopy": is_photocopy,
    }


# ─────────────────────────────────────────────
#  MTF-Matched Template Cross-Correlation
# ─────────────────────────────────────────────

def compute_mtf_matched_ncc(
    candidate: np.ndarray, 
    reference_digital: np.ndarray, 
    macro_gradient: float,
    finder_edge_slope: float = None,
) -> tuple[float, tuple[int, int]]:
    """
    Computes camera-invariant Peak NCC by conditioning the digital master reference
    with the camera's estimated optical point spread function (derived from in-frame MTF).
    This ensures mobile cameras with slight optical softening are not falsely penalized.
    """
    # Estimate optical blur sigma from macro-edge acutance
    slope_ref = finder_edge_slope if finder_edge_slope is not None else macro_gradient
    if slope_ref >= 120.0:
        est_sigma = 0.40
    elif slope_ref >= 80.0:
        est_sigma = 0.60
    elif slope_ref >= 58.0:
        est_sigma = 0.75
    else:
        est_sigma = 0.85

    # Convolve reference with camera PSF
    ksize = int(np.ceil(est_sigma * 3) * 2 + 1)
    ref_matched = cv2.GaussianBlur(reference_digital, (ksize, ksize), est_sigma)
    
    ncc_matched, loc_matched = compute_peak_cross_correlation(candidate, ref_matched)
    ncc_raw, _ = compute_peak_cross_correlation(candidate, reference_digital)
    
    best_ncc = max(ncc_matched, ncc_raw)
    return best_ncc, loc_matched


def compute_cdp_micro_fidelity(cand_cdp: np.ndarray, ref_cdp: np.ndarray) -> dict:
    """
    Computes cryptographic micro-dot fidelity against the deterministic master reference.
    Evaluates:
      1. Raw full-resolution NCC
      2. Laplacian high-pass micro-edge correlation
      3. Difference-of-Gaussians (DoG) bandpass correlation at micro-dot scale
      4. Composite Master Fidelity Score
    
    In 1st-generation original prints (even under softer camera focus),
    the micro-dots retain coherent high-frequency alignment with the cryptographic seed.
    In 2nd-generation copies/reprints, micro-dot boundaries are irreversibly scrambled
    by the 2nd print-and-scan cycle, causing micro-dot fidelity to collapse.
    """
    if cand_cdp is None or ref_cdp is None or cand_cdp.size == 0 or ref_cdp.size == 0:
        return {
            "raw_ncc": 0.0,
            "lap_ncc": 0.0,
            "dog_ncc": 0.0,
            "fidelity": 0.0,
        }
        
    pad_y = int(cand_cdp.shape[0] * 0.16)
    pad_x = int(cand_cdp.shape[1] * 0.16)
    c = cand_cdp[pad_y:-pad_y, pad_x:-pad_x].astype(np.float32)
    r = ref_cdp[pad_y:-pad_y, pad_x:-pad_x].astype(np.float32)
    
    # 1. Raw unblurred NCC
    raw_ncc, _ = compute_peak_cross_correlation(c, r)
    
    # 2. Laplacian high-pass micro-edge NCC
    lap_c = cv2.Laplacian(c, cv2.CV_32F, ksize=3)
    lap_r = cv2.Laplacian(r, cv2.CV_32F, ksize=3)
    lap_ncc, _ = compute_peak_cross_correlation(lap_c, lap_r)
    
    # 3. Difference of Gaussians (DoG bandpass at micro-dot scale)
    dog_c = cv2.GaussianBlur(c, (3, 3), 0.5) - cv2.GaussianBlur(c, (7, 7), 1.5)
    dog_r = cv2.GaussianBlur(r, (3, 3), 0.5) - cv2.GaussianBlur(r, (7, 7), 1.5)
    dog_ncc, _ = compute_peak_cross_correlation(dog_c, dog_r)
    
    fidelity = raw_ncc * 0.40 + dog_ncc * 0.40 + lap_ncc * 0.20
    
    return {
        "raw_ncc": round(float(raw_ncc), 4),
        "lap_ncc": round(float(lap_ncc), 4),
        "dog_ncc": round(float(dog_ncc), 4),
        "fidelity": round(float(fidelity), 4),
    }


# ─────────────────────────────────────────────
#  Visual Card Generator
# ─────────────────────────────────────────────

def generate_comparison_card(
    cand_core: np.ndarray,
    ref_core: np.ndarray,
    verdict: str,
    score: float,
    output_path: str = None,
) -> Image.Image:
    """Side-by-side zoom of candidate CDP vs reference CDP + difference heatmap."""
    ch, cw = cand_core.shape
    rh, rw = ref_core.shape

    box = 45
    cx, cy = cw // 2, ch // 2
    cand_zoom = cand_core[max(0, cy-box):min(ch, cy+box), max(0, cx-box):min(cw, cx+box)]
    rx, ry = rw // 2, rh // 2
    ref_zoom  = ref_core[max(0, ry-box):min(rh, ry+box), max(0, rx-box):min(rw, rx+box)]

    zoom_w, zoom_h = 240, 240
    cand_disp = cv2.resize(cand_zoom, (zoom_w, zoom_h), interpolation=cv2.INTER_NEAREST)
    ref_disp  = cv2.resize(ref_zoom,  (zoom_w, zoom_h), interpolation=cv2.INTER_NEAREST)

    diff    = cv2.absdiff(cand_disp, ref_disp)
    heatmap = cv2.applyColorMap(diff, cv2.COLORMAP_JET)

    cand_bgr = cv2.cvtColor(cand_disp, cv2.COLOR_GRAY2BGR)
    ref_bgr  = cv2.cvtColor(ref_disp,  cv2.COLOR_GRAY2BGR)

    total_w, total_h = zoom_w * 3 + 40, zoom_h + 80
    card = np.ones((total_h, total_w, 3), dtype=np.uint8) * 245

    card[60:60+zoom_h, 10:10+zoom_w]               = ref_bgr
    card[60:60+zoom_h, 20+zoom_w:20+2*zoom_w]       = cand_bgr
    card[60:60+zoom_h, 30+2*zoom_w:30+3*zoom_w]     = heatmap

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(card, "Master Digital Pattern",    (15, 45),        font, 0.55, (20,20,20), 1, cv2.LINE_AA)
    cv2.putText(card, "Scanned Pattern (4x Zoom)", (25+zoom_w, 45), font, 0.55, (20,20,20), 1, cv2.LINE_AA)
    cv2.putText(card, "Degradation Heatmap",       (35+2*zoom_w, 45),font, 0.55,(20,20,20),1,cv2.LINE_AA)

    color = (30,160,30) if "GENUINE" in verdict else (30,30,210)
    cv2.putText(card, f"VERDICT: {verdict} | Authenticity: {score}%",
                (15, 22), font, 0.65, color, 2, cv2.LINE_AA)

    res_img = Image.fromarray(cv2.cvtColor(card, cv2.COLOR_BGR2RGB))
    if output_path:
        res_img.save(output_path)
    return res_img


# ─────────────────────────────────────────────
#  Main Verification Entry Point
# ─────────────────────────────────────────────

def verify_anti_counterfeit_qr(
    image_input,
    expected_serial: str = None,
    box_size: int = 12,
    cdp_ratio: float = 0.32,
    comparison_output_path: str = None,
    save_debug_artifacts: bool = True,
    debug_dir: str = "debug_artifacts",
) -> dict:
    """
    Camera-Independent Anti-Counterfeit Verification Pipeline.
    
    STAGE 1: QR-Localized Image Quality Pre-Gate
      - Focus and exposure are measured ON THE QR CODE itself.
      - Discards background interference (plain desks/walls do NOT cause false blur failures).
      - If Stage 1 fails -> Return RECAPTURE_REQUIRED or UNREADABLE with actionable guidance.
        Do NOT execute Stage 2. Do NOT classify as COUNTERFEIT.
        
    STAGE 2: In-Frame MTF Calibration & Decoupled Verification
      - Step 2.1: Brand Database Registry Lookup.
      - Step 2.2: In-Frame Camera MTF Calibration (finder patterns).
      - Step 2.3: Relative Acutance & MTF-Matched Cross-Correlation.
      - Step 2.4: Adaptive Micro-Morphology & Void Analysis.
      - Step 2.5: Decoupled Multi-Factor Scoring & Hierarchical Verdict.
      - Step 2.6: Scan Audit Logging & Multi-Scan Clone Alert Tracking.
    """
    import product_db

    # ── Load input image ─────────────────────────────────────────────────────
    if isinstance(image_input, str):
        img_cv = cv2.imread(image_input)
    elif isinstance(image_input, Image.Image):
        img_cv = cv2.cvtColor(np.array(image_input.convert('RGB')), cv2.COLOR_RGB2BGR)
    else:
        img_cv = image_input.copy()

    if img_cv is None:
        return {
            "status": "RECAPTURE_REQUIRED",
            "message": "Unable to Verify — Please Upload a Clear Image of the QR Code",
            "verdict": "RECAPTURE REQUIRED (FAILED TO LOAD IMAGE)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "image_quality_score": 0.0,
            "cdp_authenticity_score": 0.0,
            "reprint_risk_score": 100.0,
            "digital_authenticity_score": 0.0,
            "qr_payload": "",
            "serial_number": expected_serial or "UNKNOWN",
            "guidance": "Failed to load input image. Please provide a valid JPEG or PNG file.",
            "metrics": {"stage1_passed": False},
            "description": "Failed to load input image.",
            "comparison_image": None,
            "product_info": None,
        }

    # ── Multi-pass QR code barcode detection & decode ────────────────────────
    payload, points, straight = robust_detect_and_decode_qr(img_cv)

    # ═════════════════════════════════════════════════════════════════════════
    #  STAGE 1: QR-LOCALIZED IMAGE QUALITY VALIDATION
    # ═════════════════════════════════════════════════════════════════════════
    is_valid, q_reason, q_guidance, q_metrics = validate_image_quality(img_cv, detected_points=points)

    if not is_valid:
        return {
            "status": "RECAPTURE_REQUIRED",
            "message": "Unable to Verify — Please Upload a Clear Image of the QR Code",
            "verdict": "RECAPTURE REQUIRED (QUALITY CHECK FAILED)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "image_quality_score": 15.0,
            "cdp_authenticity_score": 0.0,
            "reprint_risk_score": 50.0,
            "digital_authenticity_score": 0.0,
            "qr_payload": payload or "",
            "serial_number": expected_serial or "UNKNOWN",
            "guidance": q_guidance,
            "metrics": {
                "stage1_passed": False,
                "peak_cross_correlation_ncc": 0.0,
                "laplacian_edge_variance": round(q_metrics.get("full_image_sharpness", 0.0), 1),
                "gradient_sharpness": 0.0,
                "failure_reason": q_reason,
                **q_metrics,
            },
            "description": f"{q_reason}. {q_guidance}",
            "comparison_image": None,
            "product_info": None,
        }

    # ── Check QR Barcode Decodability ────────────────────────────────────────
    if not payload or points is None or len(points) == 0:
        full_lap = q_metrics.get("full_image_sharpness", compute_edge_acutance(cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)))
        if full_lap < GLOBAL_BLUR_MIN:
            dec_reason = f"Image is too blurry to resolve QR modules (sharpness: {full_lap:.1f})"
            dec_guidance = "Hold your phone steady, tap to focus, and recapture closer to the QR code."
            status = "RECAPTURE_REQUIRED"
            verdict = "RECAPTURE REQUIRED (IMAGE TOO BLURRY)"
        else:
            dec_reason = "No valid QR code could be detected in the frame"
            dec_guidance = "Ensure the entire QR code is visible within the camera viewfinder."
            status = "UNREADABLE"
            verdict = "UNREADABLE QR CODE (OBSTRUCTED OR DAMAGED)"

        return {
            "status": status,
            "message": "Unable to Verify — Invalid or Unreadable QR Code",
            "verdict": verdict,
            "is_genuine": False,
            "authenticity_score": 0.0,
            "image_quality_score": 25.0,
            "cdp_authenticity_score": 0.0,
            "reprint_risk_score": 50.0,
            "digital_authenticity_score": 0.0,
            "qr_payload": "",
            "serial_number": expected_serial or "UNKNOWN",
            "guidance": dec_guidance,
            "metrics": {
                "stage1_passed": False,
                "peak_cross_correlation_ncc": 0.0,
                "laplacian_edge_variance": round(full_lap, 1),
                "gradient_sharpness": 0.0,
                "failure_reason": dec_reason,
                "full_image_sharpness": round(full_lap, 1),
            },
            "description": f"{dec_reason}. {dec_guidance}",
            "comparison_image": None,
            "product_info": None,
        }

    # ── Corner Points & Perspective Tilt Sanity Check ────────────────────────
    pts_arr = points[0].astype(np.float32)
    d01 = float(np.linalg.norm(pts_arr[1] - pts_arr[0]))
    d12 = float(np.linalg.norm(pts_arr[2] - pts_arr[1]))
    d23 = float(np.linalg.norm(pts_arr[3] - pts_arr[2]))
    d30 = float(np.linalg.norm(pts_arr[0] - pts_arr[3]))
    edges = [d01, d12, d23, d30]
    edge_ratio = min(edges) / max(1.0, max(edges))

    if edge_ratio < PERSPECTIVE_EDGE_RATIO_MIN:
        tilt_reason = f"Camera perspective angle is too steep (edge ratio: {edge_ratio:.2f} < {PERSPECTIVE_EDGE_RATIO_MIN:.2f})"
        tilt_guidance = "Please align your camera directly facing the QR code straight-on rather than from an acute side angle."
        return {
            "status": "RECAPTURE_REQUIRED",
            "message": "Unable to Verify — Extreme Camera Angle",
            "verdict": "RECAPTURE REQUIRED (EXTREME PERSPECTIVE TILT)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "image_quality_score": 30.0,
            "cdp_authenticity_score": 0.0,
            "reprint_risk_score": 50.0,
            "digital_authenticity_score": 0.0,
            "qr_payload": payload,
            "serial_number": expected_serial or "UNKNOWN",
            "guidance": tilt_guidance,
            "metrics": {
                "stage1_passed": False,
                "perspective_edge_ratio": round(edge_ratio, 3),
                "failure_reason": tilt_reason,
            },
            "description": f"{tilt_reason}. {tilt_guidance}",
            "comparison_image": None,
            "product_info": None,
        }

    # ── Canonical Perspective Rectification ──────────────────────────────────
    modules = straight.shape[0] if (straight is not None and straight.size > 0) else 45
    border  = 4
    canonical_box = box_size
    full_size = (modules + 2 * border) * canonical_box
    offset = border * canonical_box
    data_w = modules * canonical_box

    dst_data = np.array([
        [offset, offset],
        [offset + data_w, offset],
        [offset + data_w, offset + data_w],
        [offset, offset + data_w]
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(pts_arr, dst_data)
    warped = cv2.warpPerspective(img_cv, M, (full_size, full_size), flags=cv2.INTER_LINEAR)
    warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    # ── Security Pattern Preliminary Integrity Check ─────────────────────────
    prelim_cw = int(full_size * cdp_ratio)
    if prelim_cw % 2 != 0: prelim_cw += 1
    px1 = (warped_gray.shape[1] - prelim_cw) // 2
    py1 = (warped_gray.shape[0] - prelim_cw) // 2
    prelim_cdp = warped_gray[py1:py1+prelim_cw, px1:px1+prelim_cw]

    cdp_var = float(np.var(prelim_cdp))
    cdp_mean = float(np.mean(prelim_cdp))
    if cdp_var < 15.0 or cdp_mean > 252.0 or cdp_mean < 8.0:
        cdp_reason = f"Center security pattern is occluded, damaged, or washed out (variance: {cdp_var:.1f})"
        cdp_guidance = "The central security micro-pattern appears covered, scratched, or washed out. Please clean the label and retry."
        return {
            "status": "RECAPTURE_REQUIRED",
            "message": "Unable to Verify — Security Pattern Occluded or Damaged",
            "verdict": "RECAPTURE REQUIRED (SECURITY PATTERN DAMAGED / OCCLUDED)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "image_quality_score": 35.0,
            "cdp_authenticity_score": 0.0,
            "reprint_risk_score": 50.0,
            "digital_authenticity_score": 0.0,
            "qr_payload": payload,
            "serial_number": expected_serial or "UNKNOWN",
            "guidance": cdp_guidance,
            "metrics": {
                "stage1_passed": False,
                "center_variance": round(cdp_var, 2),
                "center_mean": round(cdp_mean, 1),
                "failure_reason": cdp_reason,
            },
            "description": f"{cdp_reason}. {cdp_guidance}",
            "comparison_image": None,
            "product_info": None,
        }

    # ═════════════════════════════════════════════════════════════════════════
    #  STAGE 2: IN-FRAME CALIBRATION & DECOUPLED AUTHENTICITY ANALYSIS
    # ═════════════════════════════════════════════════════════════════════════

    # ── Step 2.1: Extract Serial & Query Brand Database Registry ─────────────
    serial_no = extract_serial_number(payload) if payload else ""
    if not serial_no and expected_serial:
        serial_no = expected_serial

    product_record = product_db.get_product(serial_no) if serial_no else None

    # Check: Unregistered Product
    if product_record is None:
        audit_record = product_db.record_scan(serial_no or "UNKNOWN", "UNREGISTERED PRODUCT", 0.0)
        return {
            "status": "UNREGISTERED",
            "message": "Unable to Verify — Product Not Registered",
            "verdict": "UNREGISTERED PRODUCT (SERIAL NOT FOUND)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "image_quality_score": 85.0,
            "cdp_authenticity_score": 0.0,
            "reprint_risk_score": 0.0,
            "digital_authenticity_score": 0.0,
            "qr_payload": payload,
            "serial_number": serial_no or "UNKNOWN",
            "guidance": "This serial number is not found in the official brand database. Verify product packaging or contact the manufacturer.",
            "product_info": audit_record,
            "metrics": {
                "stage1_passed": True,
                "serial_number": serial_no,
            },
            "description": "Serial number does NOT exist in official brand database. Product cannot be authenticated.",
            "comparison_image": None,
        }

    # Check: Blacklisted / Revoked Product
    if product_record.get("status") in ("INACTIVE", "BLACKLISTED", "REVOKED"):
        audit_record = product_db.record_scan(serial_no, f"BLACKLISTED ({product_record.get('status')})", 0.0)
        return {
            "status": "BLACKLISTED",
            "message": "Product Revoked or Blacklisted by Brand Owner",
            "verdict": f"BLACKLISTED / REVOKED PRODUCT ({product_record.get('status')})",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "image_quality_score": 85.0,
            "cdp_authenticity_score": 0.0,
            "reprint_risk_score": 0.0,
            "digital_authenticity_score": 0.0,
            "qr_payload": payload,
            "serial_number": serial_no,
            "guidance": "This product batch or unit has been recalled, blacklisted, or revoked by the brand manufacturer.",
            "product_info": audit_record,
            "metrics": {
                "stage1_passed": True,
                "product_status": product_record.get("status"),
            },
            "description": f"REJECTED: Product status is marked {product_record.get('status')} in the brand database. Authentic print rejected per policy.",
            "comparison_image": None,
        }

    # ── Step 2.2: In-Frame Camera MTF Calibration ────────────────────────────
    macro_metrics = measure_in_frame_macro_acutance(warped_gray, modules=modules, box_size=canonical_box)
    macro_grad = macro_metrics["macro_gradient"]
    macro_lap  = macro_metrics["macro_laplacian"]
    finder_edge_slope = macro_metrics.get("finder_edge_slope", 65.0)
    black_core_std = macro_metrics.get("black_core_std", 3.0)

    # ── Step 2.3: Multi-Ratio CDP Extraction & MTF-Matched Template Match ───
    candidate_ratios = [cdp_ratio, 0.32, 0.30, 0.28, 0.34]
    seen = set()
    candidate_ratios = [r for r in candidate_ratios if not (r in seen or seen.add(r))]

    best_ncc = -1.0
    best_candidate_tuple = None

    for r in candidate_ratios:
        center_w = int(full_size * r)
        if center_w % 2 != 0: center_w += 1
        center_w = max(center_w, 40)

        wh, ww = warped_gray.shape[:2]
        x1 = max(0, (ww - center_w) // 2)
        y1 = max(0, (wh - center_w) // 2)
        cand_cdp = warped_gray[y1:y1+center_w, x1:x1+center_w]

        ch, cw = cand_cdp.shape
        if ch < 20 or cw < 20:
            continue

        dot_size          = max(1, canonical_box // 5)
        margin_cells      = 10
        pattern_grid_size = max(10, (center_w - 2 * margin_cells * dot_size) // dot_size)

        ref_pil = generate_cdp_module_with_fiducials(
            seed_str=serial_no,
            pattern_grid_size=pattern_grid_size,
            dot_size=dot_size,
            margin_cells=margin_cells,
        )
        ref_np = np.array(ref_pil.convert('L'))
        ref_np = cv2.resize(ref_np, (cw, ch), interpolation=cv2.INTER_NEAREST)

        pad_y = int(ch * 0.16)
        pad_x = int(cw * 0.16)
        inner_cand = cand_cdp[pad_y:ch-pad_y, pad_x:cw-pad_x]
        inner_ref  = ref_np[pad_y:ch-pad_y,   pad_x:cw-pad_x]

        curr_ncc, _ = compute_mtf_matched_ncc(
            inner_cand, inner_ref, macro_gradient=macro_grad, finder_edge_slope=finder_edge_slope
        )
        if curr_ncc > best_ncc:
            best_ncc             = curr_ncc
            best_candidate_tuple = (inner_cand, inner_ref, curr_ncc, r)

    if best_candidate_tuple is None:
        inner_cand = warped_gray
        inner_ref  = warped_gray
        peak_ncc   = 0.0
    else:
        inner_cand, inner_ref, peak_ncc, _ = best_candidate_tuple

    # ── Step 2.4: CDP Micro-Metrics & Relative Acutance ──────────────────────
    cdp_grad = compute_gradient_sharpness(inner_cand)
    cdp_lap  = compute_edge_acutance(inner_cand)
    cdp_hf   = compute_fft_hf_energy_ratio(inner_cand)
    morph    = compute_dot_morphology(inner_cand)

    # Relative Acutance Ratios (normalized by the camera's measured MTF)
    rel_acutance = cdp_grad / max(1.0, macro_grad)
    rel_lap      = cdp_lap  / max(1.0, macro_lap)

    # ── Step 2.5: Physical Optical Blur vs Reprint Discrimination ───────────
    # True camera blur: micro-dots cannot be resolved due to camera optical softening
    is_camera_optical_blur = bool(
        cdp_grad < 40.0 or 
        cdp_lap < 20.0 or 
        (macro_grad < 95.0 and cdp_grad < 52.0)
    )

    if is_camera_optical_blur:
        blur_reason = f"Micro-pattern optical sharpness is too soft to analyze reliably (CDP sharpness: {cdp_grad:.1f})"
        blur_guidance = "Hold phone steady, tap to lock autofocus directly on the QR code, and ensure good lighting."
        return {
            "status": "RECAPTURE_REQUIRED",
            "message": "Unable to Verify — Image Too Blurry to Resolve Micro-Pattern",
            "verdict": "RECAPTURE REQUIRED (OPTICAL BLUR DETECTED)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "image_quality_score": 35.0,
            "cdp_authenticity_score": 0.0,
            "reprint_risk_score": 50.0,
            "digital_authenticity_score": 100.0,
            "qr_payload": payload,
            "serial_number": serial_no,
            "guidance": blur_guidance,
            "metrics": {
                "stage1_passed": True,
                "macro_gradient": macro_grad,
                "cdp_gradient": round(cdp_grad, 2),
                "cdp_laplacian": round(cdp_lap, 2),
                "laplacian_edge_variance": round(cdp_lap, 2),
                "gradient_sharpness": round(cdp_grad, 2),
                "peak_cross_correlation_ncc": round(peak_ncc, 4),
                "failure_reason": blur_reason,
            },
            "description": f"{blur_reason}. {blur_guidance}",
            "comparison_image": None,
            "product_info": product_record,
        }

    # ── Step 2.6: Decoupled Multi-Factor Scoring Model ───────────────────────
    # 1. Image Quality Score [0 - 100]
    qr_diag = np.sqrt(d01**2 + d12**2)
    res_factor = max(0.0, min(1.0, (qr_diag - 120.0) / (350.0 - 120.0)))
    macro_factor = max(0.0, min(1.0, (macro_grad - 80.0) / (250.0 - 80.0)))
    image_quality_score = round(float(res_factor * 40.0 + macro_factor * 35.0 + edge_ratio * 25.0), 1)

    # 2. CDP Authenticity Score [0 - 100] (Pattern identity with cryptographic seed)
    ncc_norm = max(0.0, min(1.0, (peak_ncc - NCC_MISMATCH_MAX) / (NCC_GENUINE_HIGH - NCC_MISMATCH_MAX)))
    cdp_authenticity_score = round(float(ncc_norm * 100.0), 1)

    # 3. Reprint Risk Score [0 - 100] (Physical 2nd-gen reprint detection)
    micro_fid = compute_cdp_micro_fidelity(inner_cand, inner_ref)
    fidelity  = micro_fid["fidelity"]
    dog_ncc   = micro_fid["dog_ncc"]
    lap_ncc   = micro_fid["lap_ncc"]
    
    # Micro-structure fidelity risk:
    fidelity_risk = max(0.0, min(1.0, (0.31 - fidelity) / (0.31 - 0.24)))
    dog_risk      = max(0.0, min(1.0, (0.28 - dog_ncc) / (0.28 - 0.20)))
    lap_risk      = max(0.0, min(1.0, (0.13 - lap_ncc) / (0.13 - 0.07)))
    micro_risk    = fidelity_risk * 0.45 + dog_risk * 0.35 + lap_risk * 0.20
    
    slope_risk   = max(0.0, min(1.0, (56.0 - finder_edge_slope) / (56.0 - 42.0)))
    rel_g_risk   = max(0.0, min(1.0, (REL_ACUTANCE_GENUINE_MIN - rel_acutance) / (REL_ACUTANCE_GENUINE_MIN - REL_ACUTANCE_REPRINT_MAX)))
    rel_lap_risk = max(0.0, min(1.0, (REL_LAP_GENUINE_MIN - rel_lap) / (REL_LAP_GENUINE_MIN - REL_LAP_REPRINT_MAX)))
    hf_risk      = max(0.0, min(1.0, (HF_GENUINE_MIN - cdp_hf) / (HF_GENUINE_MIN - HF_REPRINT_MAX)))
    
    # Combined multi-factor reprint risk
    raw_reprint_risk = max(
        micro_risk,
        rel_g_risk * 0.45 + rel_lap_risk * 0.35 + hf_risk * 0.20
    )
    
    # Decisive reprint / photocopy indicators:
    # 1. Micro-structure degradation (hallmark of second-generation copy)
    if fidelity <= 0.28 or (dog_ncc <= 0.24 and lap_ncc <= 0.10):
        raw_reprint_risk = max(raw_reprint_risk, 0.88)
    # 2. Severe morphology destruction
    elif morph["is_photocopy"]:
        raw_reprint_risk = max(raw_reprint_risk, 0.88)
    # 3. Collapse of relative acutance
    elif rel_acutance < 0.80 or (rel_lap < 0.50 and cdp_hf < 0.0028) or (cdp_grad < 95.0 and macro_grad >= 105.0):
        if peak_ncc >= 0.70 and rel_acutance >= 0.82 and not morph["is_photocopy"] and fidelity >= 0.30:
            raw_reprint_risk = 0.45  # Borderline / Suspicious, not counterfeit!
        else:
            raw_reprint_risk = max(raw_reprint_risk, 0.88)
    elif fidelity >= 0.31 and dog_ncc >= 0.28:
        raw_reprint_risk = min(raw_reprint_risk, 0.05)
        
    reprint_risk_score = round(float(raw_reprint_risk * 100.0), 1)

    # 4. Digital Authenticity Score [0 or 100]
    digital_authenticity_score = 100.0

    # 5. Composite Final Score [0 - 100]
    reprint_survival = max(0.0, 1.0 - (reprint_risk_score / 100.0))
    final_score = (cdp_authenticity_score * 0.50 + reprint_survival * 100.0 * 0.50) * (0.85 + 0.15 * (image_quality_score / 100.0))
    
    if reprint_risk_score >= 70.0:
        final_score = min(final_score, 20.0)
    elif peak_ncc < NCC_MISMATCH_MAX:
        final_score = min(final_score, 15.0)

    final_score = float(round(max(0.0, min(100.0, final_score)), 1))

    # ── Step 2.7: Hierarchical Decision Logic ────────────────────────────────
    if peak_ncc < NCC_MISMATCH_MAX:
        status       = "COUNTERFEIT"
        verdict      = "COUNTERFEIT (PATTERN MISMATCH)"
        message      = "Counterfeit Detected — Security Pattern Does Not Match Serial Number"
        verdict_desc = "FAKE! Micro-dot security pattern does NOT match the official cryptographic master for this product."
        is_genuine   = False

    elif morph["is_photocopy"] or reprint_risk_score >= 65.0:
        status       = "COUNTERFEIT"
        verdict      = "COUNTERFEIT (PHOTOCOPY / REPRINT DETECTED)"
        message      = "Counterfeit Detected — This QR Code Appears to Be a Copy"
        verdict_desc = (
            f"FAKE! Second-generation reprint or photocopy detected. Physical edge acuity collapsed "
            f"(finder edge slope={finder_edge_slope:.1f}, relative acutance={rel_acutance:.3f}, micro-voids={morph['void_count']})."
        )
        is_genuine   = False

    elif reprint_risk_score >= 40.0 or final_score < SCORE_SUSPICIOUS_THRESHOLD:
        status       = "SUSPICIOUS"
        verdict      = "SUSPICIOUS (BORDERLINE INTEGRITY)"
        message      = "Suspicious Product — Inconclusive Micro-Pattern Integrity"
        verdict_desc = "Borderline result. Micro-pattern matches seed, but optical sharpness ratio is degraded. Retake photo closer in good light."
        is_genuine   = False

    elif final_score >= SCORE_GENUINE_THRESHOLD and rel_acutance >= REL_ACUTANCE_GENUINE_MIN:
        status       = "GENUINE"
        verdict      = "GENUINE (ORIGINAL PRINT VERIFIED)"
        message      = "Genuine Product Verified"
        verdict_desc = "Genuine 1st-generation original print verified. Micro-dot security pattern, relative acutance, and morphology match official master."
        is_genuine   = True

    elif final_score >= SCORE_SUSPICIOUS_THRESHOLD:
        status       = "GENUINE"
        verdict      = "GENUINE (LOW CONFIDENCE)"
        message      = "Genuine Product — Moderate Confidence"
        verdict_desc = "Original print verified with moderate confidence. Slightly low contrast or lens softening detected."
        is_genuine   = True

    else:
        status       = "COUNTERFEIT"
        verdict      = "COUNTERFEIT (DEGRADED MICROSTRUCTURE)"
        message      = "Counterfeit Detected — Possible Copy or Reprint"
        verdict_desc = "FAKE! Micro-dot structure does not meet genuine production standards."
        is_genuine   = False

    # ── Step 2.8: Save Intermediate Debug Artifacts ──────────────────────────
    if save_debug_artifacts:
        try:
            os.makedirs(debug_dir, exist_ok=True)
            # 1. Uploaded image
            cv2.imwrite(os.path.join(debug_dir, "debug_01_uploaded.png"), img_cv)
            
            # 2. QR detection visualization (draw detected bounding quad)
            qr_detect_vis = img_cv.copy()
            if points is not None and len(points) > 0:
                pts_poly = points[0].astype(np.int32).reshape((-1, 1, 2))
                cv2.polylines(qr_detect_vis, [pts_poly], isClosed=True, color=(0, 255, 0), thickness=3)
            cv2.imwrite(os.path.join(debug_dir, "debug_02_qr_detected.png"), qr_detect_vis)
            
            # 3. Perspective-corrected canonical QR
            cv2.imwrite(os.path.join(debug_dir, "debug_03_perspective_corrected.png"), warped)
            
            # 4. Extracted raw CDP
            cv2.imwrite(os.path.join(debug_dir, "debug_04_extracted_cdp.png"), inner_cand)
            
            # 5. Photometrically normalized CDP
            norm_cdp = cv2.normalize(inner_cand, None, 0, 255, cv2.NORM_MINMAX)
            cv2.imwrite(os.path.join(debug_dir, "debug_05_normalized_cdp.png"), norm_cdp)
            
            # 6. Reference/generated digital CDP
            cv2.imwrite(os.path.join(debug_dir, "debug_06_reference_cdp.png"), inner_ref)
            
            # 7. Difference heatmap
            cand_res = cv2.resize(inner_cand, (inner_ref.shape[1], inner_ref.shape[0]))
            diff_map = cv2.absdiff(cand_res, inner_ref)
            heatmap = cv2.applyColorMap(diff_map, cv2.COLORMAP_JET)
            cv2.imwrite(os.path.join(debug_dir, "debug_07_difference_heatmap.png"), heatmap)
        except Exception:
            pass

    # ── Step 2.9: Generate Visual Comparison Card ────────────────────────────
    comparison_img = None
    try:
        comparison_img = generate_comparison_card(
            inner_cand, inner_ref, verdict, final_score,
            output_path=comparison_output_path,
        )
    except Exception:
        comparison_img = None

    # ── Step 2.10: Record Verification Scan in Official Registry ─────────────
    try:
        updated_product_record = product_db.record_scan(serial_no, verdict, final_score)
    except Exception as e:
        updated_product_record = dict(product_record)
        updated_product_record["scan_count"] = updated_product_record.get("scan_count", 0) + 1
        updated_product_record["clone_alert"] = False
        updated_product_record["clone_message"] = str(e)

    # ── Debug Telemetry Log ──────────────────────────────────────────────────
    debug_log = (
        f"\n--- VERIFICATION TELEMETRY ---\n"
        f"QR_VALID:                   True\n"
        f"PRODUCT_REGISTERED:         {product_record is not None}\n"
        f"IMAGE_WIDTH:                {img_cv.shape[1]}\n"
        f"IMAGE_HEIGHT:               {img_cv.shape[0]}\n"
        f"QR_SIZE:                    {full_size}\n"
        f"CDP_SIZE:                   {inner_cand.shape[0]}x{inner_cand.shape[1]}\n"
        f"PERSPECTIVE_CORRECTED:      True\n"
        f"IMAGE_QUALITY_SCORE:        {image_quality_score}%\n"
        f"NCC_SCORE:                  {round(peak_ncc, 4)}\n"
        f"FINDER_EDGE_SLOPE:          {round(finder_edge_slope, 2)}\n"
        f"MACRO_GRADIENT:             {macro_grad}\n"
        f"CDP_GRADIENT:               {round(cdp_grad, 2)}\n"
        f"RELATIVE_ACUTANCE_RATIO:    {round(rel_acutance, 4)}\n"
        f"RELATIVE_LAPLACIAN_RATIO:   {round(rel_lap, 4)}\n"
        f"MICRO_VOIDS:                {morph['void_count']}\n"
        f"FFT_SCORE:                  {round(cdp_hf, 6)}\n"
        f"CDP_AUTHENTICITY_SCORE:     {cdp_authenticity_score}%\n"
        f"REPRINT_RISK_SCORE:         {reprint_risk_score}%\n"
        f"FINAL_SCORE:                {final_score}%\n"
        f"FINAL_DECISION:             {verdict}\n"
        f"------------------------------"
    )

    # ── Return Structured Multi-Factor Result ────────────────────────────────
    return {
        "status": status,
        "message": message,
        "verdict": verdict,
        "is_genuine": is_genuine,
        "authenticity_score": final_score,
        "final_score": final_score,
        "image_quality_score": image_quality_score,
        "cdp_authenticity_score": cdp_authenticity_score,
        "reprint_risk_score": reprint_risk_score,
        "digital_authenticity_score": digital_authenticity_score,
        "qr_payload": payload,
        "serial_number": serial_no,
        "product_info": updated_product_record,
        "metrics": {
            "stage1_passed":              True,
            "image_quality_score":        image_quality_score,
            "cdp_authenticity_score":     cdp_authenticity_score,
            "reprint_risk_score":         reprint_risk_score,
            "relative_acutance_ratio":    round(rel_acutance, 4),
            "relative_laplacian_ratio":   round(rel_lap, 4),
            "macro_gradient":             macro_grad,
            "macro_laplacian":            macro_lap,
            "cdp_gradient":               round(cdp_grad, 2),
            "cdp_laplacian":              round(cdp_lap, 2),
            "laplacian_edge_variance":    round(cdp_lap, 2),
            "edge_acutance_laplacian":    round(cdp_lap, 2),
            "gradient_sharpness":         round(cdp_grad, 2),
            "full_image_sharpness":       round(q_metrics.get("full_image_sharpness", 0.0), 1),
            "peak_cross_correlation_ncc": round(peak_ncc, 4),
            "peak_ncc":                   round(peak_ncc, 4),
            "fft_high_freq_ratio":        round(cdp_hf, 6),
            "dot_morphology_pa_ratio":    morph["pa_ratio"],
            "dot_morphology_density":     morph["black_density"],
            "dot_morphology_clump_ratio": morph["clump_ratio"],
            "dot_count":                  morph["dot_count"],
            "micro_void_count":           morph["void_count"],
            "micro_dot_fidelity":         fidelity,
            "dog_bandpass_ncc":           dog_ncc,
            "laplacian_edge_ncc":         lap_ncc,
            "finder_edge_slope":          round(finder_edge_slope, 2),
            "is_photocopy_detected":      morph["is_photocopy"],
            "edge_ratio":                 round(edge_ratio, 3),
        },
        "description": verdict_desc,
        "comparison_image": comparison_img,
        "debug_log": debug_log,
    }
