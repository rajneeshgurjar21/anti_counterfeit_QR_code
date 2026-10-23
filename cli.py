"""
Command Line Interface (CLI) for Anti-Counterfeit QR Code System
==============================================================
Usage:
    # 1. Generate master anti-counterfeit QR code:
    python cli.py generate --serial PROD-1001 --payload "https://brand.com/verify?id=PROD-1001" --output qr_master.png

    # 2. Verify an image (detects Genuine vs Counterfeit Reprint across phones):
    python cli.py verify --image scanned_label.png

    # 3. Test multi-camera invariance across 5 phone profiles:
    python cli.py test-cameras --serial PROD-1001

    # 4. Simulate and test reprint attack:
    python cli.py test-attack --serial PROD-1001
"""

import argparse
import sys
import json
from cdp_engine import create_anti_counterfeit_qr
from simulator import (
    simulate_genuine_scan, 
    simulate_counterfeit_reprint, 
    simulate_phone_capture, 
    simulate_counterfeit_reprint_captured,
    PHONE_PROFILES
)
from cdp_verifier import verify_anti_counterfeit_qr
import product_db

def cmd_generate(args):
    print(f"[*] Generating Anti-Counterfeit QR Code for Serial: {args.serial}...")
    # Pre-register in product DB if requested
    product_db.register_product(
        serial_no=args.serial,
        product_name=args.product_name,
        brand_name=args.brand_name,
        batch_no=args.batch_no,
    )
    qr_img, cdp_img = create_anti_counterfeit_qr(
        payload=args.payload,
        serial_no=args.serial,
        output_path=args.output,
        box_size=args.box_size,
        cdp_ratio=args.cdp_ratio
    )
    if args.cdp_output:
        cdp_img.save(args.cdp_output)
        print(f"[+] Standalone CDP module saved to: {args.cdp_output}")
    print(f"[+] Master Anti-Counterfeit QR Code saved to: {args.output}")

def cmd_verify(args):
    print(f"[*] Verifying image: {args.image}...")
    res = verify_anti_counterfeit_qr(
        args.image, 
        expected_serial=args.serial, 
        comparison_output_path=args.comparison_output
    )
    
    print("\n" + "="*58)
    print(f" AUTHENTICITY VERDICT:    {res['verdict']}")
    print(f" Authenticity Score:      {res['authenticity_score']}%")
    print(f" Image Quality Score:     {res.get('image_quality_score', 'N/A')}%")
    print(f" CDP Authenticity Score:  {res.get('cdp_authenticity_score', 'N/A')}%")
    print(f" Reprint Risk Score:      {res.get('reprint_risk_score', 'N/A')}%")
    print(f" QR Code Payload:         {res['qr_payload']}")
    print(f" Serial Number:           {res['serial_number']}")
    print("-" * 58)
    m = res.get('metrics', {})
    print(f" Peak NCC (Matched):      {m.get('peak_cross_correlation_ncc', 'N/A')}")
    print(f" Relative Acutance Ratio: {m.get('relative_acutance_ratio', 'N/A')}")
    print(f" Camera Macro Gradient:   {m.get('macro_gradient', 'N/A')}")
    print(f" CDP Micro Gradient:      {m.get('cdp_gradient', 'N/A')}")
    print(f" Micro-Void Count:        {m.get('micro_void_count', 'N/A')}")
    print(f" Photocopy Signature:     {m.get('is_photocopy_detected', 'N/A')}")
    print("="*58)
    print(f"Details: {res['description']}")
    if args.comparison_output:
        print(f"[+] Microscopic comparison saved to: {args.comparison_output}")

def cmd_test_cameras(args):
    print("=" * 82)
    print(f"MULTI-CAMERA INVARIANCE TEST SUITE (Serial: {args.serial})")
    print("=" * 82)
    payload = f"https://brand.com/verify?id={args.serial}"
    product_db.register_product(
        serial_no=args.serial,
        product_name="MultiCam Shield Test Product",
        brand_name="Aura Brand Security",
        batch_no="MC-2026",
    )
    qr_img, _ = create_anti_counterfeit_qr(payload=payload, serial_no=args.serial, box_size=12)

    print("\n[PART 1: GENUINE ORIGINAL PHYSICAL LABEL ACROSS DIFFERENT PHONES]")
    print(f"{'Phone Model':<28} | {'Quality':<7} | {'CDP Score':<9} | {'Reprint Risk':<12} | {'Final Score':<11} | {'Verdict'}")
    print("-" * 88)
    
    genuine_passes = 0
    total_genuine = len(PHONE_PROFILES)
    for model_key, prof in PHONE_PROFILES.items():
        sim_img = simulate_phone_capture(qr_img, phone_model=model_key, add_background=True)
        res = verify_anti_counterfeit_qr(sim_img, expected_serial=args.serial, save_debug_artifacts=False)
        q = res.get('image_quality_score', 0.0)
        c = res.get('cdp_authenticity_score', 0.0)
        r = res.get('reprint_risk_score', 0.0)
        s = res.get('authenticity_score', 0.0)
        v = res.get('status', 'FAIL')
        if "GENUINE" in v:
            genuine_passes += 1
        print(f"{prof['name']:<28} | {q:>6.1f}% | {c:>8.1f}% | {r:>11.1f}% | {s:>10.1f}% | {res['verdict']}")

    print("\n[PART 2: 2ND-GEN COUNTERFEIT REPRINT ATTACKS ACROSS SAME PHONES]")
    print(f"{'Phone Inspecting Fake':<28} | {'Quality':<7} | {'CDP Score':<9} | {'Reprint Risk':<12} | {'Final Score':<11} | {'Verdict'}")
    print("-" * 88)
    reprint_catches = 0
    for model_key, prof in PHONE_PROFILES.items():
        fake_img = simulate_counterfeit_reprint_captured(qr_img, phone_model=model_key, add_background=True)
        res = verify_anti_counterfeit_qr(fake_img, expected_serial=args.serial, save_debug_artifacts=False)
        q = res.get('image_quality_score', 0.0)
        c = res.get('cdp_authenticity_score', 0.0)
        r = res.get('reprint_risk_score', 0.0)
        s = res.get('authenticity_score', 0.0)
        v = res.get('status', 'FAIL')
        if "COUNTERFEIT" in v or "REPRINT" in v:
            reprint_catches += 1
        print(f"{prof['name']:<28} | {q:>6.1f}% | {c:>8.1f}% | {r:>11.1f}% | {s:>10.1f}% | {res['verdict']}")

    print("=" * 88)
    print(f"SUMMARY: Genuine Pass Rate: {genuine_passes}/{total_genuine} | Counterfeit Intercept Rate: {reprint_catches}/{total_genuine}")
    if genuine_passes == total_genuine and reprint_catches == total_genuine:
        print("[SUCCESS] Full camera invariance achieved! Genuine labels pass across all phones, while reprints are intercepted.")
    print("=" * 88)

