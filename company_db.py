"""
Company Registry — Multi-Company QR Identity Management
========================================================
Manages company-level QR code identities.

Business Rule:
  ONE company  →  ONE common QR code  →  ONE common CDP master pattern.
  Every physical product of that company carries the SAME sticker.

This module is completely additive — it adds two new tables
(companies, company_scan_logs) to the existing products.db file.
The existing 'products' and 'scan_logs' tables are NEVER touched.

New tables
──────────
companies          — master registry of company QR identities.
company_scan_logs  — per-scan audit trail keyed to company_id.
"""

import os
import sqlite3
import datetime
import hashlib
import secrets
from typing import Optional, Dict, Any, List

# Shared database file — same as product_db.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "products.db"))

# ─────────────────────────────────────────────────────────────────
#  Utility helpers
# ─────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """Returns a live SQLite connection with Row dict-access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _cdp_seed_for(company_id: str) -> str:
    """
    Deterministic CDP seed from company_id.
    Adding the prefix 'COMPANY::' ensures the seed namespace cannot
    collide with existing product serial numbers.
    """
    return f"COMPANY::{company_id}"


# ─────────────────────────────────────────────────────────────────
#  Schema initialisation
# ─────────────────────────────────────────────────────────────────

def init_company_tables() -> None:
    """
    Creates the two new tables if they don't exist.
    Safe to call on every startup — uses CREATE IF NOT EXISTS.
    """
    conn = get_connection()
    cur = conn.cursor()

    # ── companies ────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        company_id          TEXT PRIMARY KEY,
        company_name        TEXT NOT NULL,
        company_code        TEXT NOT NULL UNIQUE,
        contact_email       TEXT DEFAULT '',
        qr_payload          TEXT NOT NULL,
        qr_image_path       TEXT DEFAULT '',
        cdp_image_path      TEXT DEFAULT '',
        cdp_seed            TEXT NOT NULL,
        status              TEXT DEFAULT 'ACTIVE',
        total_scan_count    INTEGER DEFAULT 0,
        first_scanned_at    TEXT DEFAULT '',
        last_scanned_at     TEXT DEFAULT '',
        registered_at       TEXT NOT NULL,
        notes               TEXT DEFAULT ''
    );
    """)

    # ── company_scan_logs ────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS company_scan_logs (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id          TEXT NOT NULL,
        scanned_at          TEXT NOT NULL,
        physical_verdict    TEXT,
        authenticity_score  REAL,
        image_quality_score REAL,
        reprint_risk_score  REAL,
        cdp_score           REAL,
        scan_number         INTEGER,
        note                TEXT DEFAULT ''
    );
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────
#  Company registration
# ─────────────────────────────────────────────────────────────────

def register_company(
    company_id: str,
    company_name: str,
    company_code: str,
    qr_payload: str,
    contact_email: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    """
    Registers a new company and assigns it a deterministic CDP seed.

    The CDP seed is derived exclusively from company_id so the same
    digital master can always be regenerated without storing any image.

    Returns the full company record dict.
    Raises ValueError if company_code already exists for a different company_id.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Guard: code uniqueness
    cur.execute(
        "SELECT company_id FROM companies WHERE company_code = ? AND company_id != ?",
        (company_code, company_id),
    )
    if cur.fetchone():
        conn.close()
        raise ValueError(
            f"company_code '{company_code}' is already taken by another company."
        )

    seed = _cdp_seed_for(company_id)
    now  = _now()

    cur.execute("""
    INSERT INTO companies
        (company_id, company_name, company_code, contact_email,
         qr_payload, cdp_seed, status, registered_at, notes)
    VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
    ON CONFLICT(company_id) DO UPDATE SET
        company_name   = excluded.company_name,
        company_code   = excluded.company_code,
        contact_email  = excluded.contact_email,
        qr_payload     = excluded.qr_payload,
        notes          = excluded.notes;
    """, (company_id, company_name, company_code,
          contact_email, qr_payload, seed, now, notes))

    conn.commit()

    cur.execute("SELECT * FROM companies WHERE company_id = ?", (company_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row)


def update_company_qr_paths(
    company_id: str,
    qr_image_path: str = "",
    cdp_image_path: str = "",
) -> bool:
    """Stores file paths of the generated QR and CDP images."""
    conn = get_connection()
    conn.execute(
        "UPDATE companies SET qr_image_path=?, cdp_image_path=? WHERE company_id=?",
        (qr_image_path, cdp_image_path, company_id),
    )
    conn.commit()
    conn.close()
    return True


def set_company_status(company_id: str, status: str) -> bool:
    """Sets company status: ACTIVE | REVOKED | SUSPENDED."""
    allowed = {"ACTIVE", "REVOKED", "SUSPENDED"}
    if status not in allowed:
        raise ValueError(f"status must be one of {allowed}")
    conn = get_connection()
    conn.execute(
        "UPDATE companies SET status=? WHERE company_id=?",
        (status, company_id),
    )
    conn.commit()
    conn.close()
    return True


# ─────────────────────────────────────────────────────────────────
#  Company lookup
# ─────────────────────────────────────────────────────────────────

def get_company(company_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a company record by its primary key."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM companies WHERE company_id = ?", (company_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_company_by_code(company_code: str) -> Optional[Dict[str, Any]]:
    """Retrieves a company record by its short code (e.g. 'APXA')."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM companies WHERE company_code = ?", (company_code,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_company_by_payload(qr_payload: str) -> Optional[Dict[str, Any]]:
    """
    Looks up a company by exact QR payload string.
    Called during verification after the QR code is decoded.
    Returns None if no company owns this payload.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM companies WHERE qr_payload = ?", (qr_payload,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_all_companies() -> List[Dict[str, Any]]:
    """Returns all registered companies ordered newest first."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM companies ORDER BY registered_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────
#  Scan audit & clone / duplicate detection
# ─────────────────────────────────────────────────────────────────

_CLONE_WARN_THRESHOLD  = 50     # warn after this many lifetime scans
_CLONE_ALERT_THRESHOLD = 500    # critical alert above this

def record_company_scan(
    company_id: str,
    physical_verdict: str,
    authenticity_score: float,
    image_quality_score: float = 0.0,
    reprint_risk_score: float  = 0.0,
    cdp_score: float           = 0.0,
    note: str                  = "",
) -> Dict[str, Any]:
    """
    Records one verification scan against a company identity.

    Because ONE QR is shared across ALL products, scan_count here
    is the company-wide total — not a per-product clone indicator.

    Duplicate-sticker detection is therefore statistical:
      • Very high scan velocity relative to known production volume
        should be investigated, but a high total count alone is
        expected and normal.

    Returns enriched company record with scan analytics.
    """
    conn = get_connection()
    cur  = conn.cursor()
    now  = _now()

    cur.execute("SELECT * FROM companies WHERE company_id = ?", (company_id,))
    row = cur.fetchone()

    if not row:
        # Unregistered — log and return error record
        cur.execute("""
        INSERT INTO company_scan_logs
            (company_id, scanned_at, physical_verdict, authenticity_score,
             image_quality_score, reprint_risk_score, cdp_score, scan_number, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'UNREGISTERED_COMPANY')
        """, (company_id, now, physical_verdict, authenticity_score,
              image_quality_score, reprint_risk_score, cdp_score))
        conn.commit()
        conn.close()
        return {
            "is_registered": False,
            "company_id": company_id,
            "company_name": "Unregistered Company",
            "status": "UNREGISTERED",
            "total_scan_count": 1,
            "scan_alert": True,
            "scan_alert_message": (
                "CRITICAL: This QR payload does not belong to any registered company!"
            ),
        }

    company = dict(row)
    new_count      = company["total_scan_count"] + 1
    first_scanned  = company["first_scanned_at"] or now
    last_scanned   = now

    cur.execute("""
    UPDATE companies
    SET total_scan_count=?, first_scanned_at=?, last_scanned_at=?
    WHERE company_id=?
    """, (new_count, first_scanned, last_scanned, company_id))

    cur.execute("""
    INSERT INTO company_scan_logs
        (company_id, scanned_at, physical_verdict, authenticity_score,
         image_quality_score, reprint_risk_score, cdp_score, scan_number, note)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (company_id, now, physical_verdict, authenticity_score,
          image_quality_score, reprint_risk_score, cdp_score, new_count, note))

    conn.commit()
    conn.close()

    # ── Duplicate-sticker analytics ──────────────────────────────
    # Since every product legitimately carries this QR, high scan
    # counts are EXPECTED.  We surface informational alerts only at
    # very high volumes so operators can cross-check production data.
    scan_alert = False
    scan_alert_message = (
        f"Company QR authenticated. Lifetime scan #{new_count:,}."
    )

    if new_count >= _CLONE_ALERT_THRESHOLD:
        scan_alert = True
        scan_alert_message = (
            f"INFO: Lifetime scan count has reached {new_count:,}. "
            "Cross-check with production volume to confirm no "
            "unauthorised duplicates are in circulation."
        )
    elif new_count >= _CLONE_WARN_THRESHOLD:
        scan_alert = False   # informational only, not a security alert
        scan_alert_message = (
            f"Company QR verified. {new_count:,} total scans recorded."
        )

    return {
        "is_registered":       True,
        "company_id":          company["company_id"],
        "company_name":        company["company_name"],
        "company_code":        company["company_code"],
        "qr_payload":          company["qr_payload"],
        "cdp_seed":            company["cdp_seed"],
        "status":              company["status"],
        "total_scan_count":    new_count,
        "first_scanned_at":    first_scanned,
        "last_scanned_at":     last_scanned,
        "scan_alert":          scan_alert,
        "scan_alert_message":  scan_alert_message,
    }


def get_company_scan_history(
    company_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """Returns the most recent scan records for a company."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT * FROM company_scan_logs WHERE company_id=? ORDER BY id DESC LIMIT ?",
        (company_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_company_scan_stats(company_id: str) -> Dict[str, Any]:
    """
    Returns aggregated scan statistics for a company.
    Useful for the management dashboard.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
    SELECT
        COUNT(*)                                      AS total_scans,
        SUM(CASE WHEN physical_verdict LIKE '%GENUINE%' THEN 1 ELSE 0 END) AS genuine_count,
        SUM(CASE WHEN physical_verdict LIKE '%COUNTERFEIT%' THEN 1 ELSE 0 END) AS counterfeit_count,
        SUM(CASE WHEN physical_verdict LIKE '%RECAPTURE%' THEN 1 ELSE 0 END) AS recapture_count,
        AVG(authenticity_score)                       AS avg_auth_score,
        AVG(reprint_risk_score)                       AS avg_reprint_risk,
        MIN(scanned_at)                               AS first_scan,
        MAX(scanned_at)                               AS last_scan
    FROM company_scan_logs
    WHERE company_id = ?
    """, (company_id,))

    row = cur.fetchone()
    conn.close()

    if not row:
        return {}

    r = dict(row)
    total = r["total_scans"] or 1
    return {
        "total_scans":       r["total_scans"],
        "genuine_count":     r["genuine_count"],
        "counterfeit_count": r["counterfeit_count"],
        "recapture_count":   r["recapture_count"],
        "genuine_rate_pct":  round((r["genuine_count"] or 0) / total * 100, 1),
        "counterfeit_rate_pct": round((r["counterfeit_count"] or 0) / total * 100, 1),
        "avg_auth_score":    round(r["avg_auth_score"] or 0, 1),
        "avg_reprint_risk":  round(r["avg_reprint_risk"] or 0, 1),
        "first_scan":        r["first_scan"],
        "last_scan":         r["last_scan"],
    }


# ─────────────────────────────────────────────────────────────────
#  Security Limitation Disclosure
# ─────────────────────────────────────────────────────────────────

SECURITY_LIMITATION_NOTICE = """
SECURITY LIMITATION — SHARED QR MODEL
======================================
When ONE common QR sticker is used across ALL products of a company,
the following limitation applies:

  A GENUINE sticker physically removed from one product and placed on
  another product CANNOT be distinguished from an original genuine sticker
  by the CDP verification system alone.

  Reason: The CDP pattern is identical on every sticker. Optical
  verification confirms the sticker is a genuine first-generation print,
  but cannot confirm WHICH product it was originally attached to.

Mitigations in this implementation:
  1. Scan count analytics — high scan velocity relative to production
     volume raises an operational alert (not a security verdict).
  2. Tamper-evident sticker materials — destructive-on-removal labels
     prevent physical transfer without visible damage.
  3. This system is appropriate for brand authentication ("is this a
     genuine Company A product?"), NOT for per-unit serialisation
     ("is this the specific unit I purchased?").

For per-unit serialisation, use unique serial numbers per product unit.
"""


# ─────────────────────────────────────────────────────────────────
#  Auto-initialise tables on import
# ─────────────────────────────────────────────────────────────────

init_company_tables()
