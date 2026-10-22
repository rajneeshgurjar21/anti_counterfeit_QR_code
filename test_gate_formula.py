import cv2
import numpy as np

def compute_fft_hf_ratio(gray, cutoff_ratio=0.20):
    f = np.fft.fft2(gray.astype(np.float32))
    fshift = np.fft.fftshift(f)
    mag = np.abs(fshift)**2
    h, w = gray.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx)**2 + (y - cy)**2)
    cutoff = min(h, w) * cutoff_ratio
    low = np.sum(mag[dist <= cutoff])
    high = np.sum(mag[dist > cutoff])
    total = low + high
    return float(high / total) if total > 0 else 0.0

def evaluate_authenticity(peak_ncc, laplacian_var, grad_sharpness, hf_ratio):
    # 1. Individual normalized factors [0.0, 1.0]
    # - NCC: Counterfeit ~0.38, Genuine >= 0.70
    ncc_factor = max(0.0, min(1.0, (peak_ncc - 0.45) / (0.72 - 0.45)))
    
    # - Laplacian Sharpness: Counterfeit < 500, Blurred ~2000-8000, Genuine >= 18000
    # Must reach at least 15000 for full score
    lap_factor = max(0.0, min(1.0, (laplacian_var - 800.0) / (18000.0 - 800.0)))
    
    # - FFT High Frequency Energy: Counterfeit ~0.002, Blurred ~0.05, Genuine >= 0.12
    hf_factor = max(0.0, min(1.0, (hf_ratio - 0.02) / (0.12 - 0.02)))
    
    # - Gradient: Counterfeit < 120, Genuine >= 450
    grad_factor = max(0.0, min(1.0, (grad_sharpness - 150.0) / (450.0 - 150.0)))
    
    # Anti-counterfeit Gate:
    # A genuine print MUST have high frequencies and sharp micro-edges.
    # We use a geometric/harmonic combination with a bottleneck penalty:
    # If HF or Laplacian collapses, the score MUST collapse regardless of NCC!
    acutance_gate = min(lap_factor, hf_factor)
    
    # Weighted base
    weighted_score = ncc_factor * 0.35 + lap_factor * 0.30 + hf_factor * 0.25 + grad_factor * 0.10
    
    # If acutance is severely degraded (blur or reprint), throttle composite
    final_factor = weighted_score * (0.3 + 0.7 * acutance_gate)
    
    # Map to percentage
    if final_factor >= 0.75:
        score = 92.0 + (final_factor - 0.75) / 0.25 * 8.0
    elif final_factor <= 0.20:
        score = max(0.0, final_factor / 0.20 * 15.0)
    else:
        score = 15.0 + (final_factor - 0.20) / (0.75 - 0.20) * 77.0
        
    score = round(max(0.0, min(100.0, score)), 1)
    
    if score >= 75.0:
        verdict = "GENUINE (ORIGINAL PRINT)"
    elif score >= 40.0:
        verdict = "SUSPICIOUS / DEGRADED"
    else:
        verdict = "COUNTERFEIT (REPRINT / BLUR DETECTED)"
        
    return score, verdict, {
        "ncc_f": round(ncc_factor, 2),
        "lap_f": round(lap_factor, 2),
        "hf_f": round(hf_factor, 2),
        "gate": round(acutance_gate, 2)
    }

# Test on all cases
master = cv2.imread("master_anti_counterfeit_qr.png", 0)
h, w = master.shape
cw = int(w * 0.32)
x1, y1 = (w - cw) // 2, (h - cw) // 2
crop = master[y1+20:y1+cw-20, x1+20:x1+cw-20]

test_cases = {
    "Pristine Master": (0.72, 38000.0, 550.0, 0.29),
    "1st-Gen Genuine Scan": (0.73, 24000.0, 512.0, 0.133),
    "Slight Blur sigma=0.5": (0.75, 18900.0, 464.0, 0.129),
    "Medium Blur sigma=0.8 (User's Case)": (0.79, 5800.0, 344.0, 0.064),
    "Heavy Blur sigma=1.2": (0.60, 1330.0, 225.0, 0.013),
    "Counterfeit Reprint": (0.39, 120.0, 87.0, 0.002),
}

for name, (ncc, lap, grad, hf) in test_cases.items():
    sc, vd, det = evaluate_authenticity(ncc, lap, grad, hf)
    print(f"{name:<35} -> Score: {sc:5.1f}% | Verdict: {vd} | {det}")
