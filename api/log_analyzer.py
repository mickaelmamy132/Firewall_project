# auto_learn.py
import time
import re
import requests
from collections import defaultdict, deque
import os

API_URL = os.environ.get("DYNFW_API_URL", "http://127.0.0.1:8000/block")
API_TOKEN = os.environ.get("DYNFW_API_TOKEN", "MyToken")
LOGFILE = os.environ.get(
    "DYNFW_LOGFILE",
    "/home/mamy/Desktop/Projet_fin_annee/Firewall_project/api/api.log"
)


THRESHOLD = 3         # tentatives 
WINDOW = 300          # secondes (5 minutes)
BLOCK_TTL = 3600*2    # 2 heures

ip_failures = defaultdict(lambda: deque())

ip_regex = re.compile(r'(\d+\.\d+\.\d+\.\d+)')

def send_block(ip, reason="ssh_bruteforce"):
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {"ip": ip, "ttl_seconds": BLOCK_TTL, "reason": reason}
    r = requests.post(API_URL, json=payload, headers=headers, timeout=5)
    return r.status_code == 200 or r.status_code == 201

def tail_file(path):
    with open(path, "r") as f:
        # go to end
        f.seek(0,2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            yield line

def handle_line(line):

    if "Failed password" in line or "Invalid user" in line:
        m = ip_regex.search(line)
        if m:
            ip = m.group(1)
            now = time.time()
            dq = ip_failures[ip]
            dq.append(now)
            # remove olds
            while dq and dq[0] < now - WINDOW:
                dq.popleft()
            if len(dq) >= THRESHOLD:
                print(f"[AUTO] Blocking {ip} (threshold reached)")
                ok = send_block(ip)
                if ok:
                    dq.clear()

if __name__ == "__main__":
    print("Starting auto-learner, watching", LOGFILE)
    for ln in tail_file(LOGFILE):
        handle_line(ln)
