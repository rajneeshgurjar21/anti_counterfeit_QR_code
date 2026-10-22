"""
Anti-Counterfeit QR Code & Copy Detection Pattern (CDP) Verifier
================================================================
REAL-WORLD CALIBRATED for printed+photographed QR codes.

Pipeline:
  1. Multi-strategy QR decode (with adaptive padding).
  2. Perspective rectification using detected QR corners.
  3. Image quality pre-gate (blur check) → RECAPTURE_REQUIRED.
  4. CDP ROI extraction from rectified image.
  5. Regenerate deterministic digital reference (same seed).
  6. Peak Normalized Cross-Correlation (pattern identity).
  7. Relative sharpness score (genuine vs counterfeit reprint).
  8. Composite authenticity score + verdict.

Calibration reference (CDP region, 188×188 px):
  Digital master  : lap=62942  hf=0.143  grad=477
  Phone (genuine) : lap=500-800  hf=0.001-0.002  grad=140-170
  Counterfeit 2nd gen: lap=30-80  hf=0.0002-0.0005  grad=50-80
"""

import urllib.parse
import cv2
import numpy as np
from PIL import Image
from cdp_engine import generate_cdp_module_with_fiducials, generate_cdp_pattern


# ─────────────────────────────────────────────
#  Constants – REAL-WORLD CALIBRATED
# ─────────────────────────────────────────────

# Laplacian variance thresholds (CDP region only, phone-photo calibrated)
LAP_GENUINE_MIN   =  120.0   # Below this: very low sharpness
LAP_GENUINE_LOW   =  150.0   # Genuine phone photo lower bound
LAP_GENUINE_HIGH  = 1000.0   # High-end phone photo upper bound (used for norm)
LAP_FAKE_MAX      =   70.0   # Counterfeit reprint is almost always below this (typically 15-40)

# FFT high-frequency ratio thresholds (CDP region, phone-photo calibrated)
HF_GENUINE_MIN    = 0.00060  # Genuine phone photo lower bound
HF_GENUINE_HIGH   = 0.00380  # Genuine phone photo upper bound (for norm)
HF_FAKE_MAX       = 0.00035  # Counterfeit is almost always below this (typically 0.0002-0.0003)

# Gradient sharpness thresholds
GRAD_GENUINE_MIN  =  90.0
GRAD_GENUINE_HIGH = 200.0
GRAD_FAKE_MAX     =  70.0

# NCC thresholds
NCC_GENUINE_MIN   = 0.35    # Below this → pattern mismatch (wrong serial / fake)
NCC_GENUINE_HIGH  = 0.65    # Best expected NCC from phone photo

# Image quality pre-gate (full image blur check)
BLUR_RECAPTURE_THRESHOLD = 25.0  # Laplacian of full image; below → RECAPTURE_REQUIRED

# Score thresholds for verdict
SCORE_GENUINE_THRESHOLD    = 65.0
SCORE_SUSPICIOUS_THRESHOLD = 35.0



