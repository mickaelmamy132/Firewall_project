#!/usr/bin/env python3
# firewall_api.py - API FastAPI pour la gestion du firewall dynamique

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware   # ✅ IMPORT MANQUANT
from pydantic import BaseModel, IPvAnyAddress, Field
import sqlite3
import time
import subprocess
from typing import Optional, List
import ipTables_manager as im
import logging
import os
from contextlib import contextmanager
import re

# ---------------------------------------------------------
# ✅ CONFIG LOGGING
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dynfw_api")

DB_PATH = os.environ.get("DYNFW_DB", "/var/lib/dynfw/dynfw.db")
API_TOKEN = os.environ.get("DYNFW_API_TOKEN", "MyToken")

# ---------------------------------------------------------
# ✅ INITIALISATION FASTAPI
# ---------------------------------------------------------
app = FastAPI(
    title="DynFW API",
    description="API pour la gestion dynamique du firewall de jose celestin",
    version="1.0.0"
)

# ---------------------------------------------------------
# ✅ AJOUT DU CORS (IMPORTANT POUR REACT)
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ou ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# ✅ BASE DE DONNÉES
# ---------------------------------------------------------
class DatabaseError(Exception):
    pass

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS blocks (
                            id INTEGER PRIMARY KEY,
                            ip TEXT UNIQUE,
                            reason TEXT,
                            ts INTEGER,
                            expires_at INTEGER
                         )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_expires_at 
                        ON blocks(expires_at)""")
            conn.commit()
        logger.info("Base de données initialisée")
    except Exception as e:
        logger.error(f"Erreur DB init: {e}")
        raise DatabaseError(f"Erreur DB: {e}")

def add_db_block(ip: str, reason: Optional[str], ttl_seconds: Optional[int]):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            ts = int(time.time())
            expires_at = ts + ttl_seconds if ttl_seconds else None
            c.execute(
                "INSERT OR REPLACE INTO blocks(ip, reason, ts, expires_at) VALUES (?,?,?,?)",
                (ip, reason, ts, expires_at)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Erreur DB add: {e}")
        raise DatabaseError(f"Erreur DB: {e}")

def remove_db_block(ip: str):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM blocks WHERE ip = ?", (ip,))
            conn.commit()
    except Exception as e:
        logger.error(f"Erreur DB remove: {e}")
        raise DatabaseError(f"Erreur DB: {e}")

def get_blocks():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT ip, reason, ts, expires_at FROM blocks ORDER BY ts DESC")
            rows = c.fetchall()
        return [{"ip": r[0], "reason": r[1], "ts": r[2], "expires_at": r[3]} for r in rows]
    except Exception as e:
        logger.error(f"Erreur DB get: {e}")
        return []

# ---------------------------------------------------------
# ✅ AUTHENTIFICATION TOKEN
# ---------------------------------------------------------
def check_token(request: Request):
    token = request.headers.get("Authorization", "")
    if token != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

# ---------------------------------------------------------
# ✅ SCHEMAS
# ---------------------------------------------------------
class BlockReq(BaseModel):
    ip: IPvAnyAddress
    ttl_seconds: Optional[int] = None
    reason: Optional[str] = None

class UnblockReq(BaseModel):
    ip: IPvAnyAddress

# ---------------------------------------------------------
# ✅ ROUTES
# ---------------------------------------------------------
@app.on_event("startup")
def startup():
    init_db()
    im.ensure_chain()
    logger.info("API DynFW démarrée")

class BlockReq(BaseModel):
    ip: IPvAnyAddress
    ttl_seconds: Optional[int] = None
    reason: Optional[str] = None
    port: Optional[int] = None  # ✅ nouveau champ

@app.post("/block", dependencies=[Depends(check_token)])
def block(r: BlockReq):
    ip = str(r.ip)
    im.block_ip(ip, port=r.port, comment=r.reason or "dynfw")
    add_db_block(ip, r.reason, r.ttl_seconds)
    return {"status": "blocked", "ip": ip}

@app.post("/unblock", dependencies=[Depends(check_token)])
def unblock(r: UnblockReq):
    ip = str(r.ip)
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

        lines = result.stdout.split("\n")
        clients = []

        for line in lines:
            # Format : IP \t MAC \t Vendor
            parts = line.split("\t")
            if len(parts) >= 3:
                ip = parts[0].strip()
                mac = parts[1].strip()
                vendor = parts[2].strip()

                # Filtrer les lignes valides (IP au bon format)
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
                    clients.append({
                        "ipAddress": ip,
                        "macAddress": mac,
                        "vendor": vendor
                    })

        return clients

    except Exception as e:
        logger.error(f"Erreur arp-scan: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors du scan réseau")

# ---------------------------------------------------------
# ✅ LANCEMENT UVICORN
# ---------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
