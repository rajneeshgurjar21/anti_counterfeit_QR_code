from PIL import Image
import cdp_engine, simulator, cdp_verifier, cv2, numpy as np

s = "PROD-2026-X8879"
qr_img, _ = cdp_engine.create_anti_counterfeit_qr(payload=f"https://brand.com/?id={s}", serial_no=s)
gen_scan = simulator.simulate_genuine_scan(qr_img)
fake_reprint = simulator.simulate_counterfeit_reprint(qr_img)
cv_img = cv2.cvtColor(np.array(qr_img), cv2.COLOR_RGB2BGR)
blur_08 = Image.fromarray(cv2.cvtColor(cv2.GaussianBlur(cv_img, (0, 0), 0.8), cv2.COLOR_BGR2RGB))
blur_12 = Image.fromarray(cv2.cvtColor(cv2.GaussianBlur(cv_img, (0, 0), 1.2), cv2.COLOR_BGR2RGB))

tests = [
    ("1. Genuine Mobile Scan", gen_scan),
    ("2. Blur sigma=0.8", blur_08),
    ("3. Blur sigma=1.2", blur_12),
    ("4. Counterfeit Reprint", fake_reprint)
]

for name, img in tests:
    res = cdp_verifier.verify_anti_counterfeit_qr(img, expected_serial=s)
    score = res["authenticity_score"]
    verdict = res["verdict"]
    print(f"{name:<24} -> Score: {score:5.1f}% | Verdict: {verdict}")
