#!/bin/bash
# start_firewall_simple.sh - Version simple sans sudo interactif

set -e

echo "🚀 Démarrage du Firewall Dynamique..."

# Répertoire du projet
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Variables d'environnement
export DYNFW_API_URL="${DYNFW_API_URL:-http://127.0.0.1:8000/block}"
export DYNFW_API_TOKEN="${DYNFW_API_TOKEN:-change_me}"
export DYNFW_LOGFILE="${DYNFW_LOGFILE:-/var/log/auth.log}"
export DYNFW_DB="${DYNFW_DB:-$PROJECT_DIR/data/dynfw.db}"
export DYNFW_THRESHOLD="${DYNFW_THRESHOLD:-5}"
export DYNFW_WINDOW="${DYNFW_WINDOW:-300}"
export DYNFW_BLOCK_TTL="${DYNFW_BLOCK_TTL:-7200}"

echo "✅ Configuration:"
echo "   API URL: $DYNFW_API_URL"
echo "   Log File: $DYNFW_LOGFILE"
echo "   DB Path: $DYNFW_DB"
echo "   Threshold: $DYNFW_THRESHOLD tentatives"
echo "   Window: $DYNFW_WINDOW secondes"
echo ""

# Créer les répertoires
mkdir -p api/logs
mkdir -p data

# Vérifier que le fichier log existe
if [ ! -f "$DYNFW_LOGFILE" ]; then
    echo "❌ Erreur: Fichier de log non trouvé: $DYNFW_LOGFILE"
    exit 1
fi

echo "📋 Démarrage en cours..."
echo ""

# Déterminer le Python à utiliser
if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

# Lancer l'API en arrière-plan
echo "[1] Lancement de l'API FastAPI..."
nohup $PYTHON api/firewall_api_improved.py > api/logs/api.log 2>&1 &
API_PID=$!
echo "    PID API: $API_PID"
sleep 2

# Vérifier que l'API a démarré
if ! kill -0 $API_PID 2>/dev/null; then
    echo "❌ Erreur: L'API n'a pas démarré"
    cat api/logs/api.log
    exit 1
fi

# Vérifier que l'API répond
echo "    Vérification de l'API..."
for i in {1..10}; do
    if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo "    ✅ API prête"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "    ⚠️  API ne répond pas encore (mais elle démarre)"
    fi
    sleep 1
done

echo ""
echo "[2] Lancement de l'auto-learner..."
nohup $PYTHON api/log_analyzer_improved.py > api/logs/learner.log 2>&1 &
LEARNER_PID=$!
echo "    PID Auto-learner: $LEARNER_PID"
sleep 1

# Vérifier que le learner a démarré
if ! kill -0 $LEARNER_PID 2>/dev/null; then
    echo "❌ Erreur: L'auto-learner n'a pas démarré"
    cat api/logs/learner.log
    exit 1
fi

echo ""
echo "✅ Firewall Dynamique démarré avec succès!"
echo ""
echo "📊 Informations:"
echo "   API: http://127.0.0.1:8000"
echo "   Docs: http://127.0.0.1:8000/docs"
echo "   Logs API: tail -f api/logs/api.log"
echo "   Logs Learner: tail -f api/logs/learner.log"
echo ""
echo "🛑 Pour arrêter:"
echo "   ./stop_firewall.sh"
echo ""

# Sauvegarder les PIDs
mkdir -p .pids
echo $API_PID > .pids/api.pid
echo $LEARNER_PID > .pids/learner.pid

echo "💡 Conseil: Testez l'API"
echo "   curl http://127.0.0.1:8000/health"
echo "   curl -H 'Authorization: Bearer change_me' http://127.0.0.1:8000/list"
echo ""
