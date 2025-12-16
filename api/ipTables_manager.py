#!/usr/bin/env python3
# iptables_manager.py - Gestion des règles iptables pour le firewall dynamique

import subprocess
import ipaddress
import logging
import shlex
from typing import Optional, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("iptables_manager")

CHAIN = "DYN_BLOCK"
TABLE = "filter"
IPTABLES_CMD = "/usr/sbin/iptables"  # changer si iptables est ailleurs

class IptablesError(Exception):
    pass

def run_cmd(cmd: List[str]):
    """Exécuter la commande iptables avec gestion d'erreur."""
    logger.debug("Running: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.error("Command failed: %s", e.stderr or e)
        raise IptablesError(f"Failed to run: {' '.join(cmd)}")

def ensure_chain():
    """Créer la chaîne custom si elle n'existe pas et s'assurer qu'INPUT pointe vers elle."""
    try:
        run_cmd(["sudo", IPTABLES_CMD, "-t", TABLE, "-n", "-L", CHAIN])
        logger.debug(f"Chain {CHAIN} exists")
    except IptablesError:
        logger.info(f"Creating chain {CHAIN}")
        run_cmd(["sudo", IPTABLES_CMD, "-t", TABLE, "-N", CHAIN])

    # s'assurer que INPUT pointe vers la chaîne
    out = subprocess.run(["sudo", IPTABLES_CMD, "-t", TABLE, "-C", "INPUT", "-j", CHAIN],
                         capture_output=True, text=True)
    if out.returncode != 0:
        logger.info(f"Inserting jump from INPUT to {CHAIN}")
        run_cmd(["sudo", IPTABLES_CMD, "-t", TABLE, "-I", "INPUT", "1", "-j", CHAIN])

def block_ip(ip: str, port: Optional[int] = None, comment: Optional[str] = None):
    """Bloquer une IP avec port optionnel et commentaire."""
    ipaddress.ip_address(ip)
    ensure_chain()
    cmd = ["sudo", IPTABLES_CMD, "-t", TABLE, "-A", CHAIN, "-s", ip]
    if port:
        cmd += ["-p", "tcp", "--dport", str(port)]
    cmd += ["-j", "DROP"]
    if comment:
        cmd += ["-m", "comment", "--comment", comment[:255]]
    run_cmd(cmd)
    logger.info(f"Blocked {ip}{' on port '+str(port) if port else ''}")

def unblock_ip(ip: str, port: Optional[int] = None):
    """Débloquer une IP. Si port précisé, ne supprime que cette règle."""
    ipaddress.ip_address(ip)
    result = subprocess.run(["sudo", IPTABLES_CMD, "-t", TABLE, "-S", CHAIN],
                            capture_output=True, text=True, check=True)
    lines = result.stdout.splitlines()
    deleted_count = 0
    for line in lines:
        if f"-s {ip}" in line:
            if port and f"--dport {port}" not in line:
                continue  # ne supprimer que si port correspond
            parts = shlex.split(line)
            if parts[0] != "-A":
                continue
            parts[0] = "-D"
            cmd = ["sudo", IPTABLES_CMD, "-t", TABLE] + parts
            run_cmd(cmd)
            deleted_count += 1
            logger.info(f"Unblocked rule: {' '.join(cmd)}")
    if deleted_count == 0:
        logger.warning(f"No rule found for {ip}{' on port '+str(port) if port else ''}")

def list_blocked() -> List[str]:
    """Lister toutes les IPs bloquées (tous ports confondus)."""
    result = subprocess.run(["sudo", IPTABLES_CMD, "-t", TABLE, "-S", CHAIN],
                            capture_output=True, text=True, check=True)
    ips = []
    for line in result.stdout.splitlines():
        if "-s" in line:
            parts = line.split()
            try:
                idx = parts.index("-s")
                ip = parts[idx + 1]
                ipaddress.ip_address(ip)
                ips.append(ip)
            except Exception:
                continue
    return ips

if __name__ == "__main__":
    ensure_chain()
    print(f"IPs bloquées ({len(list_blocked())}): {list_blocked()}")
