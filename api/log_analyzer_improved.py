#!/usr/bin/env python3
# log_analyzer.py - Auto-learner pour bloquer les IPs suspectes

import time
import re
import requests
import ipaddress
import logging
import sys
from collections import defaultdict, deque
import os

# ---------------------------------------------------------
# CONFIG LOGGING
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("auto_learner")

# ---------------------------------------------------------
# CONFIGURATION (ENV)
# ---------------------------------------------------------
API_URL = os.environ.get("DYNFW_API_URL", "http://127.0.0.1:8000/block")
API_TOKEN = os.environ.get("DYNFW_API_TOKEN", "MyToken")

LOGFILE = os.environ.get(
    "DYNFW_LOGFILE",
    "/home/mamy/Desktop/Projet_fin_annee/Firewall_project/api/api.log"
)

THRESHOLD = int(os.environ.get("DYNFW_THRESHOLD", "5"))   # tentatives
WINDOW = int(os.environ.get("DYNFW_WINDOW", "300"))       # 5 minutes
BLOCK_TTL = int(os.environ.get("DYNFW_BLOCK_TTL", "7200"))  # 2 heures
REQUEST_TIMEOUT = int(os.environ.get("DYNFW_TIMEOUT", "5"))

# ---------------------------------------------------------
# CACHE DES TENTATIVES
# ---------------------------------------------------------
ip_failures = defaultdict(lambda: deque())

# ---------------------------------------------------------
# REGEX IP (IPv4 + IPv6)
# ---------------------------------------------------------
ip_regex = re.compile(
    r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
    r'|(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}'
)

# ---------------------------------------------------------
# UTILS
# ---------------------------------------------------------
def is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def send_block(ip: str, reason: str) -> bool:
    """Appel API pour bloquer une IP"""
    if not is_valid_ip(ip):
        logger.warning(f"IP invalide ignorée: {ip}")
        return False

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "ip": ip,
        "ttl_seconds": BLOCK_TTL,
        "reason": reason
    }

    try:
        r = requests.post(
            API_URL,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        if r.status_code in (200, 201):
            logger.warning(f"🔥 IP BLOQUÉE: {ip} ({reason})")
            return True
        else:
            logger.error(f"API error {r.status_code}: {r.text}")
            return False

    except requests.exceptions.Timeout:
        logger.error(f"Timeout API pour {ip}")
    except requests.exceptions.ConnectionError:
        logger.error(f"Connexion API impossible: {API_URL}")
    except Exception as e:
        logger.error(f"Erreur blocage {ip}: {e}")

    return False


def tail_file(path: str):
    """Lecture continue du fichier de log"""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)
            logger.info(f"📡 Surveillance du fichier: {path}")
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                yield line.strip()

    except FileNotFoundError:
        logger.error(f"Fichier introuvable: {path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erreur lecture fichier: {e}")
        sys.exit(1)


# ---------------------------------------------------------
# ANALYSE DES LIGNES
# ---------------------------------------------------------
def handle_line(line: str):
    if not line:
        return

    # 🔐 Erreurs d'authentification API / SSH / JWT
    patterns = [
        "Unauthorized",
        "Invalid token",
        "authentication failed",
        "Failed password",
        "Invalid user"
    ]

    if not any(p.lower() in line.lower() for p in patterns):
        return

    matches = ip_regex.findall(line)
    if not matches:
        return

    ip = matches[0]
    if not is_valid_ip(ip):
        return

    now = time.time()
    dq = ip_failures[ip]
    dq.append(now)

    # Nettoyage fenêtre temporelle
    while dq and dq[0] < now - WINDOW:
        dq.popleft()

    if len(dq) >= THRESHOLD:
        logger.warning(
            f"🚨 Bruteforce détecté: {ip} "
            f"({len(dq)} tentatives en {WINDOW}s)"
        )

        if send_block(ip, reason="auth_bruteforce"):
            dq.clear()
    else:
        logger.info(f"{ip} → {len(dq)}/{THRESHOLD} tentatives")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    logger.info("🚀 Auto-learner DynFW démarré")
    logger.info(f"LOGFILE   : {LOGFILE}")
    logger.info(f"API       : {API_URL}")
    logger.info(f"SEUIL     : {THRESHOLD} tentatives")
    logger.info(f"FENÊTRE   : {WINDOW}s")
    logger.info(f"TTL BLOCK : {BLOCK_TTL}s")

    try:
        for line in tail_file(LOGFILE):
            handle_line(line)

    except KeyboardInterrupt:
        logger.info("🛑 Arrêt manuel")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erreur critique: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
