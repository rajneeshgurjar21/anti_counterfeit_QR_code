"""
Command Line Interface (CLI) for Anti-Counterfeit QR Code System
==============================================================
Usage:
    # 1. Generate master anti-counterfeit QR code:
    python cli.py generate --serial PROD-1001 --payload "https://brand.com/verify?id=PROD-1001" --output qr_master.png

    # 2. Verify an image (detects whether it is Genuine or Counterfeit Reprint):
    python cli.py verify --image scanned_label.png

    # 3. Simulate and test reprint attack:
    python cli.py test-attack --serial PROD-1001
"""

import argparse
import sys
import json
from cdp_engine import create_anti_counterfeit_qr
from simulator import simulate_genuine_scan, simulate_counterfeit_reprint
from cdp_verifier import verify_anti_counterfeit_qr

def cmd_generate(args):
    print(f"[*] Generating Anti-Counterfeit QR Code for Serial: {args.serial}...")
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
    res = verify_anti_counterfeit_qr(args.image, expected_serial=args.serial, comparison_output_path=args.comparison_output)
    
    print("\n" + "="*50)
    print(f" AUTHENTICITY VERDICT: {res['verdict']}")
    print(f" Authenticity Score:    {res['authenticity_score']}%")
    print(f" QR Code Payload:       {res['qr_payload']}")
    print(f" Serial Number:         {res['serial_number']}")
    print("-" * 50)
    print(f" Peak NCC Match:        {res['metrics']['peak_cross_correlation_ncc']}")
    print(f" Laplacian Sharpness:   {res['metrics']['laplacian_edge_variance']}")
    print(f" Gradient Sharpness:    {res['metrics']['gradient_sharpness']}")
    print("="*50)
    print(f"Details: {res['description']}")
    if args.comparison_output:
        print(f"[+] Microscopic comparison saved to: {args.comparison_output}")

def cmd_test_attack(args):
    print(f"[*] Running automated Reprint Attack Simulation for Serial: {args.serial}...")
    payload = f"https://brand.com/verify?id={args.serial}"
    
    # Generate
    qr_img, _ = create_anti_counterfeit_qr(payload=payload, serial_no=args.serial, box_size=12)
    
    # 1st gen scan
    gen_scan = simulate_genuine_scan(qr_img)
    res_gen = verify_anti_counterfeit_qr(gen_scan, expected_serial=args.serial)
    
    # 2nd gen counterfeit reprint
    fake_reprint = simulate_counterfeit_reprint(qr_img)
    res_fake = verify_anti_counterfeit_qr(fake_reprint, expected_serial=args.serial)
    
    print("\n" + "="*60)
    print(" 1ST-GEN ORIGINAL SCAN RESULT:")
    print(f" Verdict: {res_gen['verdict']} ({res_gen['authenticity_score']}%)")
    print(f" NCC: {res_gen['metrics']['peak_cross_correlation_ncc']} | Sharpness: {res_gen['metrics']['laplacian_edge_variance']}")
    print("-" * 60)
    print(" 2ND-GEN COUNTERFEIT REPRINT RESULT:")
    print(f" Verdict: {res_fake['verdict']} ({res_fake['authenticity_score']}%)")
    print(f" NCC: {res_fake['metrics']['peak_cross_correlation_ncc']} | Sharpness: {res_fake['metrics']['laplacian_edge_variance']}")
    print("="*60)
    
    if res_gen['is_genuine'] and not res_fake['is_genuine']:
        print("[SUCCESS] Anti-Counterfeit CDP successfully differentiated Original from Fake Reprint!")
    else:
        print("[NOTICE] Check calibration thresholds.")

def main():
    parser = argparse.ArgumentParser(description="Anti-Counterfeit QR Code & CDP CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Generate
    gen_parser = subparsers.add_parser("generate", help="Generate Anti-Counterfeit QR Code")
    gen_parser.add_argument("--serial", required=True, help="Serial number / Seed key")
    gen_parser.add_argument("--payload", required=True, help="QR code data URL/payload")
    gen_parser.add_argument("--output", default="anti_counterfeit_qr.png", help="Output file path")
    gen_parser.add_argument("--cdp-output", default=None, help="Save standalone CDP image")
    gen_parser.add_argument("--box-size", type=int, default=12, help="QR module size in pixels")
    gen_parser.add_argument("--cdp-ratio", type=float, default=0.32, help="Central CDP size ratio")

    # Verify
    ver_parser = subparsers.add_parser("verify", help="Verify authenticity of a QR code image")
    ver_parser.add_argument("--image", required=True, help="Path to image to verify")
    ver_parser.add_argument("--serial", default=None, help="Expected serial (optional)")
    ver_parser.add_argument("--comparison-output", default="comparison_report.png", help="Path to save visual comparison card")

    # Test Attack
    atk_parser = subparsers.add_parser("test-attack", help="Simulate and test a reprint attack")
    atk_parser.add_argument("--serial", default="TEST-BATCH-2026", help="Serial key for test")

    args = parser.parse_args()
    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "test-attack":
        cmd_test_attack(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
