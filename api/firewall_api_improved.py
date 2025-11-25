#!/usr/bin/env python3
# firewall_api.py - API FastAPI pour la gestion du firewall dynamique
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel, IPvAnyAddress, Field
import sqlite3
import time
import subprocess
from typing import Optional, List
import ipTables_manager as im
import logging
import os
from contextlib import contextmanager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dynfw_api")

DB_PATH = os.environ.get("DYNFW_DB", "/var/lib/dynfw/dynfw.db")
API_TOKEN = os.environ.get("DYNFW_API_TOKEN", "change_me")  # À changer en prod

class DatabaseError(Exception):
    """Exception personnalisée pour les erreurs de base de données."""
    pass

# Context manager pour la gestion des connexions DB
@contextmanager
def get_db_connection():
    """Gestionnaire de contexte pour les connexions à la base de données."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialiser la base de données."""
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
            # Créer un index sur expires_at pour les performances
            c.execute("""CREATE INDEX IF NOT EXISTS idx_expires_at 
                        ON blocks(expires_at)""")
            conn.commit()
        logger.info("Base de données initialisée")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
        raise DatabaseError(f"Erreur DB: {e}")

def add_db_block(ip: str, reason: Optional[str], ttl_seconds: Optional[int]) -> None:
    """Ajouter un bloc IP à la base de données."""
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
        logger.debug(f"IP {ip} ajoutée à la DB (TTL: {ttl_seconds}s)")
    except sqlite3.IntegrityError as e:
        logger.warning(f"IP {ip} déjà bloquée: {e}")
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout du bloc: {e}")
        raise DatabaseError(f"Erreur DB: {e}")

def remove_db_block(ip: str) -> None:
    """Supprimer un bloc IP de la base de données."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM blocks WHERE ip = ?", (ip,))
            conn.commit()
        logger.debug(f"IP {ip} supprimée de la DB")
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du bloc: {e}")
        raise DatabaseError(f"Erreur DB: {e}")

def get_blocks() -> List[dict]:
    """Récupérer tous les blocs IP."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT ip, reason, ts, expires_at FROM blocks ORDER BY ts DESC")
            rows = c.fetchall()
        return [{"ip": r[0], "reason": r[1], "ts": r[2], "expires_at": r[3]} for r in rows]
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des blocs: {e}")
        return []

def check_token(request: Request) -> None:
    """Vérifier le token d'authentification."""
    token = request.headers.get("Authorization", "")
    expected_token = f"Bearer {API_TOKEN}"
    if token != expected_token:
        logger.warning(f"Tentative d'accès non authentifiée")
        raise HTTPException(status_code=401, detail="Unauthorized")

class BlockReq(BaseModel):
    """Modèle de requête de blocage."""
    ip: IPvAnyAddress = Field(..., description="Adresse IP à bloquer")
    ttl_seconds: Optional[int] = Field(None, description="Durée de blocage en secondes")
    reason: Optional[str] = Field(None, description="Raison du blocage")

    class Config:
        example = {
            "ip": "192.168.1.100",
            "ttl_seconds": 3600,
            "reason": "ssh_bruteforce"
        }

class UnblockReq(BaseModel):
    """Modèle de requête de déblocage."""
    ip: IPvAnyAddress = Field(..., description="Adresse IP à débloquer")

app = FastAPI(
    title="DynFW API",
    description="API pour la gestion dynamique du firewall",
    version="1.0.0"
)

@app.on_event("startup")
def startup():
    """Événement au démarrage de l'application."""
    try:
        init_db()
        im.ensure_chain()
        logger.info("Démarrage de l'API DynFW réussi")
    except Exception as e:
        logger.error(f"Erreur au démarrage: {e}")
        raise

@app.post("/block", dependencies=[Depends(check_token)])
def block(r: BlockReq):
    """Bloquer une adresse IP."""
    ip = str(r.ip)
    try:
        im.block_ip(ip, comment=r.reason or "dynfw")
    except im.IptablesError as e:
        logger.error(f"Erreur iptables: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur iptables: {e}")
    except Exception as e:
        logger.error(f"Erreur lors du blocage: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne")
    
    try:
        add_db_block(ip, r.reason, r.ttl_seconds)
    except DatabaseError as e:
        logger.error(f"Erreur base de données: {e}")
        # Ne pas échouer la requête si la DB échoue
    
    logger.info(f"IP {ip} bloquée - Raison: {r.reason}")
    return {"status": "blocked", "ip": ip}

@app.post("/unblock", dependencies=[Depends(check_token)])
def unblock(r: UnblockReq):
    """Débloquer une adresse IP."""
    ip = str(r.ip)
    try:
        im.unblock_ip(ip)
    except im.IptablesError as e:
        logger.error(f"Erreur iptables: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur iptables: {e}")
    except Exception as e:
        logger.error(f"Erreur lors du déblocage: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne")
    
    try:
        remove_db_block(ip)
    except DatabaseError as e:
        logger.warning(f"Erreur base de données (déblocage continué): {e}")
    
    logger.info(f"IP {ip} débloquée")
    return {"status": "unblocked", "ip": ip}

@app.get("/list", dependencies=[Depends(check_token)])
def list_blocks():
    """Lister tous les blocs IP."""
    blocks = get_blocks()
    logger.debug(f"Liste des blocs: {len(blocks)} entrées")
    return {"blocks": blocks, "count": len(blocks)}

@app.post("/cleanup", dependencies=[Depends(check_token)])
def cleanup_expired():
    """Nettoyer les blocs IP expirés."""
    now = int(time.time())
    rows = get_blocks()
    removed_count = 0
    error_count = 0
    
    for r in rows:
        if r["expires_at"] and r["expires_at"] <= now:
            try:
                im.unblock_ip(r["ip"])
                remove_db_block(r["ip"])
                removed_count += 1
                logger.info(f"Bloc expiré supprimé: {r['ip']}")
            except Exception as e:
                logger.error(f"Erreur lors de la suppression du bloc expiré {r['ip']}: {e}")
                error_count += 1
    
    logger.info(f"Nettoyage: {removed_count} blocs supprimés, {error_count} erreurs")
    return {
        "status": "completed",
        "removed": removed_count,
        "errors": error_count
    }

@app.get("/health", tags=["Health"])
def health_check():
    """Vérifier l'état de l'API."""
    return {
        "status": "healthy",
        "timestamp": int(time.time())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