def cmd_test_attack(args):
    print(f"[*] Running automated Reprint Attack Simulation for Serial: {args.serial}...")
    payload = f"https://brand.com/verify?id={args.serial}"
    product_db.register_product(serial_no=args.serial, product_name="Test Product", brand_name="Brand A", batch_no="B1")
    qr_img, _ = create_anti_counterfeit_qr(payload=payload, serial_no=args.serial, box_size=12)
    
    # 1st gen scan (Phone A)
    gen_scan = simulate_phone_capture(qr_img, phone_model="phone_a")
    res_gen = verify_anti_counterfeit_qr(gen_scan, expected_serial=args.serial)
    
    # 2nd gen counterfeit reprint (Phone A)
    fake_reprint = simulate_counterfeit_reprint_captured(qr_img, phone_model="phone_a")
    res_fake = verify_anti_counterfeit_qr(fake_reprint, expected_serial=args.serial)
    
    print("\n" + "="*60)
    print(" 1ST-GEN ORIGINAL SCAN RESULT:")
    print(f" Verdict: {res_gen['verdict']} ({res_gen['authenticity_score']}%)")
    print(f" Relative Acutance: {res_gen['metrics'].get('relative_acutance_ratio', 'N/A')}")
    print(f" Reprint Risk: {res_gen.get('reprint_risk_score', 'N/A')}%")
    print("-" * 60)
    print(" 2ND-GEN COUNTERFEIT REPRINT RESULT:")
    print(f" Verdict: {res_fake['verdict']} ({res_fake['authenticity_score']}%)")
    print(f" Relative Acutance: {res_fake['metrics'].get('relative_acutance_ratio', 'N/A')}")
    print(f" Reprint Risk: {res_fake.get('reprint_risk_score', 'N/A')}%")
    print("="*60)

def main():
    parser = argparse.ArgumentParser(description="Camera-Independent Anti-Counterfeit QR Code & CDP CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Generate
    gen_parser = subparsers.add_parser("generate", help="Generate Anti-Counterfeit QR Code")
    gen_parser.add_argument("--serial", required=True, help="Serial number / Seed key")
    gen_parser.add_argument("--payload", required=True, help="QR code data URL/payload")
    gen_parser.add_argument("--product-name", default="Secured Product", help="Product Name")
    gen_parser.add_argument("--brand-name", default="Genuine Brand", help="Brand Name")
    gen_parser.add_argument("--batch-no", default="BATCH-001", help="Batch number")
    gen_parser.add_argument("--output", default="anti_counterfeit_qr.png", help="Output file path")
    gen_parser.add_argument("--cdp-output", default=None, help="Save standalone CDP image")
    gen_parser.add_argument("--box-size", type=int, default=12, help="QR module size in pixels")
    gen_parser.add_argument("--cdp-ratio", type=float, default=0.32, help="Central CDP size ratio")

    # Verify
    ver_parser = subparsers.add_parser("verify", help="Verify authenticity of a QR code image")
    ver_parser.add_argument("--image", required=True, help="Path to image to verify")
    ver_parser.add_argument("--serial", default=None, help="Expected serial (optional)")
    ver_parser.add_argument("--comparison-output", default="comparison_report.png", help="Path to save visual comparison card")

    # Test Multi-Camera Invariance
    cam_parser = subparsers.add_parser("test-cameras", help="Run multi-camera invariance test across 5 phone profiles")
    cam_parser.add_argument("--serial", default="PROD-MULTICAM-2026", help="Serial key for test")

    # Test Attack
    atk_parser = subparsers.add_parser("test-attack", help="Simulate and test a reprint attack")
    atk_parser.add_argument("--serial", default="TEST-BATCH-2026", help="Serial key for test")

    args = parser.parse_args()
    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "test-cameras":
        cmd_test_cameras(args)
    elif args.command == "test-attack":
        cmd_test_attack(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
