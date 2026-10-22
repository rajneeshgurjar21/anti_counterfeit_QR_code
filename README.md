# Anti-Counterfeit QR Code System with Copy Detection Pattern (CDP)

This system implements industrial-grade **Anti-Counterfeit QR Codes** embedding a **Copy Detection Pattern (CDP)** in the center of the barcode, matching the architecture shown in the reference design.

---

## 🔬 How It Works (The Science of CDP)

### 1. The Vulnerability of Normal QR Codes
Standard QR codes use large, high-contrast modules with built-in Reed-Solomon error correction. When someone photocopies or photographs and reprints a standard QR code, the reprinted code still scans 100% successfully. A standard QR code **cannot** distinguish between an authentic original label and a counterfeit photocopy.

### 2. The Copy Detection Pattern (CDP) Solution
A Copy Detection Pattern (CDP) is a high-entropy, pseudo-random micro-dot texture placed in the center cutout of the QR code:
- **Level H Error Correction (30% Recovery):** Allows replacing the central 30–32% region with the CDP without impeding standard QR code decoders.
- **Fiducial Registration Marks:** Small black square markers surrounding the CDP enable sub-pixel camera alignment, perspective correction, and orientation recovery.
- **Physical Print-and-Scan (P&S) Channel Degradation:**
  - **1st-Generation Print (Genuine Original):** High-resolution printing (600–1200 DPI) preserves distinct, razor-sharp micro-dots. Peak Normalized Cross-Correlation (NCC) with the digital master template is $\ge 0.70 - 0.95$.
  - **2nd-Generation Reprint (Counterfeit / Photocopy Attack):** When a counterfeiter captures the label with a scanner or smartphone camera and reprints it, the image undergoes consecutive optical blurring, sensor Bayer demosaicing, and secondary printer ink-bleeding (dot gain). The micro-dots blend into blurry blobs, causing the high-frequency spectral energy and Laplacian edge variance to drop by over **80%–95%**. The verification engine detects this collapse and flags the code as **`COUNTERFEIT (REPRINT DETECTED)`**.

---

## 📁 System Architecture

| File | Purpose |
| :--- | :--- |
| `cdp_engine.py` | Generates deterministic pseudo-random micro-patterns, fiducial markers, and merges them into Level-H QR codes at print-ready 600 DPI. |
| `cdp_verifier.py` | Decodes QR payloads, extracts the central CDP, rectifies perspective, computes Peak NCC, Laplacian edge acutance, and outputs the authenticity verdict. |
| `simulator.py` | Accurate physical simulation of 1st-generation mobile scanning and 2nd-generation photocopy/reprint attacks. |
| `web_app.py` | Interactive Web Dashboard with live generation, simulation, upload verification, and microscopic degradation heatmaps. |
| `cli.py` | Command-line tool for generation, verification, and batch processing. |
| `demo_pipeline.py` | End-to-end automated demonstration script. |

---

## 🚀 Quick Start Guide

### 1. Run the Interactive Web Studio
```bash
python web_app.py
```
Open **http://localhost:8080** in your browser. You can:
- Generate anti-counterfeit QR codes with custom serial numbers and URLs.
- Click **"Scan 1st-Gen Genuine Print"** to verify original authenticity (100% Genuine).
- Click **"Simulate Counterfeit Reprint Attack"** to test attack detection (0% Fake detected).
- View side-by-side microscopic zoom and degradation heatmaps.

### 2. Command Line Interface (CLI)

#### A. Generate an Anti-Counterfeit QR Code:
```bash
python cli.py generate --serial "PROD-998822" --payload "https://brand.com/verify?id=PROD-998822" --output "master_qr.png" --cdp-output "cdp_tile.png"
```

#### B. Verify an Image (Detects Genuine vs Counterfeit Reprint):
```bash
python cli.py verify --image "master_qr.png" --comparison-output "verification_card.png"
```

#### C. Run Automated Attack Simulation:
```bash
python cli.py test-attack --serial "BATCH-2026-X1"
```

---

## 📊 Verification Metrics Breakdown

| Metric | Genuine 1st-Gen Print | Counterfeit Reprint | Threshold |
| :--- | :--- | :--- | :--- |
| **Peak NCC Template Match** | `0.7300 - 0.9400` | `0.3800 - 0.4200` | $\ge 0.65$ |
| **Laplacian Edge Variance** | `10,000 - 32,000+` | `100 - 500` | $\ge 1,500$ |
| **Gradient Sharpness (Sobel)** | `450 - 550+` | `80 - 150` | $\ge 180$ |
| **Authenticity Verdict** | **GENUINE** | **COUNTERFEIT** | Pass / Fail |
