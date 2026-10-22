import cv2
import cdp_verifier

img = cv2.imread("master_anti_counterfeit_qr.png")
print("Testing master image blur degradation:")
for sigma in [0.0, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0]:
    b = cv2.GaussianBlur(img, (0, 0), sigma) if sigma > 0 else img
    res = cdp_verifier.verify_anti_counterfeit_qr(b)
    s = res["authenticity_score"]
    v = res["verdict"]
    m = res["metrics"]
    print(f"sigma={sigma:.1f}: Score={s}%, Verdict={v}, NCC={m['peak_cross_correlation_ncc']:.4f}, Lap={m['laplacian_edge_variance']:.1f}, Grad={m['gradient_sharpness']:.1f}")
