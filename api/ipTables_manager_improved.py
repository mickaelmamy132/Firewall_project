#!/usr/bin/env python3
# iptables_manager.py - Gestion des règles iptables pour le firewall dynamique
import subprocess
import ipaddress
import logging
import shlex
from typing import Optional, List


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("iptables_manager")

CHAIN = "DYN_BLOCK"
TABLE = "filter"
IPTABLES = "/usr/sbin/iptables"

class IptablesError(Exception):
    """Exception personnalisée pour les erreurs iptables."""
    pass

def run_cmd(cmd: List[str]) -> None:
    """Exécuter une commande shell avec gestion d'erreurs."""
    logger.debug(f"Exécution: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.stderr:
            logger.warning(f"Stderr: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise IptablesError(f"Timeout lors de l'exécution: {' '.join(cmd)}")
    except subprocess.CalledProcessError as e:
        raise IptablesError(f"Erreur iptables: {e.stderr or e}")
    except FileNotFoundError:
        raise IptablesError("sudo ou iptables non trouvé. Vérifier l'installation.")


def ensure_chain() -> None:
    """Créer la chaîne custom si elle n'existe pas et la lier à INPUT."""
    try:
        # Vérifier si la chaîne existe
        subprocess.run(
            ["sudo", IPTABLES, "-t", TABLE, "-n", "-L", CHAIN],
            check=True,
            capture_output=True,
            timeout=5
        )
        logger.debug(f"Chaîne {CHAIN} existe déjà")
    except subprocess.CalledProcessError:
        # La chaîne n'existe pas, la créer
        logger.info(f"Création de la chaîne {CHAIN}")
        run_cmd(["sudo", IPTABLES, "-t", TABLE, "-N", CHAIN])
    
    # S'assurer qu'il y a une redirection INPUT -> CHAIN
    try:
        subprocess.run(
            ["sudo", IPTABLES, "-t", TABLE, "-C", "INPUT", "-j", CHAIN],
            check=True,
            capture_output=True,
            timeout=5
        )
        logger.debug(f"Redirection INPUT -> {CHAIN} existe déjà")
    except subprocess.CalledProcessError:
        logger.info(f"Ajout de la redirection INPUT -> {CHAIN}")
        run_cmd(["sudo", IPTABLES, "-t", TABLE, "-I", "INPUT", "1", "-j", CHAIN])

def block_ip(ip: str, comment: Optional[str] = None) -> None:
    """Bloquer une adresse IP."""
    try:
        # Valider l'IP
        ipaddress.ip_address(ip)
    except ValueError as e:
        raise IptablesError(f"Adresse IP invalide: {ip} - {e}")
    
    try:
        ensure_chain()
        cmd = ["sudo", IPTABLES, "-t", TABLE, "-A", CHAIN, "-s", ip, "-j", "DROP"]
        if comment:
            cmd.extend(["-m", "comment", "--comment", str(comment)[:255]])
        run_cmd(cmd)
        logger.info(f"IP {ip} bloquée")
    except IptablesError as e:
        logger.error(f"Erreur lors du blocage de {ip}: {e}")
        raise

def unblock_ip(ip: str) -> None:
    """Débloquer une adresse IP."""
    try:
        # Valider l'IP
        ipaddress.ip_address(ip)
    except ValueError as e:
        raise IptablesError(f"Adresse IP invalide: {ip} - {e}")
    
    try:
        result = subprocess.run(
            ["sudo", IPTABLES, "-t", TABLE, "-S", CHAIN],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        lines = result.stdout.splitlines()
        deleted_count = 0
        
        for line in lines:
            if f"-s {ip}" in line:
                try:
                    # Transformer "-A CHAIN ..." en arguments pour -D
                    parts = shlex.split(line)
                    if parts[0] != "-A":
                        continue
                    parts[0] = "-D"
                    cmd = ["sudo", IPTABLES, "-t", TABLE] + parts
                    run_cmd(cmd)
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Erreur lors de la suppression de la règle: {e}")
        
        if deleted_count > 0:
            logger.info(f"IP {ip} débloquée ({deleted_count} règle(s) supprimée(s))")
        else:
            logger.warning(f"Aucune règle trouvée pour {ip}")
    except IptablesError as e:
        logger.error(f"Erreur lors du débloquage de {ip}: {e}")
        raise

def list_blocked() -> List[str]:
    """Lister toutes les IPs bloquées."""
    try:
        result = subprocess.run(
            ["sudo", IPTABLES, "-t", TABLE, "-S", CHAIN],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        ips = []
        for line in result.stdout.splitlines():
            if "-s" in line:
                try:
                    parts = line.split()
                    idx = parts.index("-s")
                    if idx + 1 < len(parts):
                        ip = parts[idx + 1]
                        # Valider l'IP avant de l'ajouter
                        try:
                            ipaddress.ip_address(ip)
                            ips.append(ip)
                        except ValueError:
                            logger.warning(f"IP invalide dans la règle: {ip}")
                except (ValueError, IndexError):
                    continue
        
        return ips
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur lors de la récupération de la liste: {e}")
        return []

if __name__ == "__main__":
    try:
        ensure_chain()
        blocked_ips = list_blocked()
        print(f"IPs bloquées ({len(blocked_ips)}):")
        for ip in blocked_ips:
            print(f"  - {ip}")
    except IptablesError as e:
        print(f"Erreur: {e}")
        exit(1)
