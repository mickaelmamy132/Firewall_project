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
# CONFIG LOGGING (api.log)
# ---------------------------------------------------------
LOG_PATH = os.environ.get(
    "DYNFW_API_LOG",
    "/home/mamy/Desktop/Projet_fin_annee/Firewall_project/api/api.log"
)

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("dynfw_api")

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
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
# BASE DE DONNÉES
# ---------------------------------------------------------
@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY,
                ip TEXT UNIQUE,
                port INTEGER,
                reason TEXT,
                ts INTEGER,
                expires_at INTEGER
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at
            ON blocks(expires_at)
        """)
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
    return [
        {"ip": r[0], "port": r[1], "reason": r[2], "ts": r[3], "expires_at": r[4]}
        for r in rows
    ]

# ---------------------------------------------------------
# AUTHENTIFICATION TOKEN (LOGUÉE)
# ---------------------------------------------------------
def check_token(request: Request):
    token = request.headers.get("Authorization", "")
    client_ip = request.client.host if request.client else "unknown"

    if token != f"Bearer {API_TOKEN}":
        logger.warning(f"AUTH_FAILED from {client_ip}")
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
# ROUTES
# ---------------------------------------------------------
@app.on_event("startup")
def startup():
    init_db()
    im.ensure_chain()
    logger.info("API DynFW démarrée")

@app.post("/block", dependencies=[Depends(check_token)])
def block(r: BlockReq, request: Request):
    ip = str(r.ip)
    src_ip = request.client.host if request.client else "unknown"

    logger.warning(f"BLOCK_REQUEST from {src_ip} target={ip}")

    im.block_ip(ip, port=r.port, comment=r.reason or "dynfw")
    add_db_block(ip, r.reason, r.ttl_seconds, port=r.port)

    return {"status": "blocked", "ip": ip}

@app.post("/unblock", dependencies=[Depends(check_token)])
def unblock(r: UnblockReq, request: Request):
    ip = str(r.ip)
    src_ip = request.client.host if request.client else "unknown"

    logger.info(f"UNBLOCK_REQUEST from {src_ip} target={ip}")

    im.unblock_ip(ip)
    remove_db_block(ip)

    return {"status": "unblocked", "ip": ip}

@app.get("/list", dependencies=[Depends(check_token)])
def list_blocks():
    blocks = get_blocks()
    return {"blocks": blocks, "count": len(blocks)}

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": int(time.time())}

@app.get("/clients", tags=["Network"])
def list_clients():
    """
    Scanner le réseau local avec arp-scan et retourner IP, MAC et Vendor.
    """
    try:
        result = subprocess.run(
            ["sudo", "arp-scan", "--localnet"],
            capture_output=True,
            text=True
        )

        clients = []
        seen_ips = set()

        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                ip, mac, vendor = parts[:3]
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

# ---------------------------------------------------------
# LANCEMENT
# ---------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
