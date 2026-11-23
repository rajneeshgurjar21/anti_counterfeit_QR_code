"""
Anti-Counterfeit QR Code & Product Registry Web Studio
=====================================================
Integrated Dual-Shield Verification:
1. Physical Anti-Counterfeit Verification (CDP Micro-dot Acutance & 2D-FFT)
2. Product Identity & Supply Chain Registry (Product Name, Batch, Expiry, Scan Counter & Clone Detection)

Production-ready for Render deployment (0.0.0.0 binding, dynamic $PORT, WSGI callable, headless safe).
"""

import os
import io
import json
import base64
import tempfile
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import numpy as np
from PIL import Image
import cv2

from cdp_engine import create_anti_counterfeit_qr, generate_cdp_module_with_fiducials
from simulator import simulate_genuine_scan, simulate_counterfeit_reprint
from cdp_verifier import verify_anti_counterfeit_qr, verify_company_qr, robust_detect_and_decode_qr
import product_db
import company_db

def pil_to_base64(img: Image.Image, format="PNG", dpi=(600, 600)) -> str:
    buffered = io.BytesIO()
    img.save(buffered, format=format, dpi=dpi)
    return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode("utf-8")

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Anti-Counterfeit QR & Product Authentication Studio</title>
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
  body { background: var(--bg-dark); color: var(--text-main); min-height: 100vh; padding: 16px 12px; }
  .header { text-align: center; margin-bottom: 18px; }
  .header h1 { font-size: 1.95rem; background: linear-gradient(135deg, #38bdf8, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 4px; }
  .header p { color: var(--text-muted); font-size: 0.92rem; }
  
  .container { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; max-width: 1440px; margin: 0 auto; }
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
  .btn-sm { padding: 5px 10px; font-size: 0.78rem; min-width: auto; }
  .btn-xs { padding: 2px 8px; font-size: 0.72rem; min-width: auto; }

  /* Tab Navigation */
  .tab-buttons { display: flex; gap: 6px; margin-bottom: 14px; border-bottom: 1px solid var(--card-border); padding-bottom: 8px; overflow-x: auto; }
  .tab-btn { background: transparent; border: 1px solid transparent; color: var(--text-muted); padding: 7px 12px; border-radius: 6px; font-size: 0.85rem; cursor: pointer; white-space: nowrap; flex: none; }
  .tab-btn.active { background: #1e293b; color: #fff; border-color: var(--accent-blue); font-weight: 600; }
  
  /* Mobile Scanner Action UI */
  .mobile-scanner-panel { margin-top: 6px; }
  .scan-actions-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
  @media (max-width: 580px) { .scan-actions-grid { grid-template-columns: 1fr; } }

  .action-tile {
    background: linear-gradient(145deg, #0f172a, #1e293b);
    border: 2px solid #334155;
    border-radius: 12px;
    padding: 16px 14px;
    text-align: center;
    cursor: pointer;
    transition: all 0.25s ease;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    user-select: none;
  }
  .action-tile:hover {
    border-color: var(--accent-blue);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(56, 189, 248, 0.2);
  }
  .action-tile.tile-camera {
    background: linear-gradient(145deg, rgba(2, 132, 199, 0.2), rgba(30, 41, 59, 0.9));
    border-color: rgba(56, 189, 248, 0.6);
  }
  .action-tile.tile-camera:hover {
    border-color: #38bdf8;
    box-shadow: 0 8px 25px rgba(56, 189, 248, 0.35);
  }
  .tile-icon { font-size: 2.2rem; line-height: 1; }
  .tile-title { font-size: 1rem; font-weight: 700; color: #fff; }
  .tile-subtitle { font-size: 0.74rem; color: var(--text-muted); line-height: 1.3; }

  /* Drag and Drop Zone */
  .drop-zone {
    border: 2px dashed #334155;
    border-radius: 10px;
    background: rgba(15, 23, 42, 0.6);
    padding: 14px 10px;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.82rem;
    transition: all 0.2s;
    cursor: pointer;
    margin-bottom: 12px;
  }
  .drop-zone.dragover {
    border-color: var(--accent-blue);
    background: rgba(56, 189, 248, 0.1);
    color: #fff;
  }

  /* Live Captured Preview */
  .scanned-preview-container {
    background: #060a14;
    border: 1px solid var(--card-border);
    border-radius: 10px;
    padding: 12px;
    margin-bottom: 14px;
    text-align: center;
    position: relative;
  }
  .scanned-preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 0.8rem;
    color: var(--text-muted);
  }
  .scanned-preview-img {
    max-height: 220px;
    max-width: 100%;
    border-radius: 8px;
    border: 1px solid var(--card-border);
    box-shadow: 0 4px 16px rgba(0,0,0,0.6);
  }

  /* Loading State Card */
  .loading-card {
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid var(--accent-blue);
    border-radius: 10px;
    padding: 20px 16px;
    text-align: center;
    margin: 12px 0;
    box-shadow: 0 0 25px rgba(56, 189, 248, 0.15);
  }
  .spinner-ring {
    width: 42px;
    height: 42px;
    border: 4px solid rgba(56, 189, 248, 0.2);
    border-top: 4px solid var(--accent-blue);
    border-radius: 50%;
    animation: spin 0.75s linear infinite;
    margin: 0 auto 10px auto;
  }
  @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
  .loading-title { font-size: 0.95rem; font-weight: 700; color: #fff; }
  .loading-subtitle { font-size: 0.78rem; color: var(--text-muted); margin-top: 4px; }

  /* Result Verdict Card */
  .result-card {
    border-radius: 12px;
    padding: 18px 16px;
    margin-top: 14px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.6);
    transition: all 0.3s ease;
  }
  .result-card.verdict-genuine {
    background: linear-gradient(145deg, rgba(34, 197, 94, 0.15), rgba(16, 185, 129, 0.05));
    border: 2px solid #22c55e;
    box-shadow: 0 0 25px rgba(34, 197, 94, 0.25);
  }
  .result-card.verdict-counterfeit {
    background: linear-gradient(145deg, rgba(239, 68, 68, 0.2), rgba(185, 28, 28, 0.08));
    border: 2px solid #ef4444;
    box-shadow: 0 0 25px rgba(239, 68, 68, 0.3);
  }
  .result-card.verdict-recapture {
    background: linear-gradient(145deg, rgba(56, 189, 248, 0.15), rgba(30, 41, 59, 0.8));
    border: 2px solid #38bdf8;
    box-shadow: 0 0 25px rgba(56, 189, 248, 0.2);
  }
  .result-card.verdict-unregistered {
    background: linear-gradient(145deg, rgba(245, 158, 11, 0.15), rgba(30, 41, 59, 0.8));
    border: 2px solid #f59e0b;
    box-shadow: 0 0 25px rgba(245, 158, 11, 0.2);
  }

  .verdict-banner-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    padding-bottom: 12px;
    margin-bottom: 12px;
  }
  .verdict-headline { font-size: 1.35rem; font-weight: 800; display: flex; align-items: center; gap: 8px; }
  .verdict-sub { font-size: 0.82rem; margin-top: 3px; }

  .badge { display: inline-block; padding: 4px 10px; border-radius: 20px; font-weight: 700; font-size: 0.88rem; }
  .badge-genuine { background: rgba(34, 197, 94, 0.25); color: #4ade80; border: 1px solid #22c55e; }
  .badge-counterfeit { background: rgba(239, 68, 68, 0.25); color: #f87171; border: 1px solid #ef4444; }
  .badge-recapture { background: rgba(56, 189, 248, 0.25); color: #7dd3fc; border: 1px solid #38bdf8; }
  .badge-unknown { background: rgba(148, 163, 184, 0.25); color: #cbd5e1; border: 1px solid #64748b; }
  .badge-warning { background: rgba(245, 158, 11, 0.25); color: #fbbf24; border: 1px solid #f59e0b; }

  .guidance-box { background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 10px 14px; margin-top: 10px; font-size: 0.85rem; color: #bae6fd; }
  .product-box { background: #070a14; border: 1px solid var(--card-border); border-radius: 8px; padding: 12px; margin-top: 12px; }
  .product-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem; margin-top: 6px; }
  @media (max-width: 580px) { .product-grid { grid-template-columns: 1fr; } }
  .product-item { background: #11192b; border: 1px solid #1a273e; padding: 8px 10px; border-radius: 6px; }
  .product-label { color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; margin-bottom: 2px; }
  .product-val { color: #fff; font-weight: 600; font-size: 0.88rem; word-break: break-all; }
  
  .alert-banner { padding: 10px 14px; border-radius: 8px; margin-top: 10px; font-size: 0.86rem; display: flex; align-items: center; gap: 8px; }
  .alert-warning { background: rgba(245, 158, 11, 0.15); border: 1px solid var(--warning); color: #fbbf24; }
  .alert-success { background: rgba(34, 197, 94, 0.15); border: 1px solid var(--success); color: #4ade80; }
  .alert-danger { background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); color: #f87171; }
  
  .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 12px; }
  @media (max-width: 768px) { .metric-grid { grid-template-columns: repeat(2, 1fr); } }
  .metric-card { background: #070a14; border: 1px solid var(--card-border); border-radius: 6px; padding: 8px; text-align: center; }
  .metric-label { font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 2px; }
  .metric-value { font-size: 1rem; font-weight: 700; color: #fff; }
  
  .comparison-box { margin-top: 14px; text-align: center; }
  .comparison-img { width: 100%; border-radius: 6px; border: 1px solid var(--card-border); margin-top: 6px; }
  
  .preview-area { display: flex; flex-direction: column; align-items: center; justify-content: center; background: #070a14; border: 2px dashed var(--card-border); border-radius: 10px; padding: 14px; min-height: 240px; position: relative; margin-top: 12px; }
  .preview-img { max-width: 100%; max-height: 240px; border-radius: 6px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
  .download-btn { margin-top: 10px; padding: 7px 14px; font-size: 0.82rem; background: #23324d; color: #fff; border-radius: 6px; text-decoration: none; cursor: pointer; display: inline-block; }
  .download-btn:hover { background: #33476b; }

  /* Live Stream Camera Section */
  .camera-box { position: relative; width: 100%; background: #060913; border: 1px solid var(--card-border); border-radius: 10px; overflow: hidden; min-height: 240px; display: flex; align-items: center; justify-content: center; }
  #cameraVideo { width: 100%; max-height: 300px; object-fit: cover; display: none; background: #020617; }
  .viewfinder { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 190px; height: 190px; border: 2px dashed rgba(56, 189, 248, 0.75); border-radius: 12px; pointer-events: none; box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5); }
  .viewfinder::before { content: ""; position: absolute; inset: -3px; border: 3px solid var(--accent-blue); border-radius: 14px; clip-path: polygon(0 0, 26% 0, 26% 100%, 0 100%, 0 0, 100% 0, 100% 26%, 74% 26%, 74% 0, 100% 0, 100% 100%, 74% 100%, 74% 74%, 100% 74%, 100% 100%, 0 100%, 0 74%, 26% 74%, 26% 100%, 0 100%); }
  .scan-laser { position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, #38bdf8, transparent); box-shadow: 0 0 8px #38bdf8; animation: scanAnim 2.2s ease-in-out infinite alternate; }
  @keyframes scanAnim { 0% { top: 0%; opacity: 0.3; } 50% { opacity: 1; } 100% { top: 100%; opacity: 0.3; } }

  .cloud-pill { display: inline-flex; align-items: center; gap: 6px; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); padding: 5px 12px; border-radius: 20px; font-size: 0.76rem; color: var(--accent-blue); margin-top: 6px; }
  .inventory-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 10px; }
  .inventory-table th, .inventory-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--card-border); }
  .inventory-table th { background: #080d1a; color: var(--accent-blue); text-transform: uppercase; font-size: 0.72rem; }
  .inventory-table tr:hover { background: #162035; }
  .slider-box { background: #070a14; border: 1px solid var(--card-border); border-radius: 8px; padding: 12px; margin-top: 10px; }
  .slider-row { display: flex; align-items: center; gap: 10px; margin-top: 6px; }
  .slider-val { font-weight: bold; color: var(--accent-blue); min-width: 45px; font-size: 1rem; }
</style>
</head>
<body>

<div class="header">
  <h1>Anti-Counterfeit QR & Product Authentication Studio</h1>
  <p>Dual-Shield Authentication: Physical Micro-Dot CDP Acutance + Official Cloud Registry</p>
  <div class="cloud-pill" id="cloudStatusBadge">🔒 Render HTTPS Cloud Verified &bull; 📱 Mobile Camera Direct Scan Ready</div>
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
        <button type="button" class="btn-outline btn-xs" onclick="generateNewSerial()">🎲 New Unique Serial</button>
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

  <!-- RIGHT: REAL-TIME VERIFIER WITH CAMERA SCAN -->
  <div class="card">
    <div class="card-title">
      <span>2. Real-Time Physical & Digital Verification</span>
      <span style="font-size:0.75rem; color:var(--text-muted);">Consumer & Inspector Mode</span>
    </div>
    
    <div class="tab-buttons">
      <button class="tab-btn active" onclick="setTab('scan')">📸 Mobile Camera & Upload</button>
      <button class="tab-btn" onclick="setTab('suite')">⚡ 1-Click Test Suite</button>
      <button class="tab-btn" onclick="setTab('company')">🏢 Company Mode</button>
      <button class="tab-btn" onclick="setTab('blur')">🔬 Blur Slider</button>
      <button class="tab-btn" onclick="setTab('inventory')">📋 Database Registry</button>
    </div>

    <!-- TAB 1: MOBILE CAMERA & UPLOAD (DEFAULT ACTIVE) -->
    <div id="tabScan" class="mobile-scanner-panel">
      
      <!-- Primary Actions Grid -->
      <div class="scan-actions-grid">
        <!-- Direct Mobile Rear Camera Capture -->
        <div class="action-tile tile-camera" onclick="triggerMobileCamera()">
          <div class="tile-icon">📷</div>
          <div class="tile-title">Open Camera & Scan QR</div>
          <div class="tile-subtitle">Direct mobile rear camera capture with autofocus & macro focus</div>
        </div>

        <!-- Desktop File Upload / Gallery -->
        <div class="action-tile" onclick="triggerFileUpload()">
          <div class="tile-icon">📁</div>
          <div class="tile-title">Upload Image / Gallery</div>
          <div class="tile-subtitle">Select photo from files or gallery, or drag and drop below</div>
        </div>
      </div>

      <!-- Hidden Input Elements -->
      <!-- capture="environment" invokes rear camera on mobile phones reliably over HTTPS -->
      <input type="file" id="mobileCameraInput" accept="image/*" capture="environment" style="display:none;" onchange="handleImageInput(event)">
      <input type="file" id="desktopFileInput" accept="image/*" style="display:none;" onchange="handleImageInput(event)">

      <!-- Drag & Drop Zone -->
      <div class="drop-zone" id="dropZone" onclick="triggerFileUpload()">
        <span>📥 <b>Drag and drop QR image</b> here, click to browse, or paste screenshot (Ctrl+V)</span>
      </div>

      <!-- Optional Live Viewfinder Stream Toggle -->
      <div style="margin-bottom: 12px; text-align: center;">
        <button type="button" class="btn-outline btn-sm" id="btnToggleLiveView" onclick="toggleLiveViewfinder()">
          📹 Open Live Stream Viewfinder
        </button>
      </div>

      <!-- Live Stream Viewfinder (Hidden by default) -->
      <div id="liveStreamContainer" style="display:none; margin-bottom: 12px;">
        <div class="camera-box">
          <video id="cameraVideo" autoplay playsinline muted></video>
          <div id="cameraViewfinder" class="viewfinder" style="display:none;">
            <div class="scan-laser"></div>
          </div>
          <div id="cameraPlaceholder" style="padding: 24px 16px; text-align: center; color: var(--text-muted);">
            <div style="font-size: 2rem; margin-bottom: 6px;">📷</div>
            <div style="font-size: 0.9rem; font-weight: 600; color: #fff;">Live Streaming Viewfinder</div>
            <div style="font-size: 0.75rem; margin-top: 4px;">Click <b>Start Streaming</b> below</div>
          </div>
        </div>
        <div style="display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap;">
          <button id="btnStartCam" class="btn-primary btn-sm" onclick="startCamera()">▶️ Start Streaming</button>
          <button id="btnSnapCam" class="btn-success btn-sm" style="display:none;" onclick="captureCameraFrame()">⚡ Snap & Verify</button>
          <button id="btnSwitchCam" class="btn-outline btn-sm" style="display:none; flex:0 0 auto;" onclick="switchCamera()">🔄 Flip Lens</button>
          <button id="btnStopCam" class="btn-danger btn-sm" style="display:none; flex:0 0 auto;" onclick="stopCamera()">⏹️ Stop</button>
        </div>
      </div>

      <!-- Scanned Image Preview -->
      <div id="previewContainer" class="scanned-preview-container" style="display:none;">
        <div class="scanned-preview-header">
          <span>Captured / Selected Image Preview:</span>
          <button class="btn-outline btn-xs" onclick="clearPreview()">✕ Retake / Clear</button>
        </div>
        <img id="scannedPreviewImg" class="scanned-preview-img" alt="Captured Image Preview">
        <div id="previewMeta" style="font-size:0.75rem; color:var(--accent-blue); margin-top:6px;"></div>
      </div>

    </div>

    <!-- TAB 2: 1-CLICK TEST SUITE -->
    <div id="tabSuite" style="display:none;">
      <div id="activeProductBanner" style="background:#070d1a; border:1px solid #1e2c45; border-radius:6px; padding:7px 10px; margin-bottom:10px; font-size:0.82rem; display:flex; justify-content:space-between; align-items:center;">
        <span>Active Subject: <b id="activeSerialBadge" style="color:var(--accent-blue);">PROD-2026-X8879</b> (<span id="activeNameBadge">UltraShield Antiviral 500mg</span>)</span>
        <button type="button" class="btn-outline btn-xs" onclick="generateNewSerial()">+ New Serial</button>
      </div>
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;">
        <button class="btn-success" onclick="runSim('genuine')">1. Genuine Scan</button>
        <button class="btn-warning" onclick="runSim('blur_test')">2. Blur Attack</button>
        <button class="btn-danger" onclick="runSim('counterfeit')">3. Reprint Attack</button>
        <button class="btn-danger" style="background:linear-gradient(135deg, #7f1d1d, #991b1b);" onclick="runSim('photocopy')">4. Photocopy Attack</button>
      </div>
    </div>

    <!-- TAB 3: COMPANY MODE -->
    <div id="tabCompany" style="display:none;">
      <div style="background:#0b1329; border:1px solid #1e2c45; border-radius:8px; padding:10px 12px; margin-bottom:12px;">
        <div style="font-size:0.85rem; font-weight:700; color:var(--accent-blue); margin-bottom:4px;">
          🏢 One Common QR Sticker for Every Product
        </div>
        <p style="font-size:0.75rem; color:var(--text-muted); line-height:1.4;">
          Attach the <b>identical QR sticker</b> to thousands or millions of products manufactured by your company. Verified using company-level CDP cryptographic micro-patterns.
        </p>
      </div>

      <div class="form-group">
        <label>Select Registered Company</label>
        <select id="companySelect" onchange="onCompanySelected()">
        </select>
      </div>

      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 12px;">
        <button class="btn-success" onclick="runCompanySim('genuine')">1. Genuine Scan</button>
        <button class="btn-danger" onclick="runCompanySim('counterfeit')">2. Reprint Attack</button>
        <button class="btn-danger" style="background:linear-gradient(135deg, #7f1d1d, #991b1b);" onclick="runCompanySim('photocopy')">3. Photocopy Attack</button>
      </div>

      <div style="display:flex; justify-content:space-between; align-items:center; margin-top:14px; margin-bottom:6px;">
        <span style="font-size:0.82rem; font-weight:600; color:var(--accent-purple);">Register New Company</span>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
        <div class="form-group">
          <label>Company ID (Unique)</label>
          <input type="text" id="coId" value="APEX-PHARMA-2026" placeholder="e.g. APEX-PHARMA-2026">
        </div>
        <div class="form-group">
          <label>Short Code</label>
          <input type="text" id="coCode" value="APEX" placeholder="e.g. APEX">
        </div>
      </div>

      <div class="form-group">
        <label>Company Name</label>
        <input type="text" id="coName" value="Apex Pharma Labs" placeholder="Full legal company name">
      </div>

      <div class="form-group">
        <label>QR Payload (Printed on Sticker)</label>
        <input type="text" id="coPayload" value="https://verify.apexpharma.com/auth?brand=APEX" placeholder="URL or text payload">
      </div>

      <div class="btn-row">
        <button class="btn-primary" onclick="registerCompany()">Register & Generate Company Common QR</button>
      </div>
      
      <div style="display:flex; justify-content:space-between; align-items:center; margin-top:14px;">
        <span style="font-size:0.82rem; color:var(--text-muted); font-weight:600;">Registered Companies & Scans</span>
        <button class="btn-outline btn-xs" onclick="loadCompanies()">Refresh</button>
      </div>
      <div style="max-height: 160px; overflow-y: auto; margin-top:6px;">
        <table class="inventory-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Code</th>
              <th>Scans</th>
              <th>Sticker</th>
            </tr>
          </thead>
          <tbody id="companyTableBody"></tbody>
        </table>
      </div>
    </div>
    
    <!-- TAB 4: BLUR SLIDER ATTACK -->
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
    
    <!-- TAB 5: INVENTORY DATABASE REGISTRY -->
    <div id="tabInventory" style="display:none;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:0.85rem; color:var(--text-muted);">Registered Products in Official Database</span>
        <button class="btn-outline btn-xs" onclick="loadInventory()">Refresh List</button>
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
          <tbody id="inventoryBody"></tbody>
        </table>
      </div>
    </div>
    
    <!-- LOADING STATE CARD -->
    <div id="loadingIndicator" class="loading-card" style="display:none;">
      <div class="spinner-ring"></div>
      <div class="loading-title">Analyzing Physical Anti-Counterfeit Pattern...</div>
      <div class="loading-subtitle">Inspecting micro-dot acutance, MTF sharpness & verifying cryptographic seed against registry</div>
    </div>
    
    <!-- DUAL-SHIELD RESULT CARD (HIGH IMPACT VERDICT) -->
    <div id="resultSection" style="display:none;">
      
      <div id="resultCard" class="result-card verdict-genuine">
        <!-- TOP VERDICT BANNER -->
        <div class="verdict-banner-row">
          <div>
            <div style="font-size:0.72rem; letter-spacing:1px; text-transform:uppercase; color:var(--text-muted); margin-bottom:2px;">Physical Authentication Result</div>
            <div class="verdict-headline" id="verdictHeadline">
              <span id="verdictIcon">🛡️</span>
              <span id="verdictText">GENUINE PRODUCT VERIFIED</span>
            </div>
            <div class="verdict-sub" id="verdictSubText" style="color: #cbd5e1;">Original 1st-generation physical print authenticated</div>
          </div>
          <div style="text-align: right;">
            <div style="font-size:0.72rem; letter-spacing:1px; text-transform:uppercase; color:var(--text-muted);">Confidence Score</div>
            <div id="authScore" style="font-size: 2rem; font-weight:900; color:#fff;">96.3%</div>
            <div id="verdictBadge" class="badge badge-genuine" style="margin-top:2px;">GENUINE</div>
          </div>
        </div>

        <!-- STATUS MESSAGE & GUIDANCE -->
        <div id="statusMessageBar" style="font-size:0.92rem; font-weight:600; margin-bottom:8px; color:#fff; border-left:3px solid var(--accent-blue); padding-left:8px;"></div>
        <div id="guidanceBanner" class="guidance-box" style="display:none;"></div>
        
        <!-- CLONE / DUPLICATE ALERT BANNER -->
        <div id="cloneAlertBanner" class="alert-banner" style="display:none;"></div>
        
        <!-- OFFICIAL PRODUCT / COMPANY REGISTRY CARD -->
        <div class="product-box">
          <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e2c45; padding-bottom:6px; margin-bottom:6px;">
            <span style="font-weight:700; color:var(--accent-blue); font-size:0.88rem;">Official Product Registry Details</span>
            <span id="prodRegistryStatus" style="font-size:0.75rem; font-weight:600;"></span>
          </div>
          <div class="product-grid">
            <div class="product-item">
              <div class="product-label">Decoded Serial Number / ID</div>
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
                <button type="button" class="btn-outline btn-xs" onclick="resetCurrentProductScans()">🔄 Reset to 0</button>
              </div>
              <div class="product-val" id="resScanCount" style="color:var(--accent-purple); font-size:1.1rem; margin-top:2px;">--</div>
            </div>
            <div class="product-item">
              <div class="product-label">First Scanned Timestamp</div>
              <div class="product-val" id="resFirstScan" style="font-size:0.78rem;">--</div>
            </div>
          </div>
        </div>
        
        <!-- FORENSIC PHYSICAL METRICS -->
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
        <div class="comparison-box" id="comparisonBox" style="display:none;">
          <label>Microscopic Micro-Dot Degradation & Heatmap Comparison</label>
          <img id="comparisonImg" class="comparison-img" alt="Comparison Card">
        </div>
      </div>

    </div>
    
  </div>

</div>

<script>
let currentMasterQR = null;
let currentCameraStream = null;
let currentFacingMode = 'environment';
let liveStreamActive = false;
let allProductsCache = [];
let allCompaniesCache = [];
let lastVerifiedSerial = null;

function setTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tabScan').style.display = 'none';
  document.getElementById('tabSuite').style.display = 'none';
  document.getElementById('tabCompany').style.display = 'none';
  document.getElementById('tabBlur').style.display = 'none';
  document.getElementById('tabInventory').style.display = 'none';

  if (tab !== 'scan' && currentCameraStream) {
    stopCamera();
  }

  if (tab === 'scan') {
    document.querySelectorAll('.tab-btn')[0].classList.add('active');
    document.getElementById('tabScan').style.display = 'block';
  } else if (tab === 'suite') {
    document.querySelectorAll('.tab-btn')[1].classList.add('active');
    document.getElementById('tabSuite').style.display = 'block';
  } else if (tab === 'company') {
    document.querySelectorAll('.tab-btn')[2].classList.add('active');
    document.getElementById('tabCompany').style.display = 'block';
    loadCompanies();
  } else if (tab === 'blur') {
    document.querySelectorAll('.tab-btn')[3].classList.add('active');
    document.getElementById('tabBlur').style.display = 'block';
  } else if (tab === 'inventory') {
    document.querySelectorAll('.tab-btn')[4].classList.add('active');
    document.getElementById('tabInventory').style.display = 'block';
    loadInventory();
  }
}

// Mobile Camera & File Triggers
function triggerMobileCamera() {
  const camInput = document.getElementById('mobileCameraInput');
  if (camInput) {
    camInput.value = '';
    camInput.click();
  }
}

function triggerFileUpload() {
  const fileInput = document.getElementById('desktopFileInput');
  if (fileInput) {
    fileInput.value = '';
    fileInput.click();
  }
}

function handleImageInput(e) {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  processSelectedFile(file);
}

function processSelectedFile(file) {
  const reader = new FileReader();
  reader.onload = function(evt) {
    const dataUrl = evt.target.result;
    
    // Display live image preview
    const previewContainer = document.getElementById('previewContainer');
    const previewImg = document.getElementById('scannedPreviewImg');
    const previewMeta = document.getElementById('previewMeta');
    
    if (previewContainer && previewImg) {
      previewImg.src = dataUrl;
      previewContainer.style.display = 'block';
      const sizeKB = (file.size / 1024).toFixed(1);
      previewMeta.textContent = `${file.name || 'Captured Photo'} (${sizeKB} KB) &bull; Ready for verification`;
    }

    // Send for dual-shield verification
    verifyBase64Image(dataUrl);
  };
  reader.readAsDataURL(file);
}

function clearPreview() {
  const previewContainer = document.getElementById('previewContainer');
  const previewImg = document.getElementById('scannedPreviewImg');
  if (previewContainer) previewContainer.style.display = 'none';
  if (previewImg) previewImg.src = '';
  document.getElementById('resultSection').style.display = 'none';
}

// Drag & Drop Handling
const dropZone = document.getElementById('dropZone');
if (dropZone) {
  ['dragenter', 'dragover'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('dragover');
    });
  });
  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const file = dt && dt.files && dt.files[0];
    if (file && file.type.startsWith('image/')) {
      processSelectedFile(file);
    }
  });
}

// Paste Screenshot from Clipboard (Ctrl+V)
window.addEventListener('paste', (e) => {
  const items = e.clipboardData && e.clipboardData.items;
  if (!items) return;
  for (let i = 0; i < items.length; i++) {
    if (items[i].type.indexOf('image') !== -1) {
      const file = items[i].getAsFile();
      if (file) {
        processSelectedFile(file);
        break;
      }
    }
  }
});

// Live Stream Viewfinder Controls
function toggleLiveViewfinder() {
  const container = document.getElementById('liveStreamContainer');
  const btn = document.getElementById('btnToggleLiveView');
  if (container.style.display === 'none') {
    container.style.display = 'block';
    btn.textContent = '❌ Close Live Viewfinder';
    startCamera();
  } else {
    container.style.display = 'none';
    btn.textContent = '📹 Open Live Stream Viewfinder';
    stopCamera();
  }
}

async function startCamera() {
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert("Live Camera stream API is not supported in this browser. Please use 'Open Camera & Scan QR' above.");
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
    document.getElementById('btnSnapCam').style.display = 'inline-flex';
    document.getElementById('btnSwitchCam').style.display = 'inline-flex';
    document.getElementById('btnStopCam').style.display = 'inline-flex';
  } catch (err) {
    console.error("Camera access error:", err);
    document.getElementById('cameraPlaceholder').innerHTML = `
      <div style="font-size:1.8rem; margin-bottom:6px;">⚠️</div>
      <div style="font-size:0.88rem; font-weight:600; color:#ef4444; margin-bottom:4px;">Stream Permission Needed</div>
      <div style="font-size:0.75rem; color:var(--text-muted);">Please tap the <b>Open Camera & Scan QR</b> button above to use your phone's native camera.</div>
    `;
    document.getElementById('btnStartCam').style.display = 'inline-flex';
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
  document.getElementById('btnStartCam').style.display = 'inline-flex';
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
  
  // Show in preview
  const previewContainer = document.getElementById('previewContainer');
  const previewImg = document.getElementById('scannedPreviewImg');
  const previewMeta = document.getElementById('previewMeta');
  if (previewContainer && previewImg) {
    previewImg.src = dataUrl;
    previewContainer.style.display = 'block';
    previewMeta.textContent = `Live Viewfinder Capture (${canvas.width}×${canvas.height}) &bull; Ready for verification`;
  }

  verifyBase64Image(dataUrl);
}

// Verification Network Call
async function verifyBase64Image(b64) {
  document.getElementById('loadingIndicator').style.display = 'block';
  document.getElementById('resultSection').style.display = 'none';
  try {
    const res = await fetch('/api/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_b64: b64 })
    });
    const data = await res.json();
    document.getElementById('loadingIndicator').style.display = 'none';
    renderResult(data);
  } catch (err) {
    document.getElementById('loadingIndicator').style.display = 'none';
    alert("Verification request failed: " + err);
  }
}

// Render Results with High-Impact Badging
function renderResult(data) {
  document.getElementById('resultSection').style.display = 'block';
  const card = document.getElementById('resultCard');
  const headline = document.getElementById('verdictHeadline');
  const icon = document.getElementById('verdictIcon');
  const text = document.getElementById('verdictText');
  const subText = document.getElementById('verdictSubText');
  const badge = document.getElementById('verdictBadge');
  const statusEl = document.getElementById('statusMessageBar');

  // Status message
  statusEl.textContent = data.message || data.verdict;
  
  // High-Impact Visual Distinction
  if (data.status === 'GENUINE') {
    card.className = 'result-card verdict-genuine';
    icon.textContent = '🛡️';
    text.textContent = 'GENUINE ORIGINAL PRODUCT';
    text.style.color = 'var(--success)';
    subText.textContent = 'Original 1st-generation physical print verified by microscopic acutance';
    badge.className = 'badge badge-genuine';
    badge.textContent = 'GENUINE';
    statusEl.style.borderLeftColor = 'var(--success)';
  } else if (data.status === 'COUNTERFEIT') {
    card.className = 'result-card verdict-counterfeit';
    icon.textContent = '⚠️';
    text.textContent = 'COUNTERFEIT / REPRINT DETECTED';
    text.style.color = 'var(--danger)';
    subText.textContent = 'Physical Copy Detection Pattern failed: Acutance loss or reprint toner scatter detected';
    badge.className = 'badge badge-counterfeit';
    badge.textContent = 'COUNTERFEIT';
    statusEl.style.borderLeftColor = 'var(--danger)';
  } else if (data.status === 'RECAPTURE_REQUIRED') {
    card.className = 'result-card verdict-recapture';
    icon.textContent = '📷';
    text.textContent = 'RECAPTURE REQUIRED';
    text.style.color = 'var(--accent-blue)';
    subText.textContent = 'Image blur, low lighting, or reflection detected — please retake in focus';
    badge.className = 'badge badge-recapture';
    badge.textContent = 'RECAPTURE';
    statusEl.style.borderLeftColor = 'var(--accent-blue)';
  } else {
    card.className = 'result-card verdict-unregistered';
    icon.textContent = '❌';
    text.textContent = data.verdict || 'UNREGISTERED PRODUCT';
    text.style.color = 'var(--warning)';
    subText.textContent = 'Serial number or company payload not recognized in official registry';
    badge.className = 'badge badge-warning';
    badge.textContent = data.status || 'UNREGISTERED';
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

  // Score
  const score = (data.authenticity_score !== undefined ? data.authenticity_score : 0);
  document.getElementById('authScore').textContent = score + '%';
  
  // Product / Company Info
  if (data.company_info) {
    const c = data.company_info;
    document.getElementById('resSerialNo').textContent = c.company_id;
    document.getElementById('resProdName').textContent = c.company_name;
    document.getElementById('resBrandName').textContent = c.company_code + ' (Common Sticker for All Products)';
    document.getElementById('resBatchExp').textContent = 'QR Payload: ' + (data.qr_payload || 'N/A');
    document.getElementById('resScanCount').textContent = c.total_scan_count || 1;
    document.getElementById('resFirstScan').textContent = c.registered_at || 'Just now';
    
    const regStatusEl = document.getElementById('prodRegistryStatus');
    regStatusEl.innerHTML = '<span style="color:var(--success);">🏢 Official Registered Company</span>';
    
    const alertEl = document.getElementById('cloneAlertBanner');
    alertEl.style.display = 'flex';
    alertEl.className = 'alert-banner alert-success';
    alertEl.innerHTML = `🛡️ <b>Company Common QR Verified: ${c.company_name} [${c.company_code}] &bull; Total Scans: ${c.total_scan_count}</b>`;
  } else {
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
      alertEl.innerHTML = `🛡️ <b>${p.clone_message || '1st-Time Scan Verified — Package is Genuine'}</b>`;
    }
  }

  // Forensic Metrics
  const m = data.metrics || {};
  const setEl = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = (val !== undefined && val !== null) ? val : '--';
  };
  
  setEl('valNCC', m.peak_cross_correlation_ncc !== undefined ? m.peak_cross_correlation_ncc : m.peak_ncc);
  setEl('valLap', m.laplacian_edge_variance !== undefined ? m.laplacian_edge_variance : m.edge_acutance_laplacian);
  setEl('valGate', m.finder_edge_slope !== undefined ? m.finder_edge_slope : m.acutance_gate);
  
  const riskEl = document.getElementById('valReprintRisk');
  if (riskEl) {
    const rScore = data.reprint_risk_score !== undefined ? data.reprint_risk_score : (m.reprint_risk_score !== undefined ? m.reprint_risk_score : 0);
    riskEl.textContent = rScore + '%';
    riskEl.style.color = (rScore >= 65) ? 'var(--danger)' : 'var(--success)';
  }
  setEl('valVoidCount', m.micro_void_count);
  setEl('valPARatio', m.dot_morphology_pa_ratio);
  setEl('valDensity', m.dot_morphology_density !== undefined ? (m.dot_morphology_density * 100).toFixed(1) + '%' : '--');
  setEl('valClump', m.dot_morphology_clump_ratio);

  // Comparison Image Box
  const compBox = document.getElementById('comparisonBox');
  const compImg = document.getElementById('comparisonImg');
  if (data.comparison_card_b64) {
    compImg.src = data.comparison_card_b64;
    compBox.style.display = 'block';
  } else {
    compBox.style.display = 'none';
  }

  // Scroll smoothly to results on mobile
  if (window.innerWidth < 800) {
    document.getElementById('resultSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// 1-Click Simulations
async function runSim(type) {
  document.getElementById('loadingIndicator').style.display = 'block';
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
  document.getElementById('loadingIndicator').style.display = 'none';
  renderResult(data);
}

async function runCustomBlur() {
  const sigma = parseFloat(document.getElementById('blurSlider').value);
  document.getElementById('loadingIndicator').style.display = 'block';
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
  document.getElementById('loadingIndicator').style.display = 'none';
  renderResult(data);
}

function updateBlurLabel(val) {
  document.getElementById('blurLabel').textContent = parseFloat(val).toFixed(1);
}

// Master QR Registration & Generation
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
  
  try {
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
  } catch (err) {
    console.error("Generate error:", err);
  }
}

// Company Mode Handlers
async function loadCompanies() {
  try {
    const res = await fetch('/api/companies');
    const list = await res.json();
    allCompaniesCache = list;
    const select = document.getElementById('companySelect');
    const tbody = document.getElementById('companyTableBody');
    if (select) select.innerHTML = '';
    if (tbody) tbody.innerHTML = '';

    list.forEach(c => {
      if (select) {
        const opt = document.createElement('option');
        opt.value = c.company_id;
        opt.textContent = `${c.company_name} (${c.company_code}) - ${c.total_scan_count} scans`;
        select.appendChild(opt);
      }
      if (tbody) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${c.company_id}</b></td>
          <td>${c.company_name}</td>
          <td>${c.company_code}</td>
          <td><span style="color:var(--accent-purple); font-weight:bold;">${c.total_scan_count}</span></td>
          <td>
            <a class="download-btn" style="margin:0; padding:2px 8px; font-size:0.7rem;" href="/api/company/download?company_id=${encodeURIComponent(c.company_id)}">600 DPI</a>
          </td>
        `;
        tbody.appendChild(tr);
      }
    });
  } catch (e) {
    console.error('loadCompanies error:', e);
  }
}

function onCompanySelected() {
  const cid = document.getElementById('companySelect').value;
  const co = allCompaniesCache.find(x => x.company_id === cid);
  if (!co) return;
  document.getElementById('coId').value = co.company_id;
  document.getElementById('coName').value = co.company_name;
  document.getElementById('coCode').value = co.company_code;
  document.getElementById('coPayload').value = co.qr_payload;
}

async function registerCompany() {
  const cid = document.getElementById('coId').value.trim();
  const name = document.getElementById('coName').value.trim();
  const code = document.getElementById('coCode').value.trim();
  const payload = document.getElementById('coPayload').value.trim();

  if (!cid || !name || !code || !payload) {
    alert('Please fill in Company ID, Name, Code, and Payload.');
    return;
  }

  document.getElementById('loadingIndicator').style.display = 'block';
  try {
    const res = await fetch('/api/company/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: cid,
        company_name: name,
        company_code: code,
        qr_payload: payload
      })
    });
    const data = await res.json();
    document.getElementById('loadingIndicator').style.display = 'none';

    if (data.status === 'SUCCESS') {
      currentMasterQR = data.qr_image;
      document.getElementById('qrImage').src = data.qr_image;
      document.getElementById('qrImage').style.display = 'block';
      document.getElementById('genPlaceholder').style.display = 'none';

      const dl = document.getElementById('downloadLink');
      dl.href = `/api/company/download?company_id=${encodeURIComponent(cid)}`;
      dl.download = `Company_Common_QR_600DPI_${code}.png`;
      dl.style.display = 'inline-block';

      await loadCompanies();
      alert(`Company ${name} registered successfully! Print this common QR sticker on all products.`);
    } else {
      alert('Registration failed: ' + (data.message || 'Unknown error'));
    }
  } catch (err) {
    document.getElementById('loadingIndicator').style.display = 'none';
    alert('Error: ' + err);
  }
}

async function runCompanySim(type) {
  const cid = document.getElementById('companySelect').value || document.getElementById('coId').value.trim();
  if (!cid) {
    alert('Please select or register a company first.');
    return;
  }
  document.getElementById('loadingIndicator').style.display = 'block';
  document.getElementById('resultSection').style.display = 'none';

  try {
    const res = await fetch('/api/company/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: type, company_id: cid })
    });
    const data = await res.json();
    document.getElementById('loadingIndicator').style.display = 'none';
    renderResult(data);
  } catch (err) {
    document.getElementById('loadingIndicator').style.display = 'none';
    alert('Error running company simulation: ' + err);
  }
}

// Database Registry
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
        <button class="btn-primary btn-xs" style="margin-right:4px;" onclick="loadProductIntoForm('${p.serial_no}')">Load</button>
        <button class="btn-outline btn-xs" onclick="resetScan('${p.serial_no}')">Reset</button>
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
  setTab('scan');
}

async function resetScan(serial) {
  await fetch('/api/reset-scans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ serial_no: serial })
  });
  loadInventory();
}

async function resetCurrentProductScans() {
  if (!lastVerifiedSerial) return;
  await resetScan(lastVerifiedSerial);
  document.getElementById('resScanCount').textContent = '0 (Reset)';
  const alertEl = document.getElementById('cloneAlertBanner');
  alertEl.style.display = 'flex';
  alertEl.className = 'alert-banner alert-success';
  alertEl.innerHTML = `✅ <b>Scan count reset to 0 for ${lastVerifiedSerial}! Next scan will be verified as 1st-Time Scan.</b>`;
}

// Init
window.onload = function() {
  generateQR();
  const host = window.location.host;
  const isHttps = window.location.protocol === 'https:';
  const badge = document.getElementById('cloudStatusBadge');
  if (badge) {
    badge.innerHTML = `${isHttps ? '🔒 HTTPS Secure' : '🌐 Connected'}: <b>${host}</b> &bull; 📱 Mobile Camera Direct Scan Ready`;
  }
};
</script>

</body>
</html>
"""

def handle_verify_image(img_bytes: bytes) -> dict:
    """
    Safely saves uploaded image to a temporary file, executes the dual-shield
    anti-counterfeit verification, and guarantees deletion of the temporary file.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_path = tmp.name
    try:
        tmp.write(img_bytes)
        tmp.flush()
        tmp.close()

        # Load with PIL and OpenCV
        img_pil = Image.open(tmp_path).convert('RGB')
        img_cv = cv2.imread(tmp_path)
        if img_cv is None:
            img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

        # Auto-detect Company QR vs Product QR
        payload, _, _ = robust_detect_and_decode_qr(img_cv)
        co = company_db.get_company_by_payload(payload) if payload else None

        if co:
            res = verify_company_qr(img_pil, save_debug_artifacts=False)
        else:
            res = verify_anti_counterfeit_qr(img_pil, save_debug_artifacts=False)

        comp_b64 = None
        if res.get("comparison_image"):
            comp_b64 = pil_to_base64(res["comparison_image"])
            del res["comparison_image"]

        res["comparison_card_b64"] = comp_b64
        return res
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def dispatch_request(method: str, path: str, query_string: str, body_bytes: bytes):
    """
    Unified router that handles HTTP requests across both stdlib HTTPServer and WSGI/Gunicorn.
    Returns (status_code, headers_list, body_bytes).
    """
    method = method.upper()

    if method == "OPTIONS":
        headers = [
            ("Content-Type", "text/plain"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
        ]
        return 204, headers, b""

    if method == "GET":
        if path in ("/", "/index.html"):
            headers = [("Content-Type", "text/html; charset=utf-8")]
            return 200, headers, HTML_PAGE.encode("utf-8")

        elif path in ("/healthz", "/api/health"):
            headers = [("Content-Type", "application/json")]
            return 200, headers, json.dumps({"status": "healthy"}).encode("utf-8")

        elif path == "/api/products":
            prods = product_db.list_all_products(limit=50)
            headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
            return 200, headers, json.dumps(prods).encode("utf-8")

        elif path == "/api/companies":
            cos = company_db.list_companies()
            headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
            return 200, headers, json.dumps(cos).encode("utf-8")

        elif path == "/api/company/download":
            query = urllib.parse.parse_qs(query_string)
            cid = query.get("company_id", [""])[0]
            co = company_db.get_company(cid) if cid else None
            if not co:
                return 404, [("Content-Type", "text/plain")], b"Company Not Found"

            qr_img, _ = create_anti_counterfeit_qr(
                payload=co["qr_payload"],
                serial_no=co["cdp_seed"],
                box_size=12,
                cdp_ratio=0.32
            )
            buf = io.BytesIO()
            qr_img.save(buf, format="PNG", dpi=(600, 600))
            png_bytes = buf.getvalue()
            headers = [
                ("Content-Type", "image/png"),
                ("Content-Disposition", f'attachment; filename="Company_Common_QR_{co["company_code"]}.png"'),
                ("Content-Length", str(len(png_bytes)))
            ]
            return 200, headers, png_bytes

        elif path == "/api/download":
            query = urllib.parse.parse_qs(query_string)
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
            headers = [
                ("Content-Type", "image/png"),
                ("Content-Disposition", f'attachment; filename="AntiCounterfeit_QR_600DPI_{serial}.png"'),
                ("Content-Length", str(len(png_bytes)))
            ]
            return 200, headers, png_bytes

        else:
            return 404, [("Content-Type", "text/plain")], b"Not Found"

    elif method == "POST":
        data = {}
        if body_bytes:
            try:
                data = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                data = {}

        if path == "/api/generate":
            serial = data.get("serial_no", "PROD-2026-X8879")
            payload = data.get("payload", f"https://brand-auth.com/verify?id={serial}")
            prod_name = data.get("product_name", "UltraShield Antiviral 500mg")
            brand_name = data.get("brand_name", "Apex Pharma Labs")
            batch_no = data.get("batch_no", "BATCH-09")
            exp_date = data.get("exp_date", "2029-01-14")
            mrp = data.get("mrp", "Rs. 450.00")
            box_size = int(data.get("box_size", 12))
            cdp_ratio = float(data.get("cdp_ratio", 0.32))

            product_db.register_product(
                serial_no=serial,
                product_name=prod_name,
                brand_name=brand_name,
                batch_no=batch_no,
                exp_date=exp_date,
                mrp=mrp
            )

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
            headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
            return 200, headers, json.dumps(resp).encode("utf-8")

        elif path == "/api/simulate":
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

            res = verify_anti_counterfeit_qr(sim_img, expected_serial=serial, save_debug_artifacts=False)
            comp_b64 = None
            if res.get("comparison_image"):
                comp_b64 = pil_to_base64(res["comparison_image"])
                del res["comparison_image"]

            res["comparison_card_b64"] = comp_b64
            headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
            return 200, headers, json.dumps(res).encode("utf-8")

        elif path == "/api/company/register":
            cid = data.get("company_id", "").strip()
            name = data.get("company_name", "").strip()
            code = data.get("company_code", "").strip()
            payload = data.get("qr_payload", "").strip()
            email = data.get("contact_email", "").strip()
            notes = data.get("notes", "").strip()
            box_size = int(data.get("box_size", 12))
            cdp_ratio = float(data.get("cdp_ratio", 0.32))

            if not cid or not name or not code or not payload:
                headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
                return 400, headers, json.dumps({"status": "ERROR", "message": "Missing required company fields"}).encode("utf-8")

            co = company_db.register_company(
                company_id=cid,
                company_name=name,
                company_code=code,
                qr_payload=payload,
                contact_email=email,
                notes=notes
            )
            qr_img, cdp_img = create_anti_counterfeit_qr(
                payload=payload,
                serial_no=co["cdp_seed"],
                box_size=box_size,
                cdp_ratio=cdp_ratio
            )
            resp = {
                "status": "SUCCESS",
                "company": co,
                "qr_image": pil_to_base64(qr_img),
                "cdp_image": pil_to_base64(cdp_img),
                "width": qr_img.width,
                "height": qr_img.height
            }
            headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
            return 200, headers, json.dumps(resp).encode("utf-8")

        elif path == "/api/company/simulate":
            sim_type = data.get("type", "genuine")
            cid = data.get("company_id", "APEX-PHARMA-2026")
            co = company_db.get_company(cid)
            if not co:
                headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
                return 404, headers, json.dumps({"status": "ERROR", "message": "Company not found"}).encode("utf-8")

            qr_img, _ = create_anti_counterfeit_qr(payload=co["qr_payload"], serial_no=co["cdp_seed"])
            if sim_type == "genuine":
                sim_img = simulate_genuine_scan(qr_img)
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

            res = verify_company_qr(sim_img, save_debug_artifacts=False)
            comp_b64 = None
            if res.get("comparison_image"):
                comp_b64 = pil_to_base64(res["comparison_image"])
                del res["comparison_image"]
            res["comparison_card_b64"] = comp_b64
            headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
            return 200, headers, json.dumps(res).encode("utf-8")

        elif path == "/api/verify":
            image_b64 = data.get("image_b64", "")
            if "," in image_b64:
                image_b64 = image_b64.split(",")[1]

            if not image_b64:
                headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
                return 400, headers, json.dumps({"status": "ERROR", "message": "No image data provided"}).encode("utf-8")

            img_bytes = base64.b64decode(image_b64)
            res = handle_verify_image(img_bytes)
            headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
            return 200, headers, json.dumps(res).encode("utf-8")

        elif path == "/api/reset-scans":
            serial = data.get("serial_no", "")
            if serial:
                conn = product_db.get_connection()
                conn.execute("UPDATE products SET scan_count = 0, first_scanned_at = NULL, last_scanned_at = NULL WHERE serial_no = ?", (serial,))
                conn.commit()
                conn.close()
            headers = [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")]
            return 200, headers, json.dumps({"status": "SUCCESS"}).encode("utf-8")

        else:
            return 404, [("Content-Type", "text/plain")], b"Unknown API Endpoint"

    return 405, [("Content-Type", "text/plain")], b"Method Not Allowed"


class RequestHandler(BaseHTTPRequestHandler):
    """Native Python HTTP request handler for local execution."""
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        status, headers, body = dispatch_request("GET", parsed.path, parsed.query, b"")
        self.send_response(status)
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len) if content_len > 0 else b""
        status, headers, body = dispatch_request("POST", parsed.path, parsed.query, post_data)
        self.send_response(status)
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        status, headers, body = dispatch_request("OPTIONS", self.path, "", b"")
        self.send_response(status)
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def app(environ, start_response):
    """
    WSGI callable for production deployment via Gunicorn/Uvicorn on Render.
    Entrypoint: web_app:app
    """
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    query = environ.get("QUERY_STRING", "")
    content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
    body = environ["wsgi.input"].read(content_length) if content_length > 0 else b""

    status_code, headers, resp_body = dispatch_request(method, path, query, body)

    status_phrases = {
        200: "200 OK",
        204: "204 No Content",
        400: "400 Bad Request",
        404: "404 Not Found",
        405: "405 Method Not Allowed",
        500: "500 Internal Server Error"
    }
    status_text = status_phrases.get(status_code, f"{status_code} Status")
    start_response(status_text, headers)
    return [resp_body]

# Alias for WSGI servers
application = app


def run_server(host: str = "0.0.0.0", port: int = None):
    if port is None:
        port = int(os.environ.get("PORT", 8080))
    server_address = (host, port)
    httpd = HTTPServer(server_address, RequestHandler)
    print("=" * 66)
    print(f" Anti-Counterfeit QR & CDP Authentication Web Studio")
    print(f" Server listening on: http://{host}:{port}")
    print(f" Ready for Render Cloud Deployment (PORT={port})")
    print("=" * 66)
    httpd.serve_forever()


if __name__ == "__main__":
    import sys
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8080))
    run_server(host="0.0.0.0", port=port)
