#!/usr/bin/env python3
# log_analyzer_improved.py - Auto-learner DynFW (SSH bruteforce)

import time
import re
import requests
import ipaddress
import logging
import sys
import os
from collections import defaultdict, deque

# ---------------------------------------------------------
# LOGGING
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

# 🔴 IMPORTANT : auth.log (SSH écrit ici)
LOGFILE = os.environ.get("DYNFW_LOGFILE", "/var/log/auth.log")

THRESHOLD = int(os.environ.get("DYNFW_THRESHOLD", "5"))
WINDOW = int(os.environ.get("DYNFW_WINDOW", "300"))
BLOCK_TTL = int(os.environ.get("DYNFW_BLOCK_TTL", "7200"))
REQUEST_TIMEOUT = 5

# ---------------------------------------------------------
# STOCKAGE DES TENTATIVES
# ---------------------------------------------------------
attempts = defaultdict(deque)
blocked_ips = set()

# ---------------------------------------------------------
# REGEX SSH (ROBUSTE)
# ---------------------------------------------------------
SSH_FAIL_REGEX = re.compile(
    r"(Failed password|Invalid user).* from (\d+\.\d+\.\d+\.\d+)"
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

blocked_ips = set()  # pour éviter de bloquer plusieurs fois la même IP

def send_block(ip: str, block_port: int | None = None) -> bool:
    """
    Bloque une IP via l'API.
    - block_port : int -> bloque uniquement ce port
                  None -> bloque tous les ports
    """
    if ip in blocked_ips:
        return False

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "ip": ip,
        "ttl_seconds": BLOCK_TTL,
        "reason": "ssh_bruteforce",
        "port": block_port  # None ou numéro de port
    }

    try:
        r = requests.post(
            API_URL,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        if r.status_code == 200:
            if block_port:
                logger.warning(f"🔥 IP BLOQUÉE: {ip} sur le port {block_port}")
            else:
                logger.warning(f"🔥 IP BLOQUÉE: {ip} sur tous les ports")
            blocked_ips.add(ip)
            return True
        else:
            logger.error(f"API error {r.status_code}: {r.text}")

    except Exception as e:
        logger.error(f"Erreur API: {e}")

    return False



def tail_file(path: str):
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
    except Exception as e:
        logger.error(f"Erreur lecture log: {e}")
        sys.exit(1)


# ---------------------------------------------------------
# ANALYSE DES LIGNES
# ---------------------------------------------------------
def handle_line(line: str):
    if "sshd" not in line.lower():
        return

    match = SSH_FAIL_REGEX.search(line)
    if not match:
        return

    ip = match.group(2)
    if not is_valid_ip(ip):
        return

    now = time.time()
    dq = attempts[ip]
    dq.append(now)

    # Nettoyage fenêtre
    while dq and dq[0] < now - WINDOW:
        dq.popleft()

    logger.info(f"🔐 {ip} → {len(dq)}/{THRESHOLD} tentatives")

    if len(dq) >= THRESHOLD:
        logger.warning(f"🚨 Bruteforce détecté depuis {ip}")
        if send_block(ip):
            dq.clear()


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    logger.info("🚀 Auto-learner DynFW démarré")
    logger.info(f"LOGFILE   : {LOGFILE}")
    logger.info(f"API       : {API_URL}")
    logger.info(f"SEUIL     : {THRESHOLD}")
    logger.info(f"FENÊTRE   : {WINDOW}s")
    logger.info(f"TTL BLOCK : {BLOCK_TTL}s")

    for line in tail_file(LOGFILE):
        handle_line(line)


if __name__ == "__main__":
    main()
