import cdp_engine, simulator, cdp_verifier

s = 'PROD-MULTI-TEST-2026'
qr, _ = cdp_engine.create_anti_counterfeit_qr(payload='https://x.com/?id=' + s, serial_no=s)

print("--- 1ST-GEN GENUINE SCANS ---")
for p in ['phone_a', 'phone_b', 'phone_c', 'phone_d', 'phone_e']:
    img = simulator.simulate_phone_capture(qr, phone_model=p, add_background=True)
    res = cdp_verifier.verify_anti_counterfeit_qr(img, expected_serial=s)
    m = res['metrics']
    print(f"{p:<8} | Macro_G: {m['macro_gradient']:>6.1f} | CDP_G: {m['cdp_gradient']:>6.1f} | Rel_G: {m['relative_acutance_ratio']:>6.3f} | Rel_Lap: {m['relative_laplacian_ratio']:>6.3f} | HF: {m['fft_high_freq_ratio']:>8.5f} | Score: {res['authenticity_score']}")

print("\n--- 2ND-GEN COUNTERFEIT REPRINTS ---")
for p in ['phone_a', 'phone_b', 'phone_c', 'phone_d', 'phone_e']:
    fake_img = simulator.simulate_counterfeit_reprint_captured(qr, phone_model=p, add_background=True)
    res = cdp_verifier.verify_anti_counterfeit_qr(fake_img, expected_serial=s)
    m = res['metrics']
    print(f"{p:<8} | Macro_G: {m['macro_gradient']:>6.1f} | CDP_G: {m['cdp_gradient']:>6.1f} | Rel_G: {m['relative_acutance_ratio']:>6.3f} | Rel_Lap: {m['relative_laplacian_ratio']:>6.3f} | HF: {m['fft_high_freq_ratio']:>8.5f} | Score: {res['authenticity_score']}")
