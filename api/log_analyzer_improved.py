#!/usr/bin/env python3
# log_analyzer.py - Auto-learner pour bloquer les IPs suspectes
import time
import re
import requests
import ipaddress
import logging
import sys
from collections import defaultdict, deque
from typing import Optional
import os

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("auto_learner")

# Configuration via variables d'environnement
API_URL = os.environ.get("DYNFW_API_URL", "http://127.0.0.1:8000/block")
API_TOKEN = os.environ.get("DYNFW_API_TOKEN", "change_me")
LOGFILE = os.environ.get("DYNFW_LOGFILE", "/var/log/auth.log")

THRESHOLD = int(os.environ.get("DYNFW_THRESHOLD", "5"))  # tentatives
WINDOW = int(os.environ.get("DYNFW_WINDOW", "300"))      # secondes (5 minutes)
BLOCK_TTL = int(os.environ.get("DYNFW_BLOCK_TTL", str(3600 * 2)))  # 2 heures
REQUEST_TIMEOUT = int(os.environ.get("DYNFW_TIMEOUT", "5"))  # timeout API

# Cache des tentatives de connexion échouées
ip_failures: dict = defaultdict(lambda: deque())

# Regex pour détecter les adresses IP (IPv4 et IPv6)
ip_regex = re.compile(
    r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|'
    r'(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}'
)

def is_valid_ip(ip: str) -> bool:
    """Valider qu'une adresse IP est valide."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def send_block(ip: str, reason: str = "ssh_bruteforce") -> bool:
    """Envoyer une requête de blocage à l'API."""
    if not is_valid_ip(ip):
        logger.warning(f"IP invalide: {ip}")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {API_TOKEN}"}
        payload = {"ip": ip, "ttl_seconds": BLOCK_TTL, "reason": reason}
        r = requests.post(
            API_URL, 
            json=payload, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        if r.status_code in (200, 201):
            logger.info(f"IP {ip} bloquée avec succès")
            return True
        else:
            logger.error(f"Erreur API: {r.status_code} - {r.text}")
            return False
    except requests.exceptions.Timeout:
        logger.error(f"Timeout lors du blocage de {ip}")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"Erreur de connexion à l'API: {API_URL}")
        return False
    except Exception as e:
        logger.error(f"Erreur inattendue lors du blocage de {ip}: {e}")
        return False

def tail_file(path: str):
    """Lire un fichier depuis la fin et générer les nouvelles lignes."""
    try:
        with open(path, "r", encoding='utf-8', errors='ignore') as f:
            # Aller à la fin du fichier
            f.seek(0, 2)
            logger.info(f"Suivi de {path} commencé")
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                yield line.strip()
    except FileNotFoundError:
        logger.error(f"Fichier non trouvé: {path}")
        sys.exit(1)
    except IOError as e:
        logger.error(f"Erreur de lecture du fichier {path}: {e}")
        sys.exit(1)

def handle_line(line: str) -> None:
    """Analyser une ligne de log et déclencher le blocage si nécessaire."""
    if not line:
        return
    
    # Détecter les tentatives échouées SSH
    if "Failed password" in line or "Invalid user" in line:
        matches = ip_regex.findall(line)
        if not matches:
            return
        
        ip = matches[0]
        
        # Valider l'IP
        if not is_valid_ip(ip):
            logger.debug(f"IP invalide détectée: {ip}")
            return
        
        now = time.time()
        dq = ip_failures[ip]
        dq.append(now)
        
        # Supprimer les tentatives en dehors de la fenêtre
        while dq and dq[0] < now - WINDOW:
            dq.popleft()
        
        if len(dq) >= THRESHOLD:
            logger.warning(f"Seuil atteint pour {ip} ({len(dq)} tentatives en {WINDOW}s)")
            ok = send_block(ip, reason="ssh_bruteforce")
            if ok:
                dq.clear()
                logger.info(f"IP {ip} bloquée après {len(dq)} tentatives")
        else:
            logger.debug(f"IP {ip}: {len(dq)}/{THRESHOLD} tentatives")

def main():
    """Point d'entrée principal."""
    logger.info(f"Démarrage de l'auto-learner")
    logger.info(f"Fichier de log: {LOGFILE}")
    logger.info(f"Seuil: {THRESHOLD} tentatives en {WINDOW}s")
    logger.info(f"API: {API_URL}")
    
    try:
        for line in tail_file(LOGFILE):
            handle_line(line)
    except KeyboardInterrupt:
        logger.info("Arrêt de l'auto-learner")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erreur critique: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
