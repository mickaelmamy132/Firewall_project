# app.py
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel, IPvAnyAddress
import sqlite3
import time
import subprocess
from typing import Optional, List
import ipTables_manager as im 
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dynfw_api")

DB_PATH = os.environ.get("DYNFW_DB", "/var/lib/dynfw/dynfw.db")
API_TOKEN = os.environ.get("DYNFW_API_TOKEN", "change_me")  # change in prod

# DB helpers
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS blocks (
                    id INTEGER PRIMARY KEY,
                    ip TEXT UNIQUE,
                    reason TEXT,
                    ts INTEGER,
                    expires_at INTEGER
                 )""")
    conn.commit()
    conn.close()

def add_db_block(ip: str, reason: Optional[str], ttl_seconds: Optional[int]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ts = int(time.time())
    expires_at = ts + ttl_seconds if ttl_seconds else None
    c.execute("INSERT OR REPLACE INTO blocks(ip, reason, ts, expires_at) VALUES (?,?,?,?)",
              (ip, reason, ts, expires_at))
    conn.commit()
    conn.close()

def remove_db_block(ip: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM blocks WHERE ip = ?", (ip,))
    conn.commit()
    conn.close()

def get_blocks():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ip, reason, ts, expires_at FROM blocks")
    rows = c.fetchall()
    conn.close()
    return [{"ip":r[0],"reason":r[1],"ts":r[2],"expires_at":r[3]} for r in rows]

# Auth dependency
def check_token(request: Request):
    token = request.headers.get("Authorization")
    if not token or token.replace("Bearer ", "") != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

class BlockReq(BaseModel):
    ip: IPvAnyAddress
    ttl_seconds: Optional[int] = None
    reason: Optional[str] = None

app = FastAPI(title="DynFW API")

@app.on_event("startup")
def startup():
    init_db()
    im.ensure_chain()

@app.post("/block", dependencies=[Depends(check_token)])
def block(r: BlockReq):
    ip = str(r.ip)
    try:
        im.block_ip(ip, comment=r.reason or "dynfw")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail="iptables failed")
    if r.ttl_seconds:
        add_db_block(ip, r.reason, r.ttl_seconds)
    else:
        add_db_block(ip, r.reason, None)
    return {"status":"blocked","ip":ip}

@app.post("/unblock", dependencies=[Depends(check_token)])
def unblock(r: BlockReq):
    ip = str(r.ip)
    try:
        im.unblock_ip(ip)
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="iptables failed")
    remove_db_block(ip)
    return {"status":"unblocked","ip":ip}

@app.get("/list", dependencies=[Depends(check_token)])
def list_blocks():
    return get_blocks()

@app.post("/cleanup", dependencies=[Depends(check_token)])
def cleanup_expired():
    # remove expired items from iptables and DB
    now = int(time.time())
    rows = get_blocks()
    for r in rows:
        if r["expires_at"] and r["expires_at"] <= now:
            try:
                im.unblock_ip(r["ip"])
            except Exception:
                logger.exception("Failed to remove expired ip %s", r["ip"])
            remove_db_block(r["ip"])
    return {"status":"done"}
