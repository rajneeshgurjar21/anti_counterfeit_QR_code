import cv2
import numpy as np
from PIL import Image
import cdp_engine
import simulator
import cdp_verifier

s = "PROD-2026-X8879"
payload = f"https://brand.com/?id={s}"
qr_img, _ = cdp_engine.create_anti_counterfeit_qr(payload=payload, serial_no=s)

gen_scan = simulator.simulate_genuine_scan(qr_img)
fake_reprint = simulator.simulate_counterfeit_reprint(qr_img)

cv_img = cv2.cvtColor(np.array(qr_img), cv2.COLOR_RGB2BGR)
blur_08 = Image.fromarray(cv2.cvtColor(cv2.GaussianBlur(cv_img, (0, 0), 0.8), cv2.COLOR_BGR2RGB))
blur_12 = Image.fromarray(cv2.cvtColor(cv2.GaussianBlur(cv_img, (0, 0), 1.2), cv2.COLOR_BGR2RGB))

tests = [
    ("1. Genuine Mobile Scan", gen_scan),
    ("2. Blur sigma=0.8", blur_08),
    ("3. Blur sigma=1.2", blur_12),
    ("4. Counterfeit Reprint", fake_reprint),
]

print(f"{'Case':<25} | {'Peak NCC':<10} | {'Laplacian':<10} | {'FFT HF':<10} | {'Gradient':<10}")
print("-" * 75)
for name, img in tests:
    res = cdp_verifier.verify_anti_counterfeit_qr(img, expected_serial=s)
    m = res["metrics"]
    print(f"{name:<25} | {m['peak_cross_correlation_ncc']:<10.4f} | {m['laplacian_edge_variance']:<10.1f} | {m['fft_high_freq_ratio']:<10.4f} | {m['gradient_sharpness']:<10.1f}")
