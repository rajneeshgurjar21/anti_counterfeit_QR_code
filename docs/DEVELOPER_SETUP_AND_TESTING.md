# Anti-Counterfeit QR Code System: Developer Setup, Operations & Testing Guide

> **Document Version:** 2.0.0  
> **Status:** Production Reference  
> **Module Path:** `C:\Users\91761\.gemini\antigravity\scratch\anti_counterfeit_qr\docs`  

---

## 1. System Requirements & Prerequisites

### 1.1 Hardware Prerequisites
- **Host Machine:** Windows 10/11, macOS, or Linux (x86_64 or ARM64).
- **Physical Printer (for physical tests):** Standard office laser or inkjet printer capable of $\ge 600\text{ DPI}$.
- **Mobile Device (for scanning):** Any modern smartphone with camera autofocus and macro capability (iPhone 11+, Samsung Galaxy S20+, Google Pixel 5+, or equivalent budget devices with 12MP+ cameras).
- **Photocopier (for counterfeit attack tests):** Standard office multifunction photocopier (Xerox, HP, Canon, Konica Minolta, Ricoh).

### 1.2 Software Prerequisites
- **Python:** Version `3.10` or higher (verified on Python `3.14.0`).
- **Required Libraries:**
  ```bash
  pip install opencv-python pillow numpy qrcode
  ```

---

## 2. Installation & Quick-Start

### 2.1 Repository Setup
Navigate to the project root directory:
```bash
cd C:\Users\91761\.gemini\antigravity\scratch\anti_counterfeit_qr
```

### 2.2 Verify Environment & Dependencies
Run a quick diagnostic check to verify all C++ computer vision and QR bindings:
```bash
python -c "import cv2, qrcode, PIL, numpy, sqlite3; print('All dependencies loaded successfully!')"
```

---

## 3. Running the Interactive Web Studio

The web application is self-contained and serves both the REST API and the interactive HTML5 dashboard:

```bash
python web_app.py 8080
```

- Open your web browser and navigate to:
  **`http://localhost:8080`**
- On a mobile device connected to the same Wi-Fi network, access:
  **`http://<YOUR_COMPUTER_LOCAL_IP>:8080`**

### 3.1 Features Available in Web Studio
1. **Studio Tab (Generation & Simulations):**
   - Fill in serial number, product name, batch ID, and expiry date.
   - Click **"Generate Master Anti-Counterfeit QR"** to render a fresh code.
   - Click one-click simulation buttons: **"1. Genuine Scan"**, **"2. Blur Attack"**, **"3. Reprint Attack"**, and **"4. Photocopy Attack"**.
2. **Camera Scanner Tab:**
   - Tap **"▶️ Start Camera"** for live browser scanning.
   - Tap **"📱 Take High-Res Photo (Phone Native Camera)"** to open the phone's native camera app with optical autofocus and flash.
3. **Upload Tab:**
   - Drag-and-drop or upload saved photos from disk.
4. **Blur Stress-Testing Tab:**
   - Adjust Gaussian blur sigma between $0.0$ and $2.5$ to observe the exact threshold where an image transitions from `GENUINE` to `SUSPICIOUS` and `RECAPTURE_REQUIRED`.
5. **Product Registry Tab:**
   - Inspect all registered products, cumulative scan counters, and reset counters with one click.

---

## 4. Command Line Interface (CLI) Guide

The `cli.py` script provides standalone batch operations without starting the web server.

### 4.1 Generate an Anti-Counterfeit QR Code
```bash
python cli.py generate --serial "PROD-2026-X8879" --payload "https://brand-auth.com/verify?id=PROD-2026-X8879" --output "master_qr.png" --cdp-output "cdp_tile.png"
```
- Creates `master_qr.png` (composite QR + CDP at 600 DPI).
- Creates `cdp_tile.png` (standalone micro-dot tile).

### 4.2 Verify an Image File
```bash
python cli.py verify --image "master_qr.png" --comparison-output "verification_card.png"
```
- Analyzes `master_qr.png`, decodes the payload, rectifies the CDP, and outputs the numerical metrics and verdict to stdout.
- Writes a degradation heatmap comparison card to `verification_card.png`.

### 4.3 Run Automated Attack Simulation
```bash
python cli.py test-attack --serial "TEST-BATCH-2026"
```

---

## 5. Automated Validation & Test Suite

To run the complete 13-scenario automated regression suite:

```bash
python test_master_suite.py
```

