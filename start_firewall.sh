#!/bin/bash
# start_firewall.sh - Script de démarrage du firewall dynamique

set -e  # Arrêter en cas d'erreur

echo "🚀 Démarrage du Firewall Dynamique..."

# Répertoire du projet
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# ✅ Chemin Python du venv
PYTHON="$PROJECT_DIR/venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "❌ Erreur: L'environnement virtuel 'venv' n'existe pas ou Python est introuvable."
    echo "   Crée-le avec : python3 -m venv venv"
    exit 1
fi

echo "✅ Python utilisé : $PYTHON"

# ✅ Variables d'environnement
export DYNFW_API_URL="${DYNFW_API_URL:-http://127.0.0.1:8000/block}"
export DYNFW_API_TOKEN="${DYNFW_API_TOKEN:-MyToken}"
export DYNFW_LOGFILE="${DYNFW_LOGFILE:-/var/log/auth.log}"
export DYNFW_DB="${DYNFW_DB:-/var/lib/dynfw/dynfw.db}"
export DYNFW_THRESHOLD="${DYNFW_THRESHOLD:-5}"
export DYNFW_WINDOW="${DYNFW_WINDOW:-300}"
export DYNFW_BLOCK_TTL="${DYNFW_BLOCK_TTL:-7200}"

# ✅ Vérifier sudo + iptables
if sudo -n /usr/sbin/iptables -L > /dev/null 2>&1; then
    echo "✅ Droits sudo vérifiés"
else
    echo "ℹ️  Sudo va demander le mot de passe..."
    if ! sudo /usr/sbin/iptables -L > /dev/null 2>&1; then
        echo "❌ Erreur: Impossible d'accéder à iptables"
        exit 1
    fi
fi

# ✅ Créer dossier DB
sudo mkdir -p "$(dirname "$DYNFW_DB")"
sudo chown "$USER:$USER" "$(dirname "$DYNFW_DB")"

echo "✅ Configuration:"
echo "   API URL     : $DYNFW_API_URL"
echo "   Log File    : $DYNFW_LOGFILE"
echo "   DB Path     : $DYNFW_DB"
echo "   Threshold   : $DYNFW_THRESHOLD tentatives"
echo "   Window      : $DYNFW_WINDOW secondes"
echo "   Block TTL   : $DYNFW_BLOCK_TTL secondes"
echo ""

# ✅ Vérification du fichier log
if [ ! -f "$DYNFW_LOGFILE" ]; then
    echo "⚠️  Fichier de log '$DYNFW_LOGFILE' introuvable. Recherche..."

    if [ -f "/var/log/auth.log" ]; then
        export DYNFW_LOGFILE="/var/log/auth.log"
        echo "✅ Utilisation : /var/log/auth.log"
    elif [ -f "/var/log/secure" ]; then
        export DYNFW_LOGFILE="/var/log/secure"
        echo "✅ Utilisation : /var/log/secure"
    else
        echo "❌ Aucun fichier de log trouvé."
        exit 1
    fi
fi

# ✅ Vérifier que nc existe
if ! command -v nc >/dev/null 2>&1; then
    echo "❌ Erreur: 'nc' (netcat) est requis pour vérifier l'API."
    echo "   Installe-le : sudo apt install netcat-openbsd"
    exit 1
fi

echo "📋 Démarrage en cours..."
mkdir -p api/logs .pids

# ✅ Lancer l'API
echo "[1] Lancement de l'API FastAPI..."
nohup "$PYTHON" api/firewall_api_improved.py > api/logs/api.log 2>&1 &
API_PID=$!
echo "    PID API : $API_PID"

# ✅ Attendre que l'API soit prête
echo "    Vérification de l'API..."
for i in {1..10}; do
    if nc -z 127.0.0.1 8000; then
        echo "    ✅ API prête"
        break
    fi

    if [ "$i" -eq 10 ]; then
        echo "❌ API ne répond pas"
        tail -n 20 api/logs/api.log
        exit 1
    fi

    sleep 1
done

# ✅ Lancer l'auto-learner
echo ""
echo "[2] Lancement de l'auto-learner..."
nohup "$PYTHON" api/log_analyzer_improved.py > api/logs/learner.log 2>&1 &
LEARNER_PID=$!
echo "    PID Auto-learner : $LEARNER_PID"

sleep 1
if ! kill -0 "$LEARNER_PID" 2>/dev/null; then
    echo "❌ Erreur: L'auto-learner n'a pas démarré"
    tail -n 20 api/logs/learner.log
    exit 1
fi

# ✅ Fin
echo ""
echo "✅ Firewall Dynamique démarré avec succès!"
echo ""
echo "📊 Informations:"
echo "   API          : http://127.0.0.1:8000"
echo "   Documentation: http://127.0.0.1:8000/docs"
echo "   Logs API     : tail -f api/logs/api.log"
echo "   Logs Learner : tail -f api/logs/learner.log"
echo ""
echo "🛑 Pour arrêter : ./stop_firewall.sh"
echo ""

# ✅ Sauvegarder les PID
echo "$API_PID" > .pids/api.pid
echo "$LEARNER_PID" > .pids/learner.pid

wait
