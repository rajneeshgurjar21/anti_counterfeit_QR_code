"""
End-to-end Test and Demonstration of Anti-Counterfeit QR Code System
"""

import os
from PIL import Image
import cv2
import numpy as np
from cdp_engine import create_anti_counterfeit_qr
from simulator import simulate_genuine_scan, simulate_counterfeit_reprint
from cdp_verifier import verify_anti_counterfeit_qr

def run_demonstration():
    print("="*65)
    print(" ANTI-COUNTERFEIT QR CODE (CDP) SYSTEM DEMONSTRATION")
    print("="*65)
    
    serial_no = "PROD-2026-X8879"
    payload = f"https://authenticate.brand.com/verify?id={serial_no}&batch=BATCH-09"
    
    # Step 1: Generate Master QR Code
    print("\n[Step 1] Generating Master Anti-Counterfeit QR Code...")
    qr_img, cdp_img = create_anti_counterfeit_qr(
        payload=payload,
        serial_no=serial_no,
        output_path="master_anti_counterfeit_qr.png",
        box_size=12,
        cdp_ratio=0.32
    )
    cdp_img.save("standalone_cdp_module.png")
    print("  -> Saved 'master_anti_counterfeit_qr.png' (Print-ready)")
    print("  -> Saved 'standalone_cdp_module.png' (CDP with fiducial markers)")
    
    # Step 2: Simulate 1st Gen Genuine Print & Mobile Scan
    print("\n[Step 2] Simulating 1st Generation Genuine Print & Scan...")
    genuine_scan = simulate_genuine_scan(qr_img)
    genuine_scan.save("sample_genuine_scan.png")
    print("  -> Saved 'sample_genuine_scan.png'")
    
    # Step 3: Simulate 2nd Gen Counterfeit Reprint Attack
    print("\n[Step 3] Simulating 2nd Generation Counterfeit Reprint Attack...")
    fake_reprint = simulate_counterfeit_reprint(qr_img)
    fake_reprint.save("sample_counterfeit_reprint.png")
    print("  -> Saved 'sample_counterfeit_reprint.png'")
    
    # Step 4: Run Verification on Genuine Print
    print("\n[Step 4] Running Verification on GENUINE 1st-Gen Scan:")
    res_genuine = verify_anti_counterfeit_qr("sample_genuine_scan.png", comparison_output_path="comparison_genuine.png")
    print(f"  * Status: {res_genuine['verdict']}")
    print(f"  * Authenticity Score: {res_genuine['authenticity_score']}%")
    print(f"  * Normalized Correlation (Peak NCC): {res_genuine['metrics']['peak_cross_correlation_ncc']}")
    print(f"  * Edge Sharpness (Laplacian): {res_genuine['metrics']['laplacian_edge_variance']}")
    print(f"  * Gradient Sharpness: {res_genuine['metrics']['gradient_sharpness']}")
    print(f"  * Description: {res_genuine['description']}")
    print("  -> Saved 'comparison_genuine.png'")
    
    # Step 5: Run Verification on Fake Reprint
    print("\n[Step 5] Running Verification on COUNTERFEIT Reprint Scan:")
    res_fake = verify_anti_counterfeit_qr("sample_counterfeit_reprint.png", comparison_output_path="comparison_counterfeit.png")
    print(f"  * Status: {res_fake['verdict']}")
    print(f"  * Authenticity Score: {res_fake['authenticity_score']}%")
    print(f"  * Normalized Correlation (Peak NCC): {res_fake['metrics']['peak_cross_correlation_ncc']}")
    print(f"  * Edge Sharpness (Laplacian): {res_fake['metrics']['laplacian_edge_variance']}")
    print(f"  * Gradient Sharpness: {res_fake['metrics']['gradient_sharpness']}")
    print(f"  * Description: {res_fake['description']}")
    print("  -> Saved 'comparison_counterfeit.png'")
    
    print("\n" + "="*65)
    if res_genuine['is_genuine'] and not res_fake['is_genuine']:
        print(" SUCCESS! Genuine QR verified as ORIGINAL, Counterfeit Reprint detected as FAKE!")
    else:
        print(" Verification completed.")
    print("="*65)

if __name__ == "__main__":
    run_demonstration()
