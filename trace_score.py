import cdp_engine, simulator, cdp_verifier

serial = "PROD-2026-X8879"
payload = f"https://brand-auth.com/verify?id={serial}"
qr_img, _ = cdp_engine.create_anti_counterfeit_qr(payload=payload, serial_no=serial)
sim_img = simulator.simulate_genuine_scan(qr_img)
res = cdp_verifier.verify_anti_counterfeit_qr(sim_img, expected_serial=serial)
print("Score:", res["authenticity_score"])
print("Metrics:", res["metrics"])
