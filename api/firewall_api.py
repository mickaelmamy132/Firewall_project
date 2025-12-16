#!/usr/bin/env python3
# firewall_api.py - API FastAPI pour la gestion du firewall dynamique

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, IPvAnyAddress
import sqlite3
import time
import subprocess
from typing import Optional
import ipTables_manager as im
import logging
import os
from contextlib import contextmanager
import re

# ---------------------------------------------------------
# CONFIG LOGGING
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dynfw_api")

DB_PATH = os.environ.get("DYNFW_DB", "/var/lib/dynfw/dynfw.db")
API_TOKEN = os.environ.get("DYNFW_API_TOKEN", "MyToken")

# ---------------------------------------------------------
# FASTAPI
# ---------------------------------------------------------
app = FastAPI(
    title="DynFW API",
    description="API pour la gestion dynamique du firewall",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# DATABASE HELPERS
# ---------------------------------------------------------
@contextmanager
def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS blocks (
                        id INTEGER PRIMARY KEY,
                        ip TEXT UNIQUE,
                        port INTEGER,
                        reason TEXT,
                        ts INTEGER,
                        expires_at INTEGER
                     )""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_expires_at 
                     ON blocks(expires_at)""")
        conn.commit()
    logger.info("Base de données initialisée")

def add_db_block(ip: str, reason: Optional[str], ttl_seconds: Optional[int], port: Optional[int] = None):
    with get_db_connection() as conn:
        c = conn.cursor()
        ts = int(time.time())
        expires_at = ts + ttl_seconds if ttl_seconds else None
        c.execute(
            "INSERT OR REPLACE INTO blocks(ip, port, reason, ts, expires_at) VALUES (?,?,?,?,?)",
            (ip, port, reason, ts, expires_at)
        )
        conn.commit()

def remove_db_block(ip: str):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM blocks WHERE ip = ?", (ip,))
        conn.commit()

def get_blocks():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT ip, port, reason, ts, expires_at FROM blocks ORDER BY ts DESC")
        rows = c.fetchall()
    return [{"ip": r[0], "port": r[1], "reason": r[2], "ts": r[3], "expires_at": r[4]} for r in rows]

# ---------------------------------------------------------
# AUTH DEPENDENCY
# ---------------------------------------------------------
def check_token(request: Request):
    token = request.headers.get("Authorization")
    if not token or token.replace("Bearer ", "") != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ---------------------------------------------------------
# SCHEMAS
# ---------------------------------------------------------
class BlockReq(BaseModel):
    ip: IPvAnyAddress
    ttl_seconds: Optional[int] = None
    reason: Optional[str] = None
    port: Optional[int] = None

class UnblockReq(BaseModel):
    ip: IPvAnyAddress

# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------
@app.on_event("startup")
def startup():
    init_db()
    im.ensure_chain()
    logger.info("API DynFW démarrée")

# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------
@app.post("/block", dependencies=[Depends(check_token)])
def block(r: BlockReq):
    ip = str(r.ip)
    try:
        im.block_ip(ip, port=r.port, comment=r.reason or "dynfw")
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="iptables failed")
    add_db_block(ip, r.reason, r.ttl_seconds, port=r.port)
    return {"status": "blocked", "ip": ip, "port": r.port, "reason": r.reason}

@app.post("/unblock", dependencies=[Depends(check_token)])
def unblock(r: UnblockReq):
    ip = str(r.ip)
    try:
        im.unblock_ip(ip)
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="iptables failed")
    remove_db_block(ip)
    return {"status": "unblocked", "ip": ip}

@app.get("/list", dependencies=[Depends(check_token)])
def list_blocks():
    return get_blocks()

@app.get("/clients", tags=["Network"])
def list_clients():
    """
    Scanner le réseau local avec arp-scan et retourner IP, MAC et Vendor.
    Évite les doublons.
    """
    try:
        result = subprocess.run(
            ["sudo", "arp-scan", "--localnet"],
            capture_output=True,
            text=True
        )

        clients = []
        seen_ips = set()

        for line in result.stdout.split("\n"):
            parts = line.split("\t")
            if len(parts) >= 3:
                ip = parts[0].strip()
                mac = parts[1].strip()
                vendor = parts[2].strip()
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", ip) and ip not in seen_ips:
                    clients.append({
                        "ipAddress": ip,
                        "macAddress": mac,
                        "vendor": vendor
                    })
                    seen_ips.add(ip)
        return clients
    except Exception as e:
        logger.error(f"Erreur arp-scan: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors du scan réseau")

@app.post("/cleanup", dependencies=[Depends(check_token)])
def cleanup_expired():
    now = int(time.time())
    for r in get_blocks():
        if r["expires_at"] and r["expires_at"] <= now:
            try:
                im.unblock_ip(r["ip"])
            except Exception:
                logger.exception("Failed to remove expired IP %s", r["ip"])
            remove_db_block(r["ip"])
    return {"status": "done"}

# ---------------------------------------------------------
# RUN UVICORN
# ---------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
