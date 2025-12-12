#!/bin/bash
# start_firewall.sh - Script de démarrage du firewall dynamique

set -e  # Arrêter si erreur

echo "🚀 Démarrage du Firewall Dynamique..."

# Répertoire du projet
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Variables d'environnement
export DYNFW_API_URL="${DYNFW_API_URL:-http://127.0.0.1:8000/block}"
export DYNFW_API_TOKEN="${DYNFW_API_TOKEN:-change_me}"
export DYNFW_LOGFILE="${DYNFW_LOGFILE:-/var/log/auth.log}"
export DYNFW_DB="${DYNFW_DB:-/var/lib/dynfw/dynfw.db}"
export DYNFW_THRESHOLD="${DYNFW_THRESHOLD:-5}"
export DYNFW_WINDOW="${DYNFW_WINDOW:-300}"
export DYNFW_BLOCK_TTL="${DYNFW_BLOCK_TTL:-7200}"

# Vérifier que l'utilisateur a les droits sudo
if sudo -n /usr/sbin/iptables -L > /dev/null 2>&1; then
    echo "✅ Droits sudo vérifiés"
else
    echo "ℹ️  Sudo va demander le mot de passe une première fois"
    if ! sudo /usr/sbin/iptables -L > /dev/null 2>&1; then
        echo "❌ Erreur: Impossible d'accéder à iptables"
        exit 1
    fi
fi

# Créer le répertoire DB s'il n'existe pas
sudo mkdir -p "$(dirname "$DYNFW_DB")"
sudo chown "$USER:$USER" "$(dirname "$DYNFW_DB")"

echo "✅ Configuration:"
echo "   API URL: $DYNFW_API_URL"
echo "   Log File: $DYNFW_LOGFILE"
echo "   DB Path: $DYNFW_DB"
echo "   Threshold: $DYNFW_THRESHOLD tentatives"
echo "   Window: $DYNFW_WINDOW secondes"
echo ""

# Auto-détection du fichier de log si non trouvé
if [ ! -f "$DYNFW_LOGFILE" ]; then
    echo "⚠️  Fichier de log '$DYNFW_LOGFILE' non trouvé. Recherche d'alternatives..."
    if [ -f "/var/log/auth.log" ]; then
        export DYNFW_LOGFILE="/var/log/auth.log"
        echo "    ✅ Fichier de log trouvé et utilisé: $DYNFW_LOGFILE"
    elif [ -f "/var/log/secure" ]; then
        export DYNFW_LOGFILE="/var/log/secure"
        echo "    ✅ Fichier de log trouvé et utilisé: $DYNFW_LOGFILE"
    fi
fi

# Vérifier que le fichier log existe
if [ ! -f "$DYNFW_LOGFILE" ]; then
    echo "❌ Erreur: Aucun fichier de log d'authentification trouvé."
    echo ""
    echo "    ℹ️  Veuillez vérifier l'emplacement des logs d'authentification sur votre système."
    echo "    Puis, mettez à jour la variable DYNFW_LOGFILE dans le fichier .env"
    echo ""
    exit 1
fi

echo "📋 Démarrage en cours..."
echo ""

# Lancer l'API en arrière-plan
echo "[1] Lancement de l'API FastAPI..."
nohup ./venv/bin/python api/firewall_api_improved.py > api/logs/api.log 2>&1 &
API_PID=$!
echo "    PID API: $API_PID"
sleep 2

# Vérifier que l'API a démarré
if ! kill -0 $API_PID 2>/dev/null; then
    echo "❌ Erreur: L'API n'a pas démarré"
    cat logs/api.log
    exit 1
fi

# Vérifier que l'API répond
echo "    Vérification de l'API..."
for i in {1..10}; do
    if curl -s http://127.0.0.1:8000/health > /dev/null; then
        echo "    ✅ API prête"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "    ❌ API ne répond pas"
        exit 1
    fi
    sleep 1
done

echo ""
echo "[2] Lancement de l'auto-learner..."
nohup ./venv/bin/python api/log_analyzer_improved.py > api/logs/learner.log 2>&1 &
LEARNER_PID=$!
echo "    PID Auto-learner: $LEARNER_PID"
sleep 1

# Vérifier que le learner a démarré
if ! kill -0 $LEARNER_PID 2>/dev/null; then
    echo "❌ Erreur: L'auto-learner n'a pas démarré"
    cat logs/learner.log
    exit 1
fi

echo ""
echo "✅ Firewall Dynamique démarré avec succès!"
echo ""
echo "📊 Informations:"
echo "   API: http://127.0.0.1:8000"
echo "   Docs: http://127.0.0.1:8000/docs"
echo "   Logs API: tail -f logs/api.log"
echo "   Logs Learner: tail -f logs/learner.log"
echo ""
echo "🛑 Pour arrêter:"
echo "   ./stop_firewall.sh"
echo ""

# Sauvegarder les PIDs
mkdir -p .pids
echo $API_PID > .pids/api.pid
echo $LEARNER_PID > .pids/learner.pid

wait