# ─────────────────────────────────────────────
#  Helper Functions
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
    sobelx = cv2.Sobel(img_gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(img_gray, cv2.CV_64F, 0, 1, ksize=3)
    return float(np.mean(np.sqrt(sobelx**2 + sobely**2)))


def compute_edge_acutance(img_gray: np.ndarray) -> float:
    """
    Computes Laplacian variance of the image.
    Higher = sharper micro-dot edges (genuine first-gen print).
    Lower = blurred / second-gen reprint.
    """
    laplacian = cv2.Laplacian(img_gray, cv2.CV_64F)
    return float(laplacian.var())


def compute_fft_hf_energy_ratio(img_gray: np.ndarray, cutoff_ratio: float = 0.20) -> float:
    """
    High-frequency spectral energy fraction via 2D-FFT.
    Physical blur / reprinting collapses HF energy.
    """
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
    Provides translation invariance (±14 px search window).
    """
    cand = candidate.astype(np.float32)
    ref  = reference.astype(np.float32)

    pad = 14
    cand_pad = cv2.copyMakeBorder(cand, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    ref_crop = ref[6:ref.shape[0]-6, 6:ref.shape[1]-6]

    res = cv2.matchTemplate(cand_pad, ref_crop, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return float(max_val), max_loc


def check_image_quality(img_gray: np.ndarray) -> tuple[bool, float]:
    """
    Pre-gate: checks if the full image is too blurry to analyze.
    Returns (is_ok, lap_var).
    """
    lap_var = compute_edge_acutance(img_gray)
    return lap_var >= BLUR_RECAPTURE_THRESHOLD, lap_var


def validate_image_quality(img_cv: np.ndarray) -> tuple[bool, str, str, dict]:
    """
    Stage 1: Image Quality Validation Pre-Gate.
    Ensures image is clear, focused, adequately exposed, and decodable
    BEFORE any physical authenticity or micro-dot analysis is performed.
    
    Returns:
        (is_valid, failure_reason, guidance, details_dict)
    """
    if img_cv is None or img_cv.size == 0:
        return False, "Failed to load input image", "Please provide a valid image file in PNG or JPEG format.", {}

    h, w = img_cv.shape[:2]
    
    # 1. Minimum Resolution Check (< 200px in either dimension)
    if h < 200 or w < 200:
        return (
            False,
            f"Image resolution too low ({w}x{h} px, min 200x200)",
            "Image must be at least 200x200 pixels. Please capture closer or upload a higher-resolution photograph.",
            {"height": h, "width": w}
        )

    img_gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    mean_val = float(np.mean(img_gray))
    std_val = float(np.std(img_gray))
    lap_var = compute_edge_acutance(img_gray)
    sat_ratio = float(np.mean(img_gray > 250))

    # 2. Underexposure / Total Darkness Check
    if mean_val < 30.0:
        return (
            False,
            f"Image underexposed / too dark (mean brightness: {mean_val:.1f}/255)",
            "Lighting is too dim to resolve microscopic security features. Please turn on camera flash or move to a well-lit environment.",
            {"mean_brightness": round(mean_val, 1)}
        )

    # 3. Specular Glare / Severe Overexposure Check
    # In QR codes, white background/modules typically account for 50-75% of pixels.
    # Specular glare is present when brightness is almost totally saturated (> 88%)
    # or contrast is severely washed out (std < 30 and mean > 240).
    if (sat_ratio > 0.88) or (mean_val > 240.0 and std_val < 30.0):
        return (
            False,
            "Excessive specular glare / overexposure detected",
            "Bright surface reflections or camera flash reflection are washing out the QR code. Tilt camera slightly to avoid direct glare.",
            {"saturation_ratio": round(sat_ratio, 3), "contrast_std": round(std_val, 1)}
        )

    # 4. Severe Focus / Blur Check
    if lap_var < BLUR_RECAPTURE_THRESHOLD:
        return (
            False,
            f"Image is out of focus / blurry (sharpness: {lap_var:.1f} < {BLUR_RECAPTURE_THRESHOLD:.0f})",
            "Hold your phone steady, tap the screen to lock optical autofocus on the QR code, and avoid motion blur.",
            {"laplacian_sharpness": round(lap_var, 1)}
        )

    return True, "", "", {
        "height": h,
        "width": w,
        "mean_brightness": round(mean_val, 1),
        "saturation_ratio": round(sat_ratio, 3),
        "laplacian_sharpness": round(lap_var, 1)
    }


def compute_dot_morphology(inner_cand: np.ndarray) -> dict:
    """
    Analyzes micro-dot morphology, toner density balance, and clumping.
    Genuine 1st-generation physical prints retain discrete micro-dots, distinct
    boundaries, and high perimeter-to-area ratio (P/A). Office photocopies and
    optical reprints experience toner spread/ink-bleed and non-linear thresholding,
    merging adjacent dots into large fused blobs, destroying micro-voids, and
    collapsing P/A.
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
            "is_photocopy": True
        }

    # 1. Normalize and binarize using Otsu's optimal global threshold
    norm = cv2.normalize(inner_cand, None, 0, 255, cv2.NORM_MINMAX)
    _, binary = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    total_pixels = binary.size
    black_pixels = int(np.sum(binary > 0))
    black_density = black_pixels / max(1, total_pixels)

    # 2. Connected component analysis on black toner dots
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    areas = []
    perimeters = []
    clump_thresh = 60 # Component area > 60px classified as multi-dot clump
    large_clump_area = 0

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 3: # Discard 1-2 pixel isolated noise
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

    # 3. White micro-void count (un-inked paper gaps inside the CDP)
    white_mask = (255 - binary).copy()
    white_mask[0, :] = 0; white_mask[-1, :] = 0; white_mask[:, 0] = 0; white_mask[:, -1] = 0
    num_w_labels, _, w_stats, _ = cv2.connectedComponentsWithStats(white_mask, connectivity=8)
    void_count = sum(1 for i in range(1, num_w_labels) if w_stats[i, cv2.CC_STAT_AREA] >= 3 and w_stats[i, cv2.CC_STAT_AREA] < (total_pixels * 0.4))

    # 4. Normalized score components [0.0 → 1.0]
    # Perimeter-to-Area ratio: genuine phone prints range 0.25 to 0.50; photocopies collapse < 0.16
    pa_norm = max(0.0, min(1.0, (pa_ratio - 0.14) / (0.28 - 0.14)))
    
    # Toner density balance: target ~ 0.50 (genuine: 0.44-0.56, dark copy: > 0.65, faint copy: < 0.35)
    density_dev = abs(black_density - 0.50)
    density_norm = max(0.0, min(1.0, 1.0 - max(0.0, density_dev - 0.06) / 0.12))
    
    # Dot clump penalty: fused toner into 1-4 massive blobs is a hallmark of photocopies
    if dot_count <= 4 or mean_dot_area > 2500:
        clump_norm = 0.0
    elif dot_count >= 15 and mean_dot_area < 800:
        clump_norm = 1.0
    else:
        clump_norm = max(0.0, min(1.0, (dot_count - 4) / 11.0))

    morph_norm = pa_norm * 0.45 + density_norm * 0.35 + clump_norm * 0.20

    # 5. Dedicated photocopy discriminant condition
    is_photocopy = bool(
        (pa_ratio < 0.16) or
        (black_density > 0.65 and pa_ratio < 0.22) or
        (dot_count <= 4 and mean_dot_area > 2000) or
        (morph_norm < 0.28)
    )

    return {
        "pa_ratio": round(pa_ratio, 4),
        "mean_dot_area": round(mean_dot_area, 1),
        "clump_ratio": round(clump_ratio, 4),
        "dot_count": dot_count,
        "void_count": void_count,
        "black_density": round(black_density, 4),
        "morph_norm": round(morph_norm, 3),
        "is_photocopy": is_photocopy
    }


