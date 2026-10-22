"""
Anti-Counterfeit QR Code & Product Registry Web Studio
=====================================================
Integrated Dual-Shield Verification:
1. Physical Anti-Counterfeit Verification (CDP Micro-dot Acutance & 2D-FFT)
2. Product Identity & Supply Chain Registry (Product Name, Batch, Expiry, Scan Counter & Clone Detection)
"""

import os
import io
import json
import base64
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import numpy as np
from PIL import Image
import cv2

from cdp_engine import create_anti_counterfeit_qr, generate_cdp_module_with_fiducials
from simulator import simulate_genuine_scan, simulate_counterfeit_reprint
from cdp_verifier import verify_anti_counterfeit_qr
import product_db

def pil_to_base64(img: Image.Image, format="PNG", dpi=(600, 600)) -> str:
    buffered = io.BytesIO()
    img.save(buffered, format=format, dpi=dpi)
    return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode("utf-8")

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anti-Counterfeit QR Code & Product Authentication Studio</title>
<style>
  :root {
    --bg-dark: #080c16;
    --card-bg: #11192b;
    --card-border: #1e2c45;
    --accent-blue: #38bdf8;
    --accent-purple: #a855f7;
    --success: #22c55e;
    --danger: #ef4444;
    --warning: #f59e0b;
    --text-main: #f8fafc;
    --text-muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
  body { background: var(--bg-dark); color: var(--text-main); min-height: 100vh; padding: 18px 14px; }
  .header { text-align: center; margin-bottom: 20px; }
  .header h1 { font-size: 2.1rem; background: linear-gradient(135deg, #38bdf8, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 4px; }
  .header p { color: var(--text-muted); font-size: 1rem; }
  
  .container { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; max-width: 1440px; margin: 0 auto; }
  @media (max-width: 1080px) { .container { grid-template-columns: 1fr; } }
  
  .card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 18px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); }
  .card-title { font-size: 1.15rem; font-weight: 600; margin-bottom: 14px; color: var(--accent-blue); display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--card-border); padding-bottom: 8px; }
  
  .form-group { margin-bottom: 12px; }
  label { display: block; font-size: 0.82rem; color: var(--text-muted); margin-bottom: 4px; font-weight: 500; }
  input, select { width: 100%; background: #080d1a; border: 1px solid var(--card-border); border-radius: 6px; padding: 8px 10px; color: #fff; font-size: 0.9rem; outline: none; }
  input:focus, select:focus { border-color: var(--accent-blue); }
  
  .btn-row { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
  button { flex: 1; min-width: 120px; padding: 9px 14px; border-radius: 6px; font-size: 0.88rem; font-weight: 600; cursor: pointer; border: none; transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 6px; }
  .btn-primary { background: linear-gradient(135deg, #0284c7, #2563eb); color: #fff; }
  .btn-primary:hover { opacity: 0.92; transform: translateY(-1px); }
  .btn-success { background: linear-gradient(135deg, #16a34a, #15803d); color: #fff; }
  .btn-danger { background: linear-gradient(135deg, #dc2626, #b91c1c); color: #fff; }
  .btn-warning { background: linear-gradient(135deg, #d97706, #b45309); color: #fff; }
  .btn-outline { background: #1e293b; border: 1px solid var(--card-border); color: #fff; }
  .btn-outline:hover { background: #334155; }
  
  .preview-area { display: flex; flex-direction: column; align-items: center; justify-content: center; background: #070a14; border: 2px dashed var(--card-border); border-radius: 10px; padding: 14px; min-height: 240px; position: relative; margin-top: 12px; }
  .preview-img { max-width: 100%; max-height: 240px; border-radius: 6px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
  .download-btn { margin-top: 10px; padding: 7px 14px; font-size: 0.82rem; background: #23324d; color: #fff; border-radius: 6px; text-decoration: none; cursor: pointer; display: inline-block; }
  .download-btn:hover { background: #33476b; }
  
  .tab-buttons { display: flex; gap: 6px; margin-bottom: 12px; border-bottom: 1px solid var(--card-border); padding-bottom: 8px; overflow-x: auto; }
  .tab-btn { background: transparent; border: 1px solid transparent; color: var(--text-muted); padding: 6px 11px; border-radius: 6px; font-size: 0.85rem; cursor: pointer; white-space: nowrap; }
  .tab-btn.active { background: #1e293b; color: #fff; border-color: var(--accent-blue); font-weight: 600; }
  
  .badge { display: inline-block; padding: 5px 12px; border-radius: 20px; font-weight: 700; font-size: 0.95rem; text-align: center; }
  .badge-genuine { background: rgba(34, 197, 94, 0.2); color: var(--success); border: 1px solid var(--success); }
  .badge-counterfeit { background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }
  .badge-suspicious { background: rgba(245, 158, 11, 0.2); color: var(--warning); border: 1px solid var(--warning); }
  .badge-recapture { background: rgba(56, 189, 248, 0.2); color: var(--accent-blue); border: 1px solid var(--accent-blue); }
  .badge-unknown { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid #64748b; }
  .badge-blacklisted { background: rgba(220, 38, 38, 0.3); color: #fca5a5; border: 1px solid #ef4444; }
  .guidance-box { background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 10px 14px; margin-top: 10px; font-size: 0.85rem; color: #bae6fd; }
  
  .product-box { background: #070a14; border: 1px solid var(--card-border); border-radius: 8px; padding: 12px; margin-top: 12px; }
  .product-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem; margin-top: 6px; }
  .product-item { background: #11192b; border: 1px solid #1a273e; padding: 8px 10px; border-radius: 6px; }
  .product-label { color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; margin-bottom: 2px; }
  .product-val { color: #fff; font-weight: 600; font-size: 0.88rem; }
  
  .alert-banner { padding: 10px 14px; border-radius: 8px; margin-top: 10px; font-size: 0.86rem; display: flex; align-items: center; gap: 8px; }
  .alert-warning { background: rgba(245, 158, 11, 0.15); border: 1px solid var(--warning); color: #fbbf24; }
  .alert-success { background: rgba(34, 197, 94, 0.15); border: 1px solid var(--success); color: #4ade80; }
  .alert-danger { background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); color: #f87171; }
  
  .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 12px; }
  @media (max-width: 768px) { .metric-grid { grid-template-columns: repeat(2, 1fr); } }
  .metric-card { background: #070a14; border: 1px solid var(--card-border); border-radius: 6px; padding: 8px; text-align: center; }
  .metric-label { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 2px; }
  .metric-value { font-size: 1.05rem; font-weight: 700; color: #fff; }
  
  .comparison-box { margin-top: 14px; text-align: center; }
  .comparison-img { width: 100%; border-radius: 6px; border: 1px solid var(--card-border); margin-top: 6px; }
  
  .slider-box { background: #070a14; border: 1px solid var(--card-border); border-radius: 8px; padding: 12px; margin-top: 10px; }
  .slider-row { display: flex; align-items: center; gap: 10px; margin-top: 6px; }
  .slider-val { font-weight: bold; color: var(--accent-blue); min-width: 45px; font-size: 1rem; }
  
  .loader { display: none; border: 3px solid #334155; border-top: 3px solid var(--accent-blue); border-radius: 50%; width: 26px; height: 26px; animation: spin 0.8s linear infinite; margin: 12px auto; }
  @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
  
  .inventory-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 10px; }
  .inventory-table th, .inventory-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--card-border); }
  .inventory-table th { background: #080d1a; color: var(--accent-blue); text-transform: uppercase; font-size: 0.72rem; }
  .inventory-table tr:hover { background: #162035; }

  /* Live Camera Scanner Styles */
  .camera-box { position: relative; width: 100%; background: #060913; border: 1px solid var(--card-border); border-radius: 10px; overflow: hidden; min-height: 260px; display: flex; align-items: center; justify-content: center; }
  #cameraVideo { width: 100%; max-height: 320px; object-fit: cover; display: none; background: #020617; }
  .viewfinder { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 200px; height: 200px; border: 2px dashed rgba(56, 189, 248, 0.75); border-radius: 12px; pointer-events: none; box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5); }
  .viewfinder::before { content: ""; position: absolute; inset: -3px; border: 3px solid var(--accent-blue); border-radius: 14px; clip-path: polygon(0 0, 26% 0, 26% 100%, 0 100%, 0 0, 100% 0, 100% 26%, 74% 26%, 74% 0, 100% 0, 100% 100%, 74% 100%, 74% 74%, 100% 74%, 100% 100%, 0 100%, 0 74%, 26% 74%, 26% 100%, 0 100%); }
  .scan-laser { position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, #38bdf8, transparent); box-shadow: 0 0 8px #38bdf8; animation: scanAnim 2.2s ease-in-out infinite alternate; }
  @keyframes scanAnim { 0% { top: 0%; opacity: 0.3; } 50% { opacity: 1; } 100% { top: 100%; opacity: 0.3; } }
  .mobile-pill { display: inline-flex; align-items: center; gap: 6px; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); padding: 4px 10px; border-radius: 20px; font-size: 0.76rem; color: var(--accent-blue); margin-top: 6px; }
</style>
</head>
<body>

<div class="header">
  <h1>Anti-Counterfeit QR Code & Product Authentication Studio</h1>
  <p>Dual-Shield Authentication: Physical Copy Detection Pattern (CDP) + Official Product Registry</p>
  <div class="mobile-pill">📱 Mobile Scan URL: <b>http://192.168.29.142:8080</b> (Open on your phone on same Wi-Fi)</div>
</div>

<div class="container">

  <!-- LEFT: PRODUCT & MASTER QR GENERATOR -->
  <div class="card">
    <div class="card-title">
      <span>1. Register Product & Generate QR</span>
      <span style="font-size:0.75rem; color:var(--text-muted);">600 DPI Print-Ready</span>
    </div>
    
    <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 8px;">
      <div class="form-group">
        <label>Product Name</label>
        <input type="text" id="prodName" value="UltraShield Antiviral 500mg">
      </div>
      <div class="form-group">
        <label>Brand / Manufacturer</label>
        <input type="text" id="brandName" value="Apex Pharma Labs">
      </div>
    </div>
    
    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;">
      <div class="form-group">
        <label>Batch Number</label>
        <input type="text" id="batchNo" value="BATCH-09">
      </div>
      <div class="form-group">
        <label>Expiry Date</label>
        <input type="text" id="expDate" value="2029-01-14">
      </div>
      <div class="form-group">
        <label>MRP / Price</label>
        <input type="text" id="mrp" value="Rs. 450.00">
      </div>
    </div>

    <div class="form-group">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
        <label style="margin:0;">Serial Number (Unique per item - Seed for CDP)</label>
        <button type="button" class="btn-outline" style="flex:none; padding:2px 8px; font-size:0.75rem;" onclick="generateNewSerial()">🎲 New Unique Serial</button>
      </div>
      <input type="text" id="serialNo" value="PROD-2026-X8879" oninput="syncPayload()">
    </div>
    
    <div class="form-group">
      <label>QR Payload / Verification URL (Auto-Synced with Serial)</label>
      <input type="text" id="qrPayload" value="https://brand-auth.com/verify?id=PROD-2026-X8879&batch=09" readonly style="background:#060a14; color:var(--accent-blue); font-family:monospace; font-size:0.82rem;">
    </div>
    
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
      <div class="form-group">
        <label>CDP Size Ratio</label>
        <select id="cdpRatio">
          <option value="0.32" selected>32% (Standard Level H)</option>
          <option value="0.30">30% (Compact)</option>
          <option value="0.34">34% (High Entropy)</option>
        </select>
      </div>
      <div class="form-group">
        <label>Print Resolution</label>
        <select id="boxSize">
          <option value="12" selected>12px (600 DPI Master)</option>
          <option value="10">10px (Small Label)</option>
          <option value="14">14px (Carton Box)</option>
        </select>
      </div>
    </div>
    
    <div class="btn-row">
      <button class="btn-primary" onclick="generateQR()">Register Product & Generate QR</button>
    </div>
    
    <div class="preview-area" id="genPreview">
      <img id="qrImage" class="preview-img" style="display:none;" alt="Generated QR">
      <div id="genPlaceholder" style="color:var(--text-muted); text-align:center;">
        Click <b>Register Product & Generate QR</b> to create the master barcode.
      </div>
      <div id="qrMetaBadge" style="display:none; margin-top:8px; font-size:0.75rem; color:var(--accent-blue); background:#0c1524; border:1px solid #1e2c45; border-radius:6px; padding:6px 10px; text-align:center;">
        <span id="qrDimensions">588 × 588 px</span> &bull; <b style="color:var(--success);">600 DPI Master Print</b> &bull; Physical Size: <span id="qrPhysicalSize">2.49 × 2.49 cm</span>
      </div>
      <a id="downloadLink" class="download-btn" style="display:none;" download="anti_counterfeit_qr.png">Download 600 DPI Master PNG</a>
    </div>
  </div>

  <!-- RIGHT: DUAL-SHIELD TEST RUNNER & VERIFIER -->
  <div class="card">
    <div class="card-title">
      <span>2. Product & Physical Authenticity Check</span>
      <span style="font-size:0.75rem; color:var(--text-muted);">Real-Time Verifier</span>
    </div>
    
    <div class="tab-buttons">
      <button class="tab-btn active" onclick="setTab('suite')">1-Click Test Suite</button>
      <button class="tab-btn" onclick="setTab('camera')">📸 Live Camera Scan</button>
      <button class="tab-btn" onclick="setTab('upload')">📁 Upload Image</button>
      <button class="tab-btn" onclick="setTab('blur')">Custom Blur Slider</button>
      <button class="tab-btn" onclick="setTab('inventory')">Database Registry</button>
    </div>
    
    <!-- TAB 1: 1-CLICK TEST SUITE -->
    <div id="tabSuite">
      <div id="activeProductBanner" style="background:#070d1a; border:1px solid #1e2c45; border-radius:6px; padding:7px 10px; margin-bottom:10px; font-size:0.82rem; display:flex; justify-content:space-between; align-items:center;">
        <span>Active Subject: <b id="activeSerialBadge" style="color:var(--accent-blue);">PROD-2026-X8879</b> (<span id="activeNameBadge">UltraShield Antiviral 500mg</span>)</span>
        <button type="button" class="btn-outline" style="flex:none; padding:2px 8px; font-size:0.72rem;" onclick="generateNewSerial()">+ New Serial</button>
      </div>
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;">
        <button class="btn-success" onclick="runSim('genuine')">1. Genuine Scan</button>
        <button class="btn-warning" onclick="runSim('blur_test')">2. Blur Attack</button>
        <button class="btn-danger" onclick="runSim('counterfeit')">3. Reprint Attack</button>
        <button class="btn-danger" style="background:linear-gradient(135deg, #7f1d1d, #991b1b);" onclick="runSim('photocopy')">4. Photocopy Attack</button>
      </div>
    </div>

    <!-- TAB 2: LIVE CAMERA SCANNER -->
    <div id="tabCamera" style="display:none;">
      <p style="color: var(--text-muted); font-size: 0.82rem; margin-bottom: 8px;">
        Scan physical printed QR code directly from your mobile or laptop camera:
      </p>

      <div class="camera-box">
        <video id="cameraVideo" autoplay playsinline muted></video>
        <div id="cameraViewfinder" class="viewfinder" style="display:none;">
          <div class="scan-laser"></div>
        </div>
        <div id="cameraPlaceholder" style="padding: 30px 16px; text-align: center; color: var(--text-muted);">
          <div style="font-size: 2.2rem; margin-bottom: 8px;">📷</div>
          <div style="font-size: 0.95rem; font-weight: 600; color: #fff; margin-bottom: 4px;">Live Viewfinder Ready</div>
          <div style="font-size: 0.8rem; line-height: 1.4;">Click <b>Start Camera</b> to open the live scanner,<br>or tap <b>Take High-Res Photo</b> to use your phone's native camera.</div>
        </div>
      </div>

      <div style="display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap;">
        <button id="btnStartCam" class="btn-primary" onclick="startCamera()">▶️ Start Camera</button>
        <button id="btnSnapCam" class="btn-success" style="display:none;" onclick="captureCameraFrame()">⚡ Snap & Verify</button>
        <button id="btnSwitchCam" class="btn-outline" style="display:none; flex:0 0 auto;" onclick="switchCamera()">🔄 Switch</button>
        <button id="btnStopCam" class="btn-danger" style="display:none; flex:0 0 auto;" onclick="stopCamera()">⏹️ Stop</button>
      </div>

      <div style="margin-top: 12px; border-top: 1px dashed var(--card-border); padding-top: 10px;">
        <button type="button" class="btn-warning" style="width:100%;" onclick="openNativeCamera()">
          📱 Take High-Res Photo (Phone Native Camera)
        </button>
        <input type="file" id="nativeCameraInput" accept="image/*" capture="environment" style="display:none;" onchange="uploadImage(event)">
        <p style="font-size: 0.72rem; color: var(--text-muted); margin-top: 5px; text-align: center;">
          💡 <b>Recommended for mobile:</b> Native Camera provides optical autofocus, flashlight, and full sensor resolution (12MP+ macro) for microscopic dot verification.
        </p>
      </div>
    </div>
    
    <!-- TAB 3: BLUR SLIDER ATTACK -->
    <div id="tabBlur" style="display:none;">
      <p style="color: var(--text-muted); font-size: 0.85rem;">
        Test how blur degradation is detected at different intensities:
      </p>
      <div class="slider-box">
        <div style="display: flex; justify-content: space-between;">
          <label>Blur Intensity (Gaussian Sigma):</label>
          <span class="slider-val" id="blurLabel">0.8</span>
        </div>
        <div class="slider-row">
          <input type="range" id="blurSlider" min="0.0" max="2.5" step="0.1" value="0.8" oninput="updateBlurLabel(this.value)">
          <button class="btn-warning" style="flex:0 0 130px;" onclick="runCustomBlur()">Apply & Test</button>
        </div>
      </div>
    </div>
    
    <!-- TAB 4: FILE UPLOAD -->
    <div id="tabUpload" style="display:none;">
      <div class="form-group">
        <label>Upload photo of printed QR or any test image</label>
        <input type="file" id="fileUpload" accept="image/*" onchange="uploadImage(event)">
      </div>
    </div>

    <!-- TAB 4: INVENTORY DATABASE REGISTRY -->
    <div id="tabInventory" style="display:none;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:0.85rem; color:var(--text-muted);">Registered Products in Official Database</span>
        <button class="btn-outline" style="flex:none; padding:4px 10px; font-size:0.75rem;" onclick="loadInventory()">Refresh List</button>
      </div>
      <div style="max-height: 280px; overflow-y: auto; margin-top:8px;">
        <table class="inventory-table">
          <thead>
            <tr>
              <th>Serial</th>
              <th>Product Name</th>
              <th>Batch</th>
              <th>Scans</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="inventoryBody">
            <!-- Dynamically populated -->
          </tbody>
        </table>
      </div>
    </div>
    
    <div id="loader" class="loader"></div>
    
    <!-- DUAL-SHIELD RESULT REPORT -->
    <div id="resultSection" style="display:none; margin-top: 14px;">
      
      <!-- AUTHENTICITY HEADER -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <div>
          <div style="font-size:0.75rem; color:var(--text-muted);">PHYSICAL AUTHENTICITY</div>
          <div id="verdictBadge" class="badge"></div>
        </div>
        <div style="text-align: right;">
          <div style="font-size:0.75rem; color:var(--text-muted);">CONFIDENCE SCORE</div>
          <div id="authScore" style="font-size: 1.7rem; font-weight:800; color: #fff;"></div>
        </div>
      </div>

      <!-- STATUS MESSAGE & GUIDANCE -->
      <div id="statusMessageBar" style="font-size:0.95rem; font-weight:600; margin-bottom:8px; color:#fff; border-left:3px solid var(--accent-blue); padding-left:8px;"></div>
      <div id="guidanceBanner" class="guidance-box" style="display:none;"></div>
      
      <!-- CLONE / DUPLICATE ALERT BANNER -->
      <div id="cloneAlertBanner" class="alert-banner" style="display:none;"></div>
      
      <!-- OFFICIAL PRODUCT REGISTRY CARD -->
      <div class="product-box">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e2c45; padding-bottom:6px; margin-bottom:6px;">
          <span style="font-weight:700; color:var(--accent-blue); font-size:0.9rem;">Official Product Record</span>
          <span id="prodRegistryStatus" style="font-size:0.75rem; font-weight:600;"></span>
        </div>
        <div class="product-grid">
          <div class="product-item">
            <div class="product-label">Decoded Serial Number</div>
            <div class="product-val" id="resSerialNo" style="color:var(--accent-blue);">--</div>
          </div>
          <div class="product-item">
            <div class="product-label">Product Name</div>
            <div class="product-val" id="resProdName">--</div>
          </div>
          <div class="product-item">
            <div class="product-label">Brand / Manufacturer</div>
            <div class="product-val" id="resBrandName">--</div>
          </div>
          <div class="product-item">
            <div class="product-label">Batch No & Expiry</div>
            <div class="product-val" id="resBatchExp">--</div>
          </div>
          <div class="product-item">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="product-label" style="margin:0;">Total Scan Count</span>
              <button type="button" class="btn-outline" style="padding:1px 6px; font-size:0.68rem;" onclick="resetCurrentProductScans()">🔄 Reset to 0</button>
            </div>
            <div class="product-val" id="resScanCount" style="color:var(--accent-purple); font-size:1.15rem; margin-top:2px;">--</div>
          </div>
          <div class="product-item">
            <div class="product-label">First Scanned Timestamp</div>
            <div class="product-val" id="resFirstScan" style="font-size:0.78rem;">--</div>
          </div>
        </div>
      </div>
      
      <!-- PHYSICAL METRICS -->
      <div class="metric-grid">
        <div class="metric-card">
          <div class="metric-label">Peak NCC (Seed Match)</div>
          <div class="metric-value" id="valNCC">--</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Print Acuity Slope</div>
          <div class="metric-value" id="valGate">--</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Reprint Risk</div>
          <div class="metric-value" id="valReprintRisk">--</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Micro-Void Count</div>
          <div class="metric-value" id="valVoidCount">--</div>
        </div>
      </div>

      <!-- MICRO-DOT MORPHOLOGY METRICS (PHOTOCOPY DISCRIMINATION) -->
      <div class="metric-grid" style="margin-top:6px;">
        <div class="metric-card">
          <div class="metric-label">Dot P/A Ratio</div>
          <div class="metric-value" id="valPARatio">--</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Toner Density</div>
          <div class="metric-value" id="valDensity">--</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Dot Clump Ratio</div>
          <div class="metric-value" id="valClump">--</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Laplacian Sharpness</div>
          <div class="metric-value" id="valLap">--</div>
        </div>
      </div>
      
      <!-- COMPARISON ZOOM CARD -->
      <div class="comparison-box">
        <label>Microscopic Micro-Dot Degradation & Heatmap</label>
        <img id="comparisonImg" class="comparison-img" alt="Comparison Card">
      </div>
    </div>
    
  </div>

</div>

<script>
let currentMasterQR = null;
let currentCameraStream = null;
let currentFacingMode = 'environment';

function setTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tabSuite').style.display = 'none';
  document.getElementById('tabCamera').style.display = 'none';
  document.getElementById('tabUpload').style.display = 'none';
  document.getElementById('tabBlur').style.display = 'none';
  document.getElementById('tabInventory').style.display = 'none';

  if (tab !== 'camera' && currentCameraStream) {
    stopCamera();
  }

  if (tab === 'suite') {
    document.querySelectorAll('.tab-btn')[0].classList.add('active');
    document.getElementById('tabSuite').style.display = 'block';
  } else if (tab === 'camera') {
    document.querySelectorAll('.tab-btn')[1].classList.add('active');
    document.getElementById('tabCamera').style.display = 'block';
    startCamera();
  } else if (tab === 'upload') {
    document.querySelectorAll('.tab-btn')[2].classList.add('active');
    document.getElementById('tabUpload').style.display = 'block';
  } else if (tab === 'blur') {
    document.querySelectorAll('.tab-btn')[3].classList.add('active');
    document.getElementById('tabBlur').style.display = 'block';
  } else if (tab === 'inventory') {
    document.querySelectorAll('.tab-btn')[4].classList.add('active');
    document.getElementById('tabInventory').style.display = 'block';
    loadInventory();
  }
}

let allProductsCache = [];

function syncPayload() {
  const serial = document.getElementById('serialNo').value.trim();
  const batch = document.getElementById('batchNo').value.trim();
  document.getElementById('qrPayload').value = `https://brand-auth.com/verify?id=${encodeURIComponent(serial)}&batch=${encodeURIComponent(batch)}`;
  updateActiveBadges();
}

function updateActiveBadges() {
  const serial = document.getElementById('serialNo').value.trim();
  const prodName = document.getElementById('prodName').value.trim();
  const badgeEl = document.getElementById('activeSerialBadge');
  const nameEl = document.getElementById('activeNameBadge');
  if (badgeEl) badgeEl.textContent = serial;
  if (nameEl) nameEl.textContent = prodName;
}

function generateNewSerial() {
  const num = Math.floor(100 + Math.random() * 900);
  document.getElementById('serialNo').value = `PROD-${num}`;
  syncPayload();
  generateQR();
}

function updateBlurLabel(val) {
  document.getElementById('blurLabel').textContent = parseFloat(val).toFixed(1);
}

async function generateQR() {
  syncPayload();
  const serial = document.getElementById('serialNo').value.trim();
  const payload = document.getElementById('qrPayload').value.trim();
  const prodName = document.getElementById('prodName').value.trim();
  const brandName = document.getElementById('brandName').value.trim();
  const batchNo = document.getElementById('batchNo').value.trim();
  const expDate = document.getElementById('expDate').value.trim();
  const mrp = document.getElementById('mrp').value.trim();
  const ratio = parseFloat(document.getElementById('cdpRatio').value);
  const box = parseInt(document.getElementById('boxSize').value);
  
  const res = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      serial_no: serial, 
      payload: payload, 
      product_name: prodName,
      brand_name: brandName,
      batch_no: batchNo,
      exp_date: expDate,
      mrp: mrp,
      cdp_ratio: ratio, 
      box_size: box 
    })
  });
  
  const data = await res.json();
  if (data.status === 'SUCCESS') {
    currentMasterQR = data.qr_image;
    document.getElementById('qrImage').src = data.qr_image;
    document.getElementById('qrImage').style.display = 'block';
    document.getElementById('genPlaceholder').style.display = 'none';
    
    const dl = document.getElementById('downloadLink');
    dl.href = `/api/download?serial=${encodeURIComponent(serial)}&payload=${encodeURIComponent(payload)}&box_size=${box}&cdp_ratio=${ratio}`;
    dl.download = `AntiCounterfeit_QR_600DPI_${serial}.png`;
    dl.style.display = 'inline-block';
    
    const metaBadge = document.getElementById('qrMetaBadge');
    if (metaBadge && data.width && data.height) {
      const cmW = ((data.width / 600) * 2.54).toFixed(2);
      const cmH = ((data.height / 600) * 2.54).toFixed(2);
      document.getElementById('qrDimensions').textContent = `${data.width} × ${data.height} px`;
      document.getElementById('qrPhysicalSize').textContent = `${cmW} × ${cmH} cm (~${(cmW/2.54).toFixed(2)} in)`;
      metaBadge.style.display = 'block';
    }
    
    updateActiveBadges();
  }
}

async function runSim(type) {
  document.getElementById('loader').style.display = 'block';
  document.getElementById('resultSection').style.display = 'none';
  
  syncPayload();
  const serial = document.getElementById('serialNo').value.trim();
  const payload = document.getElementById('qrPayload').value.trim();
  
  const res = await fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: type, serial_no: serial, payload: payload })
  });
  
  const data = await res.json();
  document.getElementById('loader').style.display = 'none';
  renderResult(data);
}

async function runCustomBlur() {
  const sigma = parseFloat(document.getElementById('blurSlider').value);
  document.getElementById('loader').style.display = 'block';
  document.getElementById('resultSection').style.display = 'none';
  
  syncPayload();
  const serial = document.getElementById('serialNo').value.trim();
  const payload = document.getElementById('qrPayload').value.trim();
  
  const res = await fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: 'custom_blur', sigma: sigma, serial_no: serial, payload: payload })
  });
  
  const data = await res.json();
  document.getElementById('loader').style.display = 'none';
  renderResult(data);
}

async function startCamera() {
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert("Live Camera API is not supported in this browser. Please use 'Take High-Res Photo' below.");
      return;
    }
    if (currentCameraStream) {
      stopCamera();
    }
    const constraints = {
      video: {
        facingMode: currentFacingMode,
        width: { ideal: 1920 },
        height: { ideal: 1080 }
      }
    };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    currentCameraStream = stream;
    const video = document.getElementById('cameraVideo');
    video.srcObject = stream;
    video.style.display = 'block';
    await video.play();

    document.getElementById('cameraPlaceholder').style.display = 'none';
    document.getElementById('cameraViewfinder').style.display = 'block';
    document.getElementById('btnStartCam').style.display = 'none';
    document.getElementById('btnSnapCam').style.display = 'flex';
    document.getElementById('btnSwitchCam').style.display = 'flex';
    document.getElementById('btnStopCam').style.display = 'flex';
  } catch (err) {
    console.error("Camera access error:", err);
    document.getElementById('cameraPlaceholder').innerHTML = `
      <div style="font-size:2rem; margin-bottom:6px;">⚠️</div>
      <div style="font-size:0.9rem; font-weight:600; color:#ef4444; margin-bottom:4px;">Camera Permission or Context Needed</div>
      <div style="font-size:0.78rem; color:var(--text-muted);">Browser blocked live video (${err.name || 'Permission'}).<br>Please tap the <b>Take High-Res Photo</b> button below!</div>
    `;
    document.getElementById('btnStartCam').style.display = 'flex';
    document.getElementById('btnSnapCam').style.display = 'none';
    document.getElementById('btnSwitchCam').style.display = 'none';
    document.getElementById('btnStopCam').style.display = 'none';
  }
}

function stopCamera() {
  if (currentCameraStream) {
    currentCameraStream.getTracks().forEach(track => track.stop());
    currentCameraStream = null;
  }
  const video = document.getElementById('cameraVideo');
  if (video) {
    video.srcObject = null;
    video.style.display = 'none';
  }
  document.getElementById('cameraPlaceholder').style.display = 'block';
  document.getElementById('cameraViewfinder').style.display = 'none';
  document.getElementById('btnStartCam').style.display = 'flex';
  document.getElementById('btnSnapCam').style.display = 'none';
  document.getElementById('btnSwitchCam').style.display = 'none';
  document.getElementById('btnStopCam').style.display = 'none';
}

function switchCamera() {
  currentFacingMode = (currentFacingMode === 'environment') ? 'user' : 'environment';
  startCamera();
}

function captureCameraFrame() {
  const video = document.getElementById('cameraVideo');
  if (!video || !video.videoWidth) {
    alert("Camera stream is not ready. Please wait a moment.");
    return;
  }
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL('image/png');
  verifyBase64Image(dataUrl);
}

function openNativeCamera() {
  document.getElementById('nativeCameraInput').click();
}

async function verifyBase64Image(b64) {
  document.getElementById('loader').style.display = 'block';
  document.getElementById('resultSection').style.display = 'none';
  try {
    const res = await fetch('/api/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_b64: b64 })
    });
    const data = await res.json();
    document.getElementById('loader').style.display = 'none';
    renderResult(data);
  } catch (err) {
    document.getElementById('loader').style.display = 'none';
    alert("Verification request failed: " + err);
  }
}

async function uploadImage(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function() {
    verifyBase64Image(reader.result);
  };
  reader.readAsDataURL(file);
}

async function loadInventory() {
  const res = await fetch('/api/products');
  const data = await res.json();
  allProductsCache = data;
  const tbody = document.getElementById('inventoryBody');
  tbody.innerHTML = '';
  
  data.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><b>${p.serial_no}</b></td>
      <td>${p.product_name}</td>
      <td>${p.batch_no}</td>
      <td><span style="color:var(--accent-purple); font-weight:bold;">${p.scan_count}</span></td>
      <td>
        <button class="btn-primary" style="padding:2px 8px; font-size:0.72rem; margin-right:4px;" onclick="loadProductIntoForm('${p.serial_no}')">Load & Test</button>
        <button class="btn-outline" style="padding:2px 8px; font-size:0.72rem;" onclick="resetScan('${p.serial_no}')">Reset</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function loadProductIntoForm(serial) {
  const p = allProductsCache.find(x => x.serial_no === serial);
  if (!p) return;
  document.getElementById('serialNo').value = p.serial_no;
  document.getElementById('prodName').value = p.product_name;
  document.getElementById('brandName').value = p.brand_name || '';
  document.getElementById('batchNo').value = p.batch_no || '';
  document.getElementById('expDate').value = p.exp_date || '';
  document.getElementById('mrp').value = p.mrp || '';
  syncPayload();
  generateQR();
  setTab('suite');
}

async function resetScan(serial) {
  await fetch('/api/reset-scans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ serial_no: serial })
  });
  loadInventory();
}

let lastVerifiedSerial = null;

async function resetCurrentProductScans() {
  if (!lastVerifiedSerial) return;
  await resetScan(lastVerifiedSerial);
  document.getElementById('resScanCount').textContent = '0 (Reset)';
  const alertEl = document.getElementById('cloneAlertBanner');
  alertEl.style.display = 'flex';
  alertEl.className = 'alert-banner alert-success';
  alertEl.innerHTML = `✅ <b>Scan count reset to 0 for ${lastVerifiedSerial}! Next scan will be verified as 1st-Time Scan.</b>`;
}

function renderResult(data) {
  document.getElementById('resultSection').style.display = 'block';
  
  // Status message
  const statusEl = document.getElementById('statusMessageBar');
  statusEl.textContent = data.message || data.verdict;
  if (data.status === 'GENUINE') {
    statusEl.style.borderLeftColor = 'var(--success)';
  } else if (data.status === 'COUNTERFEIT') {
    statusEl.style.borderLeftColor = 'var(--danger)';
  } else if (data.status === 'RECAPTURE_REQUIRED') {
    statusEl.style.borderLeftColor = 'var(--accent-blue)';
  } else {
    statusEl.style.borderLeftColor = 'var(--warning)';
  }

  // Guidance Banner
  const guidanceEl = document.getElementById('guidanceBanner');
  if (data.guidance) {
    guidanceEl.style.display = 'block';
    guidanceEl.innerHTML = `💡 <b>Actionable Guidance:</b> ${data.guidance}`;
  } else {
    guidanceEl.style.display = 'none';
  }

  // Verdict Badge
  const badge = document.getElementById('verdictBadge');
  badge.textContent = data.verdict;
  
  if (data.status === 'GENUINE') {
    badge.className = 'badge badge-genuine';
  } else if (data.status === 'COUNTERFEIT') {
    badge.className = 'badge badge-counterfeit';
  } else if (data.status === 'RECAPTURE_REQUIRED') {
    badge.className = 'badge badge-recapture';
  } else if (data.status === 'UNKNOWN' || data.status === 'UNREGISTERED') {
    badge.className = 'badge badge-unknown';
  } else if (data.status === 'BLACKLISTED') {
    badge.className = 'badge badge-blacklisted';
  } else {
    badge.className = 'badge badge-suspicious';
  }
  
  document.getElementById('authScore').textContent = (data.authenticity_score !== undefined ? data.authenticity_score : 0) + '%';
  
  // Product Info
  const p = data.product_info || {};
  lastVerifiedSerial = data.serial_number || p.serial_no;
  document.getElementById('resSerialNo').textContent = lastVerifiedSerial || 'N/A';
  document.getElementById('resProdName').textContent = p.product_name || 'N/A';
  document.getElementById('resBrandName').textContent = p.brand_name || 'N/A';
  document.getElementById('resBatchExp').textContent = (p.batch_no || 'N/A') + ' | ' + (p.exp_date || '') + ' (' + (p.mrp || '') + ')';
  document.getElementById('resScanCount').textContent = p.scan_count || 1;
  document.getElementById('resFirstScan').textContent = p.first_scanned_at || 'Just now';
  
  const regStatusEl = document.getElementById('prodRegistryStatus');
  if (p.is_registered) {
    regStatusEl.innerHTML = '<span style="color:var(--success);">✅ Official Registered Product</span>';
  } else {
    regStatusEl.innerHTML = '<span style="color:var(--danger);">❌ Unregistered / Unknown Product</span>';
  }
  
  // Clone / Multi-Scan Alert
  const alertEl = document.getElementById('cloneAlertBanner');
  if (p.clone_alert) {
    alertEl.style.display = 'flex';
    alertEl.className = 'alert-banner alert-warning';
    alertEl.innerHTML = `⚠️ <b>${p.clone_message}</b>`;
  } else if (!p.is_registered) {
    alertEl.style.display = 'flex';
    alertEl.className = 'alert-banner alert-danger';
    alertEl.innerHTML = `🚨 <b>CRITICAL: Serial number is NOT found in official database!</b>`;
  } else {
    alertEl.style.display = 'flex';
    alertEl.className = 'alert-banner alert-success';
    alertEl.innerHTML = `🛡️ <b>${p.clone_message}</b>`;
  }
  
  const m = data.metrics || {};
  document.getElementById('valNCC').textContent = m.peak_cross_correlation_ncc !== undefined ? m.peak_cross_correlation_ncc : (m.peak_ncc !== undefined ? m.peak_ncc : '--');
  document.getElementById('valLap').textContent = m.laplacian_edge_variance !== undefined ? m.laplacian_edge_variance : (m.edge_acutance_laplacian !== undefined ? m.edge_acutance_laplacian : '--');
  document.getElementById('valFFT').textContent = m.fft_high_freq_ratio !== undefined ? m.fft_high_freq_ratio : '--';
  document.getElementById('valGate').textContent = m.finder_edge_slope !== undefined ? m.finder_edge_slope : (m.acutance_gate !== undefined ? m.acutance_gate : '--');
  const riskEl = document.getElementById('valReprintRisk');
  if (riskEl) {
    const rScore = data.reprint_risk_score !== undefined ? data.reprint_risk_score : (m.reprint_risk_score !== undefined ? m.reprint_risk_score : 0);
    riskEl.textContent = rScore + '%';
    riskEl.style.color = (rScore >= 65) ? 'var(--danger)' : 'var(--success)';
  }
  const voidEl = document.getElementById('valVoidCount');
  if (voidEl) {
    voidEl.textContent = m.micro_void_count !== undefined ? m.micro_void_count : '--';
  }
  document.getElementById('valPARatio').textContent = m.dot_morphology_pa_ratio !== undefined ? m.dot_morphology_pa_ratio : '--';
  document.getElementById('valDensity').textContent = m.dot_morphology_density !== undefined ? (m.dot_morphology_density * 100).toFixed(1) + '%' : '--';
  document.getElementById('valClump').textContent = m.dot_morphology_clump_ratio !== undefined ? m.dot_morphology_clump_ratio : '--';

  
  if (data.comparison_card_b64) {
    document.getElementById('comparisonImg').src = data.comparison_card_b64;
  }
}

window.onload = generateQR;
</script>

</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == "/" or parsed_url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed_url.path == "/api/products":
            prods = product_db.list_all_products(limit=50)
            self.send_json(prods)
        elif parsed_url.path == "/api/download":
            query = urllib.parse.parse_qs(parsed_url.query)
            serial = query.get("serial", ["PROD-2026-X8879"])[0]
            payload = query.get("payload", [f"https://brand-auth.com/verify?id={serial}"])[0]
            box_size = int(query.get("box_size", ["12"])[0])
            cdp_ratio = float(query.get("cdp_ratio", ["0.32"])[0])
            
            qr_img, _ = create_anti_counterfeit_qr(
                payload=payload,
                serial_no=serial,
                box_size=box_size,
                cdp_ratio=cdp_ratio
            )
            buf = io.BytesIO()
            qr_img.save(buf, format="PNG", dpi=(600, 600))
            png_bytes = buf.getvalue()
            
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Disposition", f'attachment; filename="AntiCounterfeit_QR_600DPI_{serial}.png"')
            self.send_header("Content-Length", str(len(png_bytes)))
            self.end_headers()
            self.wfile.write(png_bytes)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_len).decode('utf-8')
        data = json.loads(post_data) if post_data else {}
        
        if self.path == "/api/generate":
            serial = data.get("serial_no", "PROD-2026-X8879")
            payload = data.get("payload", f"https://brand-auth.com/verify?id={serial}")
            prod_name = data.get("product_name", "UltraShield Antiviral 500mg")
            brand_name = data.get("brand_name", "Apex Pharma Labs")
            batch_no = data.get("batch_no", "BATCH-09")
            exp_date = data.get("exp_date", "2029-01-14")
            mrp = data.get("mrp", "Rs. 450.00")
            box_size = int(data.get("box_size", 12))
            cdp_ratio = float(data.get("cdp_ratio", 0.32))
            
            # 1. Register in SQLite Product Database
            product_db.register_product(
                serial_no=serial,
                product_name=prod_name,
                brand_name=brand_name,
                batch_no=batch_no,
                exp_date=exp_date,
                mrp=mrp
            )
            
            # 2. Create Anti-Counterfeit Master QR
            qr_img, cdp_img = create_anti_counterfeit_qr(
                payload=payload,
                serial_no=serial,
                box_size=box_size,
                cdp_ratio=cdp_ratio
            )
            
            resp = {
                "status": "SUCCESS",
                "qr_image": pil_to_base64(qr_img),
                "cdp_image": pil_to_base64(cdp_img),
                "width": qr_img.width,
                "height": qr_img.height
            }
            self.send_json(resp)
            
        elif self.path == "/api/simulate":
            sim_type = data.get("type", "genuine")
            serial = data.get("serial_no", "PROD-2026-X8879")
            payload = data.get("payload", f"https://brand-auth.com/verify?id={serial}")
            
            qr_img, _ = create_anti_counterfeit_qr(payload=payload, serial_no=serial)
            
            if sim_type == "genuine":
                sim_img = simulate_genuine_scan(qr_img)
            elif sim_type == "blur_test":
                cv_img = cv2.cvtColor(np.array(qr_img), cv2.COLOR_RGB2BGR)
                blurred = cv2.GaussianBlur(cv_img, (0, 0), 0.8)
                sim_img = Image.fromarray(cv2.cvtColor(blurred, cv2.COLOR_BGR2RGB))
            elif sim_type == "custom_blur":
                sigma = float(data.get("sigma", 0.8))
                cv_img = cv2.cvtColor(np.array(qr_img), cv2.COLOR_RGB2BGR)
                blurred = cv2.GaussianBlur(cv_img, (0, 0), sigma) if sigma > 0 else cv_img
                sim_img = Image.fromarray(cv2.cvtColor(blurred, cv2.COLOR_BGR2RGB))
            elif sim_type == "photocopy":
                cv_img = cv2.cvtColor(np.array(qr_img), cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                scan = cv2.GaussianBlur(gray, (3, 3), 0.8)
                gaussian = cv2.GaussianBlur(scan, (5, 5), 1.5)
                sharpened = cv2.addWeighted(scan, 2.0, gaussian, -1.0, 0)
                stretched = np.clip(np.power(sharpened.astype(np.float32) / 255.0, 1.35) * 255.0, 0, 255).astype(np.uint8)
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                dilated_toner = cv2.dilate(255 - stretched, kernel, iterations=1)
                reprinted = cv2.GaussianBlur(255 - dilated_toner, (3, 3), 0.7)
                phone_capture = cv2.GaussianBlur(reprinted, (3, 3), 0.8)
                sim_img = Image.fromarray(phone_capture).convert("RGB")
            else:
                sim_img = simulate_counterfeit_reprint(qr_img)
                
            res = verify_anti_counterfeit_qr(sim_img, expected_serial=serial)
            
            comp_b64 = None
            if res.get("comparison_image"):
                comp_b64 = pil_to_base64(res["comparison_image"])
                del res["comparison_image"]
                
            res["comparison_card_b64"] = comp_b64
            self.send_json(res)
            
        elif self.path == "/api/verify":
            image_b64 = data.get("image_b64", "")
            if "," in image_b64:
                image_b64 = image_b64.split(",")[1]
            img_bytes = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            
            res = verify_anti_counterfeit_qr(img)
            comp_b64 = None
            if res.get("comparison_image"):
                comp_b64 = pil_to_base64(res["comparison_image"])
                del res["comparison_image"]
                
            res["comparison_card_b64"] = comp_b64
            self.send_json(res)

        elif self.path == "/api/reset-scans":
            serial = data.get("serial_no", "")
            if serial:
                conn = product_db.get_connection()
                conn.execute("UPDATE products SET scan_count = 0, first_scanned_at = NULL, last_scanned_at = NULL WHERE serial_no = ?", (serial,))
                conn.commit()
                conn.close()
            self.send_json({"status": "SUCCESS"})
            
        else:
            self.send_error(404, "Unknown API Endpoint")

    def send_json(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        return

def run_server(port: int = 8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"Anti-Counterfeit QR Web Studio running on:")
    print(f"  Local Desktop: http://localhost:{port}")
    print(f"  Mobile Phone:  http://192.168.29.142:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
