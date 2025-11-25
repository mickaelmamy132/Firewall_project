#!/bin/bash
# stop_firewall.sh - Script d'arrêt du firewall dynamique

echo "🛑 Arrêt du Firewall Dynamique..."

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Arrêter l'API et l'auto-learner
pkill -f "firewall_api_improved.py" || true
pkill -f "log_analyzer_improved.py" || true

# Arrêter les processus stockés dans les PIDs
if [ -f .pids/api.pid ]; then
    kill $(cat .pids/api.pid) 2>/dev/null || true
    rm .pids/api.pid
fi

if [ -f .pids/learner.pid ]; then
    kill $(cat .pids/learner.pid) 2>/dev/null || true
    rm .pids/learner.pid
fi

sleep 1

echo "✅ Firewall arrêté"