### 5.1 Scenarios Tested
1. **Scenario 1:** Original Master QR (Digital Master / 600 DPI) $\to$ Expected: `GENUINE` ($\ge 90\%$).
2. **Scenario 2:** Genuine Print - Phone Photo (Straight-on) $\to$ Expected: `GENUINE` ($\ge 65\%$).
3. **Scenario 3:** Genuine Print - Moderate Angle / 15° Perspective Tilt $\to$ Expected: `GENUINE` ($\ge 65\%$).
4. **Scenario 4:** Genuine Print - Non-uniform Lighting / Shadow $\to$ Expected: `GENUINE` ($\ge 65\%$).
5. **Scenario 5:** Genuine Print - Budget Camera Sensor Noise $\to$ Expected: `GENUINE` ($\ge 65\%$).
6. **Scenario 6:** Slightly Blurred / Low-Res Capture $\to$ Expected: `SUSPICIOUS` / `RECAPTURE_REQUIRED` (Must not falsely classify as counterfeit).
7. **Scenario 7:** Cropped / Obstructed QR Code $\to$ Expected: `UNREADABLE`.
8. **Scenario 8a:** 2nd-Gen Reprint Attack (Rescan Blur / MTF Loss) $\to$ Expected: `COUNTERFEIT` ($\le 35\%$).
9. **Scenario 8b:** Office Photocopier Attack (Toner Bleed / Clumping) $\to$ Expected: `COUNTERFEIT` ($\le 25\%$).
10. **Scenario 9:** Unknown / Unregistered Serial Number $\to$ Expected: `UNREGISTERED` alert.
11. **Scenario 10:** Substituted Security Graphic (Wrong CDP Seed) $\to$ Expected: `COUNTERFEIT` ($\le 25\%$).
12. **Scenario 11:** Revoked / Blacklisted Serial Number $\to$ Expected: `BLACKLISTED` ($0\%$).
13. **Scenario 12:** Repeated Scans (Multi-Scan Clone Alert) $\to$ Expected: `CLONE_ALERT` triggered.

---

## 6. How to Reproduce Physical Print & Photocopy Scenarios

Follow this step-by-step protocol to test physical labels:

### Step 1: Generate & Print the Original QR Code
1. Open `http://localhost:8080`.
2. Enter Serial: `PROD-2026-X0001`, Product: `CardioGuard Extra 20mg`.
3. Click **"Generate Master Anti-Counterfeit QR"**.
4. Click **"Download Master Print PNG (600 DPI)"**.
5. Print the downloaded PNG on a standard office printer:
   - Paper: Standard 75–80 GSM white paper or matte sticker label stock.
   - Scale: Set printer scaling to **100% (Actual Size)** (approx. $2.7 \times 2.7\text{ cm}$ or $1.1 \times 1.1\text{ in}$).
   - Quality: High / Best (600 DPI).

### Step 2: Test Scenario 1 (Original Genuine Print)
1. Place the printed paper under normal room lighting.
2. Open your phone camera or the Web Studio at `http://<IP>:8080`.
3. Take a sharp, well-lit photo from approx. 12–18 cm away, ensuring the QR code fills 40–70% of the viewfinder.
4. Upload the photo to the application.
5. **Expected Result:**
   - Verdict: **`GENUINE (ORIGINAL PRINT)`**
   - Confidence Score: **$85\% - 95\%$**
   - Dot P/A Ratio: **$0.25 - 0.45$**
   - Toner Density: **$48\% - 54\%$**

### Step 3: Test Scenario 2 (Photocopied Counterfeit Print)
1. Take the printed paper from Step 1 to an office photocopier / Xerox machine.
2. Make a standard 1:1 black-and-white photocopy onto a second sheet of paper.
3. Take a photograph of the **photocopied paper** using the exact same phone camera under the same lighting.
4. Upload the photo to the application.
5. **Expected Result:**
   - Verdict: **`COUNTERFEIT (PHOTOCOPY / REPRINT DETECTED)`**
   - Confidence Score: **$10\% - 20\%$** (Strictly $\le 22.0\%$)
   - Dot P/A Ratio: **$0.06 - 0.14$** *(Micro-dot perimeter collapsed)*
   - Toner Density: **$68\% - 80\%$** *(Abnormally dark / saturated toner)*
   - Dot Count: **$2 - 4$** *(Dots fused into massive clumps)*

---

## 7. Troubleshooting & FAQ

### 1. `RECAPTURE REQUIRED – IMAGE TOO BLURRY`
- **Cause:** Global Laplacian variance is $< 25.0$. The photo was taken while moving or the camera lens was out of focus.
- **Solution:** Tap your phone screen to focus on the QR code, ensure sufficient room light, and hold the device steady.

### 2. `UNREADABLE QR CODE (OBSTRUCTED OR DAMAGED)`
- **Cause:** OpenCV's barcode finder pattern detector failed to localize 3 corner squares.
- **Solution:** Ensure the quiet zone (white margin around the QR code) is not cut off by the photo frame.

### 3. Port `8080` Already in Use
- **Error:** `OSError: [WinError 10048] Only one usage of each socket address is normally permitted`.
- **Solution:**
  ```powershell
  # Find PID on port 8080:
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8080).OwningProcess
  # Stop the process:
  Stop-Process -Id <PID> -Force
  # Or start on an alternate port:
  python web_app.py 8085
  ```

### 4. Live Camera Access Blocked in Mobile Browser
- **Cause:** Mobile browsers (Safari on iOS and Chrome on Android) require an `HTTPS` connection to grant live video streaming access to `getUserMedia`.
- **Solution:** Use the dedicated **"📱 Take High-Res Photo (Phone Native Camera)"** button in the Web Studio. This invokes the OS-level file capture API (`<input type="file" capture="environment">`), which works reliably over standard HTTP local IP connections.
