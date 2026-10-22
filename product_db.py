"""
Product Registry & Inventory Database (SQLite)
==============================================
Manages product metadata, batch tracking, scan counters, 
and audit logs for anti-counterfeit verification.
"""

import sqlite3
import datetime
from typing import Optional, Dict, Any, List

DB_PATH = "products.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        serial_no TEXT PRIMARY KEY,
        product_name TEXT NOT NULL,
        brand_name TEXT NOT NULL,
        batch_no TEXT NOT NULL,
        mfg_date TEXT,
        exp_date TEXT,
        mrp TEXT,
        status TEXT DEFAULT 'ACTIVE',
        scan_count INTEGER DEFAULT 0,
        first_scanned_at TEXT,
        last_scanned_at TEXT,
        created_at TEXT NOT NULL
    );
    """)
    
    # Scan audit logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scan_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_no TEXT,
        scanned_at TEXT NOT NULL,
        physical_verdict TEXT,
        authenticity_score REAL,
        scan_number INTEGER,
        note TEXT
    );
    """)
    
    # Pre-seed a few sample products if table is empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO products (serial_no, product_name, brand_name, batch_no, mfg_date, exp_date, mrp, status, created_at)
        VALUES 
        ('PROD-2026-X8879', 'UltraShield Antiviral 500mg', 'Apex Pharma Labs', 'BATCH-09', '2026-01-15', '2029-01-14', 'Rs. 450.00', 'ACTIVE', ?),
        ('MED-BATCH-001', 'CardioGuard Extra 20mg', 'Apex Pharma Labs', 'BATCH-01', '2026-02-10', '2028-02-09', 'Rs. 620.00', 'ACTIVE', ?),
        ('BATCH-ALPHA-99', 'SyntheX Synthetic Engine Oil 4L', 'Castrolix Premium', 'ENG-99', '2026-03-01', '2031-03-01', 'Rs. 1,899.00', 'ACTIVE', ?)
        """, (now, now, now))
        
    conn.commit()
    conn.close()

def register_product(
    serial_no: str,
    product_name: str,
    brand_name: str,
    batch_no: str,
    mfg_date: str = "",
    exp_date: str = "",
    mrp: str = ""
) -> bool:
    """Registers or updates a product in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
    INSERT INTO products (serial_no, product_name, brand_name, batch_no, mfg_date, exp_date, mrp, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
    ON CONFLICT(serial_no) DO UPDATE SET
        product_name=excluded.product_name,
        brand_name=excluded.brand_name,
        batch_no=excluded.batch_no,
        mfg_date=excluded.mfg_date,
        exp_date=excluded.exp_date,
        mrp=excluded.mrp;
    """, (serial_no, product_name, brand_name, batch_no, mfg_date, exp_date, mrp, now))
    
    conn.commit()
    conn.close()
    return True

def get_product(serial_no: str) -> Optional[Dict[str, Any]]:
    """Retrieves product details by serial number."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE serial_no = ?", (serial_no,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def record_scan(serial_no: str, physical_verdict: str, authenticity_score: float) -> Dict[str, Any]:
    """
    Records a verification scan:
    - Increments scan counter
    - Detects multi-scan clone attacks
    - Returns updated product record with security assessment
    """
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("SELECT * FROM products WHERE serial_no = ?", (serial_no,))
    row = cursor.fetchone()
    
    if not row:
        # Product not in database (Unknown/Unregistered item)
        cursor.execute("""
        INSERT INTO scan_logs (serial_no, scanned_at, physical_verdict, authenticity_score, scan_number, note)
        VALUES (?, ?, ?, ?, 1, 'UNREGISTERED_SERIAL')
        """, (serial_no, now, physical_verdict, authenticity_score))
        conn.commit()
        conn.close()
        return {
            "is_registered": False,
            "product_name": "Unregistered Product / Unknown Item",
            "brand_name": "Unknown Brand",
            "batch_no": "N/A",
            "mfg_date": "N/A",
            "exp_date": "N/A",
            "mrp": "N/A",
            "scan_count": 1,
            "first_scanned_at": now,
            "db_status": "UNREGISTERED (Not Found in Official Registry)",
            "clone_alert": True,
            "clone_message": "CRITICAL: Serial number does NOT exist in official brand database!"
        }
    
    prod = dict(row)
    new_count = prod["scan_count"] + 1
    first_scan = prod["first_scanned_at"] or now
    
    cursor.execute("""
    UPDATE products 
    SET scan_count = ?, first_scanned_at = ?, last_scanned_at = ?
    WHERE serial_no = ?
    """, (new_count, first_scan, now, serial_no))
    
    # Note on duplicate scan attempts
    note = "NORMAL_FIRST_SCAN" if new_count == 1 else f"REPEAT_SCAN_COUNT_{new_count}"
    cursor.execute("""
    INSERT INTO scan_logs (serial_no, scanned_at, physical_verdict, authenticity_score, scan_number, note)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (serial_no, now, physical_verdict, authenticity_score, new_count, note))
    
    conn.commit()
    conn.close()
    
    # Clone attack detection logic
    clone_alert = False
    clone_message = "Valid Product. First time verified."
    if new_count > 1:
        clone_alert = True
        clone_message = f"WARNING: This QR code has already been scanned {new_count} times! (First scanned: {first_scan}). Possible clone or reused packaging!"

    prod["scan_count"] = new_count
    prod["first_scanned_at"] = first_scan
    prod["last_scanned_at"] = now
    prod["is_registered"] = True
    prod["db_status"] = "REGISTERED & VERIFIED"
    prod["clone_alert"] = clone_alert
    prod["clone_message"] = clone_message
    
    return prod

def list_all_products(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns list of recent registered products."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Initialize on module load
init_db()