def generate_comparison_card(
    cand_core: np.ndarray,
    ref_core: np.ndarray,
    verdict: str,
    score: float,
    output_path: str = None,
) -> Image.Image:
    """
    Side-by-side zoom of candidate CDP vs reference CDP + difference heatmap.
    """
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
    cv2.putText(card, "Master Digital Pattern",   (15, 45),       font, 0.55, (20,20,20), 1, cv2.LINE_AA)
    cv2.putText(card, "Scanned Pattern (4x Zoom)",(25+zoom_w, 45),font, 0.55, (20,20,20), 1, cv2.LINE_AA)
    cv2.putText(card, "Degradation Heatmap",      (35+2*zoom_w, 45),font, 0.55,(20,20,20),1,cv2.LINE_AA)

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
) -> dict:
    """
    Two-Stage Anti-Counterfeit Verification Pipeline:
    
    STAGE 1: Image Quality Validation (Pre-Gate)
      - Image integrity & minimum resolution (>= 200x200 px).
      - Exposure & lighting (no total darkness, no excessive glare).
      - Optical focus & motion blur pre-check.
      - QR barcode decodability & finder pattern detection.
      - Perspective angle tilt sanity check (< 45 deg tilt).
      - Central CDP security pattern integrity (no obstruction/scratch/damage).
      * If Stage 1 fails -> Return RECAPTURE_REQUIRED with actionable guidance.
        Do NOT execute Stage 2. Do NOT classify as COUNTERFEIT.
        
    STAGE 2: Authenticity & Registry Verification (Executed ONLY after Stage 1 passes)
      - Step 2.1: Brand Database Registry Lookup.
          - If unregistered/unknown -> Status UNKNOWN, Message "Unable to Verify — Product Not Registered", Score 0.0%
          - If blacklisted/revoked -> Status BLACKLISTED, Message "Product Revoked or Blacklisted by Brand Owner", Score 0.0%
      - Step 2.2: Cryptographic CDP Seed Verification & Physical Micro-Structure Analysis.
          - Multi-ratio canonical perspective rectification.
          - Micro-dot morphology (Perimeter-to-Area ratio, toner clumping, density balance).
          - Edge acutance (Laplacian variance) & 2D-FFT high frequency energy.
          - Hierarchical Decision Gates:
              1. peak_ncc < 0.30 -> COUNTERFEIT (Pattern Mismatch)
              2. is_photocopy -> COUNTERFEIT (Photocopy / Reprint Detected)
              3. laplacian_var < 70 or (lap < 100 and hf < 0.0006) -> COUNTERFEIT (Reprint / Copy Detected)
              4. authenticity_score >= 65.0 -> GENUINE (Original Print)
              5. 45.0 <= authenticity_score < 65.0 -> SUSPICIOUS (Inconclusive Integrity)
              6. else -> COUNTERFEIT
      - Step 2.3: Scan Audit Logging & Multi-Scan Clone Alert Tracking.
    """
    import product_db

    # ── Load image ──────────────────────────────────────────────────────────
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
            "qr_payload": "",
            "serial_number": expected_serial or "UNKNOWN",
            "guidance": "Failed to load input image. Please provide a valid JPEG or PNG file.",
            "metrics": {"stage1_passed": False},
            "description": "Failed to load input image.",
            "comparison_image": None,
            "product_info": None,
        }

    # ═════════════════════════════════════════════════════════════════════════
    #  STAGE 1: IMAGE QUALITY VALIDATION
    # ═════════════════════════════════════════════════════════════════════════
    is_valid, q_reason, q_guidance, q_metrics = validate_image_quality(img_cv)
    full_lap = q_metrics.get("laplacian_sharpness", compute_edge_acutance(cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)))

    if not is_valid:
        return {
            "status": "RECAPTURE_REQUIRED",
            "message": "Unable to Verify — Please Upload a Clear Image of the QR Code",
            "verdict": "RECAPTURE REQUIRED (QUALITY CHECK FAILED)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "qr_payload": "",
            "serial_number": expected_serial or "UNKNOWN",
            "guidance": q_guidance,
            "metrics": {
                "stage1_passed": False,
                "failure_reason": q_reason,
                "full_image_sharpness": round(full_lap, 1),
                **q_metrics,
            },
            "description": f"{q_reason}. {q_guidance}",
            "comparison_image": None,
            "product_info": None,
        }

    # ── Multi-pass QR code barcode detection & decode ─────────────────────────
    detector = cv2.QRCodeDetector()
    payload, points, straight = detector.detectAndDecode(img_cv)

    if not payload or points is None:
        for pad in [30, 50, 70, 100]:
            padded = cv2.copyMakeBorder(
                img_cv, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=[255, 255, 255]
            )
            p, pts_p, s = detector.detectAndDecode(padded)
            if p and pts_p is not None:
                payload = p
                points = pts_p - np.array([[[pad, pad]]])
                straight = s
                break

    # ── Verify QR Decode Success ─────────────────────────────────────────────
    if not payload or points is None or len(points) == 0:
        if full_lap < 35.0:
            dec_reason = f"Image is too blurry to resolve QR modules (sharpness: {full_lap:.1f})"
            dec_guidance = "Hold your phone steady, tap to focus, and recapture closer to the QR code."
        else:
            dec_reason = "QR code could not be detected or is obstructed/cropped"
            dec_guidance = "Ensure the entire QR code, including all four corners and white quiet zone border, is fully in frame and unobstructed."

        return {
            "status": "RECAPTURE_REQUIRED",
            "message": "Unable to Verify — Please Upload a Clear Image of the QR Code",
            "verdict": "RECAPTURE REQUIRED (QR CODE UNREADABLE / OBSTRUCTED)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "qr_payload": "",
            "serial_number": expected_serial or "UNKNOWN",
            "guidance": dec_guidance,
            "metrics": {
                "stage1_passed": False,
                "failure_reason": dec_reason,
                "full_image_sharpness": round(full_lap, 1),
            },
            "description": f"{dec_reason}. {dec_guidance}",
            "comparison_image": None,
            "product_info": None,
        }

    # ── Corner points of the decoded data matrix ─────────────────────────────
    pts_arr = points[0].astype(np.float32)

    # ── Perspective angle / tilt check ───────────────────────────────────────
    d01 = float(np.linalg.norm(pts_arr[1] - pts_arr[0]))
    d12 = float(np.linalg.norm(pts_arr[2] - pts_arr[1]))
    d23 = float(np.linalg.norm(pts_arr[3] - pts_arr[2]))
    d30 = float(np.linalg.norm(pts_arr[0] - pts_arr[3]))
    edges = [d01, d12, d23, d30]
    min_edge = min(edges)
    max_edge = max(edges)
    edge_ratio = min_edge / max(1.0, max_edge)

    if edge_ratio < 0.35:
        tilt_reason = f"Camera perspective angle is too steep (edge ratio: {edge_ratio:.2f} < 0.35)"
        tilt_guidance = "Please align your camera directly facing the QR code straight-on rather than from an acute side angle."
        return {
            "status": "RECAPTURE_REQUIRED",
            "message": "Unable to Verify — Please Upload a Clear Image of the QR Code",
            "verdict": "RECAPTURE REQUIRED (EXTREME PERSPECTIVE TILT)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "qr_payload": payload,
            "serial_number": expected_serial or "UNKNOWN",
            "guidance": tilt_guidance,
            "metrics": {
                "stage1_passed": False,
                "perspective_edge_ratio": round(edge_ratio, 3),
                "failure_reason": tilt_reason,
                "full_image_sharpness": round(full_lap, 1),
            },
            "description": f"{tilt_reason}. {tilt_guidance}",
            "comparison_image": None,
            "product_info": None,
        }

    # ── Canonical Perspective Rectification ───────────────────────────────────
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
    warped = cv2.warpPerspective(img_cv, M, (full_size, full_size))
    warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    # ── Preliminary center security pattern integrity check ──────────────────
    prelim_cw = int(full_size * cdp_ratio)
    if prelim_cw % 2 != 0: prelim_cw += 1
    px1 = (warped_gray.shape[1] - prelim_cw) // 2
    py1 = (warped_gray.shape[0] - prelim_cw) // 2
    prelim_cdp = warped_gray[py1:py1+prelim_cw, px1:px1+prelim_cw]

    cdp_var = float(np.var(prelim_cdp))
    cdp_mean = float(np.mean(prelim_cdp))
    if cdp_var < 30.0 or cdp_mean > 250.0 or cdp_mean < 10.0:
        cdp_reason = f"Center security pattern is occluded, damaged, or unreadable (variance: {cdp_var:.1f})"
        cdp_guidance = "The central micro-pattern appears smudged, scratched, covered, or washed out. Please clean the label and upload a clear photo."
        return {
            "status": "RECAPTURE_REQUIRED",
            "message": "Unable to Verify — Please Upload a Clear Image of the QR Code",
            "verdict": "RECAPTURE REQUIRED (SECURITY PATTERN DAMAGED / OCCLUDED)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "qr_payload": payload,
            "serial_number": expected_serial or "UNKNOWN",
            "guidance": cdp_guidance,
            "metrics": {
                "stage1_passed": False,
                "center_variance": round(cdp_var, 2),
                "center_mean": round(cdp_mean, 1),
                "failure_reason": cdp_reason,
                "full_image_sharpness": round(full_lap, 1),
            },
            "description": f"{cdp_reason}. {cdp_guidance}",
            "comparison_image": None,
            "product_info": None,
        }

    # ═════════════════════════════════════════════════════════════════════════
    #  STAGE 2: AUTHENTICITY & REGISTRY VERIFICATION
    #  (Executed ONLY because Stage 1 passed completely)
    # ═════════════════════════════════════════════════════════════════════════

    # ── Step 2.1: Extract Serial & Query Brand Database Registry ─────────────
    serial_no = extract_serial_number(payload) if payload else ""
    if not serial_no and expected_serial:
        serial_no = expected_serial

    product_record = product_db.get_product(serial_no) if serial_no else None

    # Check 1: Product Not Registered / Unknown Item
    if product_record is None:
        audit_record = product_db.record_scan(serial_no or "UNKNOWN", "UNREGISTERED PRODUCT", 0.0)
        return {
            "status": "UNKNOWN",
            "message": "Unable to Verify — Product Not Registered",
            "verdict": "UNREGISTERED PRODUCT (SERIAL NOT FOUND)",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "qr_payload": payload,
            "serial_number": serial_no or "UNKNOWN",
            "guidance": "This serial number is not found in the official brand database. Verify product packaging or contact the manufacturer.",
            "product_info": audit_record,
            "metrics": {
                "stage1_passed": True,
                "full_image_sharpness": round(full_lap, 1),
            },
            "description": "Serial number does NOT exist in official brand database. Product cannot be authenticated.",
            "comparison_image": None,
        }

    # Check 2: Product Status Revoked or Blacklisted
    if product_record.get("status") in ("INACTIVE", "BLACKLISTED", "REVOKED"):
        audit_record = product_db.record_scan(serial_no, f"BLACKLISTED ({product_record.get('status')})", 0.0)
        return {
            "status": "BLACKLISTED",
            "message": "Product Revoked or Blacklisted by Brand Owner",
            "verdict": f"BLACKLISTED / REVOKED PRODUCT ({product_record.get('status')})",
            "is_genuine": False,
            "authenticity_score": 0.0,
            "qr_payload": payload,
            "serial_number": serial_no,
            "guidance": "This product batch or unit has been recalled, blacklisted, or revoked by the brand manufacturer.",
            "product_info": audit_record,
            "metrics": {
                "stage1_passed": True,
                "full_image_sharpness": round(full_lap, 1),
            },
            "description": f"REJECTED: Product status is marked {product_record.get('status')} in the brand database. Authentic print rejected per policy.",
            "comparison_image": None,
        }

    # ── Step 2.2: Physical CDP Micro-Structure Analysis ─────────────────────
    candidate_ratios = [cdp_ratio, 0.32, 0.30, 0.28, 0.34]
    seen = set()
    candidate_ratios = [r for r in candidate_ratios if not (r in seen or seen.add(r))]

    best_ncc             = -1.0
    best_candidate_tuple = None

    for r in candidate_ratios:
        center_w = int(full_size * r)
        if center_w % 2 != 0:
            center_w += 1
        center_w = max(center_w, 40)

        wh = warped_gray.shape[0]
        ww = warped_gray.shape[1]
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

        curr_ncc, _ = compute_peak_cross_correlation(inner_cand, inner_ref)
        if curr_ncc > best_ncc:
            best_ncc             = curr_ncc
            best_candidate_tuple = (inner_cand, inner_ref, curr_ncc, r)

    if best_candidate_tuple is None:
        inner_cand = warped_gray
        inner_ref  = warped_gray
        peak_ncc   = 0.0
    else:
        inner_cand, inner_ref, peak_ncc, _ = best_candidate_tuple

    # ── Compute CDP-region metrics ─────────────────────────────────────────
    laplacian_var  = compute_edge_acutance(inner_cand)
    grad_sharpness = compute_gradient_sharpness(inner_cand)
    hf_energy      = compute_fft_hf_energy_ratio(inner_cand)
    morph          = compute_dot_morphology(inner_cand)

    pa_ratio      = morph["pa_ratio"]
    mean_dot_area = morph["mean_dot_area"]
    clump_ratio   = morph["clump_ratio"]
    dot_count     = morph["dot_count"]
    void_count    = morph["void_count"]
    black_density = morph["black_density"]
    morph_norm    = morph["morph_norm"]
    is_photocopy  = morph["is_photocopy"]

    # ── Normalization [0 → 1] ──────────────────────────────────────────────
    lap_norm  = max(0.0, min(1.0, (laplacian_var  - LAP_FAKE_MAX)   / (LAP_GENUINE_HIGH  - LAP_FAKE_MAX)))
    hf_norm   = max(0.0, min(1.0, (hf_energy      - HF_FAKE_MAX)    / (HF_GENUINE_HIGH   - HF_FAKE_MAX)))
    grad_norm = max(0.0, min(1.0, (grad_sharpness  - GRAD_FAKE_MAX)  / (GRAD_GENUINE_HIGH - GRAD_FAKE_MAX)))
    ncc_norm  = max(0.0, min(1.0, (peak_ncc        - NCC_GENUINE_MIN)/ (NCC_GENUINE_HIGH  - NCC_GENUINE_MIN)))

    sharpness_avg = (lap_norm * 0.50 + hf_norm * 0.30 + grad_norm * 0.20)
    sharpness_gate = sharpness_avg * (0.25 + 0.75 * min(lap_norm, hf_norm))

    # Weighted base score
    weighted_raw = (
        ncc_norm   * 0.30
        + morph_norm * 0.30
        + lap_norm * 0.20
        + hf_norm  * 0.15
        + grad_norm * 0.05
    )

    ncc_gate = max(0.0, min(1.0, (peak_ncc - 0.25) / (NCC_GENUINE_MIN - 0.25)))
    if is_photocopy:
        morph_gate = min(0.15, morph_norm)
    else:
        morph_gate = 0.40 + 0.60 * morph_norm

    composite = weighted_raw * (0.10 + 0.90 * ncc_gate) * (0.20 + 0.80 * morph_gate)

    if is_photocopy:
        authenticity_score = round(max(0.0, min(22.0, composite * 100.0)), 1)
    elif composite >= 0.70:
        authenticity_score = 80.0 + (composite - 0.70) / 0.30 * 20.0
    elif composite >= 0.45:
        authenticity_score = 50.0 + (composite - 0.45) / 0.25 * 30.0
    elif composite >= 0.20:
        authenticity_score = 20.0 + (composite - 0.20) / 0.25 * 30.0
    else:
        authenticity_score = max(0.0, composite / 0.20 * 20.0)

    authenticity_score = float(round(max(0.0, min(100.0, authenticity_score)), 1))

    # ── Hierarchical Decision Logic ──────────────────────────────────────────
    if peak_ncc < 0.30:
        verdict      = "COUNTERFEIT (PATTERN MISMATCH)"
        verdict_desc = "FAKE! Micro-dot pattern does NOT match official cryptographic seed for this serial number."
        status       = "COUNTERFEIT"
        message      = "Counterfeit Detected — Possible Copy or Reprint"
        is_genuine   = False
        authenticity_score = min(authenticity_score, 15.0)

    elif is_photocopy:
        verdict      = "COUNTERFEIT (PHOTOCOPY / REPRINT DETECTED)"
        verdict_desc = (
            f"FAKE! Photocopied reprint detected. Micro-dot structure has collapsed due to secondary toner spread "
            f"and print-scan degradation (P/A ratio={pa_ratio:.3f}, toner density={black_density*100:.1f}%, dots={dot_count})."
        )
        status       = "COUNTERFEIT"
        message      = "Counterfeit Detected — This QR Code Appears to Be a Copy"
        is_genuine   = False
        authenticity_score = min(authenticity_score, 22.0)

    elif laplacian_var < LAP_FAKE_MAX or (laplacian_var < 100.0 and hf_energy < 0.0006):
        verdict      = "COUNTERFEIT (REPRINT / COPY DETECTED)"
        verdict_desc = "FAKE! Second-generation copy or reprint detected. High-frequency micro-texture has collapsed — characteristic of re-printing."
        status       = "COUNTERFEIT"
        message      = "Counterfeit Detected — Possible Copy or Reprint"
        is_genuine   = False
        authenticity_score = min(authenticity_score, 25.0)

    elif authenticity_score >= SCORE_GENUINE_THRESHOLD:
        verdict      = "GENUINE (ORIGINAL PRINT)"
        verdict_desc = "Genuine 1st-generation original print verified. Micro-dot pattern, morphology, and edge sharpness match official cryptographic reference."
        status       = "GENUINE"
        message      = "Genuine Product Verified"
        is_genuine   = True

    elif authenticity_score >= 45.0:
        verdict      = "SUSPICIOUS (INCONCLUSIVE INTEGRITY)"
        verdict_desc = "Borderline result. Micro-dot pattern matches official cryptographic seed, but physical acutance is inconclusive. Retake photo closer with good lighting."
        status       = "SUSPICIOUS"
        message      = "Suspicious Product — Inconclusive Security Pattern"
        is_genuine   = False

    else:
        verdict      = "COUNTERFEIT (LOW CONFIDENCE)"
        verdict_desc = "FAKE or severely degraded image. Micro-dot sharpness and pattern correlation are both below genuine thresholds."
        status       = "COUNTERFEIT"
        message      = "Counterfeit Detected — This QR Code Appears to Be a Copy"
        is_genuine   = False
        authenticity_score = min(authenticity_score, 30.0)

    # ── Visual comparison card ────────────────────────────────────────────
    comparison_img = None
    try:
        comparison_img = generate_comparison_card(
            inner_cand, inner_ref, verdict, authenticity_score,
            output_path=comparison_output_path,
        )
    except Exception:
        comparison_img = None

    # ── Record verification scan in official registry ─────────────────────
    try:
        updated_product_record = product_db.record_scan(serial_no, verdict, authenticity_score)
    except Exception as e:
        updated_product_record = dict(product_record)
        updated_product_record["scan_count"] = updated_product_record.get("scan_count", 0) + 1
        updated_product_record["clone_alert"] = False
        updated_product_record["clone_message"] = str(e)

    return {
        "status": status,
        "message": message,
        "verdict": verdict,
        "is_genuine": is_genuine,
        "authenticity_score": round(float(authenticity_score), 1),
        "qr_payload": payload,
        "serial_number": serial_no,
        "product_info": updated_product_record,
        "metrics": {
            "stage1_passed":              True,
            "peak_cross_correlation_ncc": round(peak_ncc, 4),
            "peak_ncc":                   round(peak_ncc, 4),
            "laplacian_edge_variance":    round(laplacian_var, 2),
            "edge_acutance_laplacian":    round(laplacian_var, 2),
            "fft_high_freq_ratio":        round(hf_energy, 6),
            "gradient_sharpness":         round(grad_sharpness, 2),
            "dot_morphology_pa_ratio":    round(pa_ratio, 4),
            "dot_morphology_density":     round(black_density, 4),
            "dot_morphology_mean_area":   round(mean_dot_area, 1),
            "dot_morphology_clump_ratio": round(clump_ratio, 4),
            "dot_count":                  dot_count,
            "micro_void_count":           void_count,
            "morph_norm":                 round(morph_norm, 3),
            "is_photocopy_detected":      is_photocopy,
            "ncc_norm":                   round(ncc_norm, 3),
            "lap_norm":                   round(lap_norm, 3),
            "hf_norm":                    round(hf_norm, 3),
            "grad_norm":                  round(grad_norm, 3),
            "sharpness_gate":             round(sharpness_gate, 3),
            "acutance_gate":              round(sharpness_gate, 3),
            "composite_raw":              round(composite, 4),
            "full_image_sharpness":       round(full_lap, 1),
        },
        "description": verdict_desc,
        "comparison_image": comparison_img,
    }

