import cdp_engine, simulator, cdp_verifier, cv2, numpy as np

qr_img, _ = cdp_engine.create_anti_counterfeit_qr(payload='https://brand.com/?id=PROD-2026-X8879', serial_no='PROD-2026-X8879')

for sigma in [0.0, 0.25, 0.35, 0.45, 0.60, 0.80, 1.20]:
    if sigma == 0:
        sim_img = qr_img
    else:
        sim_img = simulator.simulate_genuine_scan(qr_img, blur_sigma=sigma, blur_ksize=3)
    res = cdp_verifier.verify_anti_counterfeit_qr(sim_img, expected_serial='PROD-2026-X8879')
    s = res['authenticity_score']
    v = res['verdict']
    print(f"sigma={sigma:.2f} -> Score: {s:5.1f}% | Verdict: {v}")
