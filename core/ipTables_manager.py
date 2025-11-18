# iptables_manager.py
import subprocess
import ipaddress
import logging
import shlex
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("iptables_manager")

CHAIN = "DYN_BLOCK"
TABLE = "filter"

def run_cmd(cmd: list[str]):
    logger.debug("Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)

def ensure_chain():
    # create chain if not exists and insert into INPUT if needed
    try:
        run_cmd(["sudo", "iptables", "-t", TABLE, "-n", "-L", CHAIN])
    except subprocess.CalledProcessError:
        logger.info("Creating chain %s", CHAIN)
        run_cmd(["sudo", "iptables", "-t", TABLE, "-N", CHAIN])
    # ensure there's a jump from INPUT to CHAIN at top
    out = subprocess.run(["sudo", "iptables", "-t", TABLE, "-C", "INPUT", "-j", CHAIN],
                         check=False)
    if out.returncode != 0:
        logger.info("Inserting jump from INPUT to %s", CHAIN)
        run_cmd(["sudo", "iptables", "-t", TABLE, "-I", "INPUT", "1", "-j", CHAIN])

def block_ip(ip: str, comment: Optional[str] = None):
    ipaddress.ip_address(ip)  # raises if invalid
    ensure_chain()
    cmd = ["sudo", "iptables", "-t", TABLE, "-A", CHAIN, "-s", ip, "-j", "DROP"]
    if comment:
        cmd += ["-m", "comment", "--comment", comment]
    run_cmd(cmd)
    logger.info("Blocked %s", ip)

def unblock_ip(ip: str):
    ipaddress.ip_address(ip)
    # remove all matching rules for that source in CHAIN
    # iptables doesn't accept delete by src alone with -D unless exact rule exists,
    # so we list and remove any rule that contains the ip.
    out = subprocess.run(["sudo", "iptables", "-t", TABLE, "-S", CHAIN],
                         capture_output=True, text=True, check=True)
    lines = out.stdout.splitlines()
    for line in lines:
        if f"-s {ip}" in line:
            # transform "-A CHAIN ..." into arguments for -D
            parts = shlex.split(line)
            # replace leading -A with -D
            parts[0] = "-D"
            # run iptables with these args
            cmd = ["sudo", "iptables", "-t", TABLE] + parts
            run_cmd(cmd)
            logger.info("Unblocked rule: %s", " ".join(cmd))

def list_blocked() -> list[str]:
    out = subprocess.run(["sudo", "iptables", "-t", TABLE, "-S", CHAIN],
                         capture_output=True, text=True, check=True)
    ips = []
    for line in out.stdout.splitlines():
        if "-s" in line:
            # crude parse
            parts = line.split()
            try:
                i = parts.index("-s")
                ips.append(parts[i+1])
            except Exception:
                continue
    return ips

if __name__ == "__main__":
    # quick demo
    ensure_chain()
    print("Blocked list:", list_blocked())
