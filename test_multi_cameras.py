"""
Dedicated Multi-Camera Anti-Counterfeit Test Suite
=================================================
Validates the camera-independent verification pipeline across diverse mobile phones:
- Phone A (Flagship / Ultra-Sharp)
- Phone B (Aggressive Noise Reduction)
- Phone C (Distance Capture / Sub-sampled on realistic background)
- Phone D (Challenging Lighting & Moderate Tilt)
- Phone E (Budget Camera / Lens Softness)

Validates that:
1. The exact same genuine physical print is recognized as GENUINE on all phones.
2. Counterfeit reprints and photocopies are recognized as COUNTERFEIT across all phones.
3. Truly degraded/blurry images return RECAPTURE_REQUIRED / LOW_IMAGE_QUALITY (never false counterfeit).
4. Unregistered and revoked products are correctly blocked.
"""

import os
import sys
import numpy as np
import cv2
from PIL import Image

import cdp_engine
import simulator
from simulator import PHONE_PROFILES, simulate_phone_capture, simulate_counterfeit_reprint_captured
import cdp_verifier
import product_db

def run_multi_camera_test_suite():
    print("=" * 105)
    print("STARTING DEDICATED MULTI-CAMERA ANTI-COUNTERFEIT TEST SUITE")
    print("=" * 105)

    TEST_SERIAL = "PROD-MULTI-TEST-2026"
    TEST_PAYLOAD = f"https://verify.aura-pharma.com/auth?id={TEST_SERIAL}&batch=MT-01"

    # 1. Register test product in database
    product_db.register_product(
        serial_no=TEST_SERIAL,
        product_name="AuraCare Vaccine 5ml Vial",
        brand_name="Aura Pharma Global",
        batch_no="MT-01",
        mfg_date="2026-04-01",
        exp_date="2029-04-01",
        mrp="$140.00"
    )

    # 2. Generate Master Anti-Counterfeit QR Code (Digital Master)
    qr_master_pil, cdp_master_pil = cdp_engine.create_anti_counterfeit_qr(
        payload=TEST_PAYLOAD,
        serial_no=TEST_SERIAL,
        box_size=12,
        cdp_ratio=0.32
    )

    results_table = []

    def run_case(category, phone_name, img, expected_status, notes=""):
        res = cdp_verifier.verify_anti_counterfeit_qr(
            img, 
            expected_serial=TEST_SERIAL,
            save_debug_artifacts=False
        )
        status = res.get("status", "UNKNOWN")
        verdict = res.get("verdict", "N/A")
        q_score = res.get("image_quality_score", 0.0)
        c_score = res.get("cdp_authenticity_score", 0.0)
        r_score = res.get("reprint_risk_score", 0.0)
        final_score = res.get("authenticity_score", 0.0)
        qr_decoded = bool(res.get("qr_payload"))

        # Match check
        if expected_status == "GENUINE":
            passed = ("GENUINE" in status)
        elif expected_status == "COUNTERFEIT":
            passed = ("COUNTERFEIT" in status or "REPRINT" in status)
        elif expected_status == "RECAPTURE_REQUIRED":
            passed = (status in ("RECAPTURE_REQUIRED", "INVALID_QR"))
        elif expected_status == "UNREGISTERED":
            passed = (status == "UNREGISTERED")
        elif expected_status == "BLACKLISTED":
            passed = (status == "BLACKLISTED")
        else:
            passed = (status == expected_status)

        results_table.append({
            "category": category,
            "phone": phone_name,
            "qr_decoded": "Yes" if qr_decoded else "No",
            "q_score": q_score,
            "c_score": c_score,
            "r_score": r_score,
            "final_score": final_score,
            "status": status,
            "verdict": verdict,
            "expected": expected_status,
            "passed": passed,
            "notes": notes,
        })
        return passed

    # ═════════════════════════════════════════════════════════════════════
    # TEST SECTION 1: GENUINE ORIGINAL PHYSICAL LABEL ACROSS 5 PHONES
    # ═════════════════════════════════════════════════════════════════════
    print("\n--- TEST SECTION 1: GENUINE PHYSICAL LABEL ACROSS 5 MOBILE PHONES ---")
    
    # Phone A: Flagship (iPhone / Pixel Pro) - 3 variations
    img_a1 = simulate_phone_capture(qr_master_pil, phone_model="phone_a")
    run_case("Genuine", "Phone A (Sample 1: Direct)", img_a1, "GENUINE", "Crisp flagship capture")
    
    img_a2 = simulate_phone_capture(qr_master_pil, phone_model="phone_a", override_blur=0.65)
    run_case("Genuine", "Phone A (Sample 2: Mild blur)", img_a2, "GENUINE", "Normal handheld variation")

    # Phone B: Aggressive Noise Reduction (Samsung / Xiaomi) - 3 variations
    img_b1 = simulate_phone_capture(qr_master_pil, phone_model="phone_b")
    run_case("Genuine", "Phone B (Sample 1: De-noised)", img_b1, "GENUINE", "Strong bilateral noise filtering")

    img_b2 = simulate_phone_capture(qr_master_pil, phone_model="phone_b", override_blur=0.95)
    run_case("Genuine", "Phone B (Sample 2: Softer ISP)", img_b2, "GENUINE", "Softer lens optics")

    # Phone C: Distance Capture on Realistic Table Background - 2 variations
    img_c1 = simulate_phone_capture(qr_master_pil, phone_model="phone_c", add_background=True)
    run_case("Genuine", "Phone C (Sample 1: Distance+Desk)", img_c1, "GENUINE", "Desk background + sub-sampling")

    img_c2 = simulate_phone_capture(qr_master_pil, phone_model="phone_c", add_background=False)
    run_case("Genuine", "Phone C (Sample 2: Sub-sampled)", img_c2, "GENUINE", "25cm distance capture")

    # Phone D: Challenging Lighting & Perspective Tilt - 2 variations
    img_d1 = simulate_phone_capture(qr_master_pil, phone_model="phone_d")
    run_case("Genuine", "Phone D (Sample 1: 14° Tilt)", img_d1, "GENUINE", "Perspective pitch + shadow gradient")

    img_d2 = simulate_phone_capture(qr_master_pil, phone_model="phone_d", override_blur=0.85)
    run_case("Genuine", "Phone D (Sample 2: Shadow Falloff)", img_d2, "GENUINE", "Non-uniform illumination")

    # Phone E: Budget Camera / Lens Softness - 2 variations
    img_e1 = simulate_phone_capture(qr_master_pil, phone_model="phone_e")
    run_case("Genuine", "Phone E (Sample 1: Budget Lens)", img_e1, "GENUINE", "Optical point spread + contrast drop")

    img_e2 = simulate_phone_capture(qr_master_pil, phone_model="phone_e", override_blur=1.35)
    run_case("Genuine", "Phone E (Sample 2: Soft Focus)", img_e2, "GENUINE", "Low-cost sensor")

    # ═════════════════════════════════════════════════════════════════════
    # TEST SECTION 2: 2ND-GEN COUNTERFEIT REPRINTS ACROSS PHONES
    # ═════════════════════════════════════════════════════════════════════
    print("\n--- TEST SECTION 2: COUNTERFEIT REPRINT ATTACKS ACROSS PHONES ---")

    # Reprint inspected by Phone A (Sharp camera inspecting fake)
    fake_a = simulate_counterfeit_reprint_captured(qr_master_pil, phone_model="phone_a")
    run_case("Counterfeit", "Reprint on Phone A", fake_a, "COUNTERFEIT", "Reprint with sharp macro-modules")

    # Reprint inspected by Phone B (Soft camera inspecting fake)
    fake_b = simulate_counterfeit_reprint_captured(qr_master_pil, phone_model="phone_b")
    run_case("Counterfeit", "Reprint on Phone B", fake_b, "COUNTERFEIT", "Reprint with ISP noise reduction")

    # Reprint inspected by Phone C (Distance inspecting fake)
    fake_c = simulate_counterfeit_reprint_captured(qr_master_pil, phone_model="phone_c", add_background=True)
    run_case("Counterfeit", "Reprint on Phone C", fake_c, "COUNTERFEIT", "Reprint with desk background")

    # Tampered CDP (Pattern generated with wrong cryptographic seed)
    tampered_pil, _ = cdp_engine.create_anti_counterfeit_qr(
        payload=TEST_PAYLOAD,
        serial_no="WRONG-TAMPERED-SERIAL-9999",
        box_size=12,
        cdp_ratio=0.32
    )
    tampered_scan = simulate_phone_capture(tampered_pil, phone_model="phone_a")
    run_case("Tampered", "Wrong CDP Seed Pattern", tampered_scan, "COUNTERFEIT", "Payload says Serial X, CDP is from Serial Y")

    # ═════════════════════════════════════════════════════════════════════
    # TEST SECTION 3: IMAGE QUALITY DEGRADATION (MUST NOT CALL FAKE!)
    # ═════════════════════════════════════════════════════════════════════
    print("\n--- TEST SECTION 3: LOW IMAGE QUALITY / RECAPTURE REQUIRED ---")

    # Extreme motion blur (sigma = 4.5)
    cv_master = cv2.cvtColor(np.array(qr_master_pil), cv2.COLOR_RGB2BGR)
    severe_blur = Image.fromarray(cv2.cvtColor(cv2.GaussianBlur(cv_master, (19, 19), 4.5), cv2.COLOR_BGR2RGB))
    run_case("Bad Image", "Extreme Motion Blur", severe_blur, "RECAPTURE_REQUIRED", "Truly unreadable photo")

    # Extreme darkness (mean brightness < 15)
    dark_cv = np.clip(cv_master.astype(np.float32) * 0.05, 0, 255).astype(np.uint8)
    dark_img = Image.fromarray(cv2.cvtColor(dark_cv, cv2.COLOR_BGR2RGB))
    run_case("Bad Image", "Severe Underexposure", dark_img, "RECAPTURE_REQUIRED", "Flash off in pitch dark")

    # ═════════════════════════════════════════════════════════════════════
    # TEST SECTION 4: PRODUCT REGISTRY & LIFECYCLE SECURITY
    # ═════════════════════════════════════════════════════════════════════
    print("\n--- TEST SECTION 4: PRODUCT REGISTRY SECURITY CHECKS ---")

    # Unregistered product
    unreg_pil, _ = cdp_engine.create_anti_counterfeit_qr(
        payload="https://fake-registry.com/verify?id=UNREGISTERED-SERIAL-8888",
        serial_no="UNREGISTERED-SERIAL-8888",
        box_size=12
    )
    run_case("Registry", "Unregistered Serial", unreg_pil, "UNREGISTERED", "Serial not in database")

    # Blacklisted product
    BL_SERIAL = "PROD-BLACKLIST-2026"
    product_db.register_product(
        serial_no=BL_SERIAL,
        product_name="Contaminated Lot X",
        brand_name="Aura Pharma",
        batch_no="BAD-01",
        status="REVOKED"
    )
    bl_pil, _ = cdp_engine.create_anti_counterfeit_qr(
        payload=f"https://verify.aura.com/?id={BL_SERIAL}",
        serial_no=BL_SERIAL,
        box_size=12
    )
    run_case("Registry", "Revoked/Blacklisted Unit", bl_pil, "BLACKLISTED", "Recalled lot rejected")

    # ═════════════════════════════════════════════════════════════════════
    # PRINT RESULTS TABLE
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 115)
    print(f"{'Category':<12} | {'Test Scenario':<32} | {'QR':<3} | {'Quality':<7} | {'CDP':<6} | {'Reprint':<7} | {'Score':<6} | {'Verdict':<32} | {'Pass'}")
    print("=" * 115)

    passed_count = 0
    total_count = len(results_table)

    for r in results_table:
        pass_str = "PASS [OK]" if r["passed"] else "FAIL [X]"
        if r["passed"]:
            passed_count += 1
        print(f"{r['category']:<12} | {r['phone']:<32} | {r['qr_decoded']:<3} | {r['q_score']:>6.1f}% | {r['c_score']:>5.1f}% | {r['r_score']:>6.1f}% | {r['final_score']:>5.1f}% | {r['verdict'][:32]:<32} | {pass_str}")

    print("=" * 115)
    print(f"TEST RESULTS: {passed_count}/{total_count} PASSED ({passed_count/total_count*100:.1f}%)")
    print("=" * 115)
    return passed_count == total_count

if __name__ == "__main__":
    success = run_multi_camera_test_suite()
    sys.exit(0 if success else 1)
