#!/bin/bash
# DEMARRAGE_COMPLET.sh - Démarrage complet et vérification du firewall

set -e

echo "=========================================="
echo "🔥  FIREWALL DYNAMIQUE - DÉMARRAGE COMPLET"
echo "=========================================="
echo ""

PROJECT_DIR="/home/mamy/Desktop/Firewall_project"
cd "$PROJECT_DIR"

# Étape 1: Vérifier les prérequis
echo "📋 [1] Vérification des prérequis..."

# Vérifier iptables
if ! which iptables > /dev/null 2>&1 && [ ! -f /usr/sbin/iptables ]; then
    echo "❌ iptables non trouvé. Installation..."
    sudo apt update && sudo apt install -y iptables
fi
echo "    ✅ iptables disponible"

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 non trouvé. Installation..."
    sudo apt install -y python3 python3-pip
fi
echo "    ✅ Python3 disponible"

# Vérifier curl
if ! command -v curl &> /dev/null; then
    echo "    ⚠️  curl non trouvé. Installation..."
    sudo apt install -y curl
fi
echo "    ✅ curl disponible"

# Étape 2: Créer le fichier de log SSH
echo ""
echo "📋 [2] Préparation du fichier de log..."
if [ ! -f /var/log/auth.log ]; then
    echo "    Création de /var/log/auth.log..."
    sudo touch /var/log/auth.log
fi
sudo chmod 644 /var/log/auth.log
echo "    ✅ /var/log/auth.log prêt"

# Étape 3: Installer les dépendances Python
echo ""
echo "📋 [3] Installation des dépendances Python..."
if [ -f .venv/bin/python ]; then
    PYTHON=".venv/bin/python"
    echo "    Environnement virtuel détecté"
else
    PYTHON="python3"
    echo "    Utilisation de python3 système"
fi

$PYTHON -m pip install -q --upgrade pip 2>/dev/null || true
$PYTHON -m pip install -q fastapi uvicorn requests pydantic 2>/dev/null || pip3 install -q fastapi uvicorn requests pydantic

echo "    ✅ Dépendances Python installées"

# Étape 4: Démarrer le firewall
echo ""
echo "📋 [4] Démarrage du Firewall..."
bash start_firewall_simple.sh

echo ""
echo "=========================================="
echo "✅ DÉMARRAGE RÉUSSI!"
echo "=========================================="
echo ""
echo "🔗 Accès rapide:"
echo "   - API Docs: http://127.0.0.1:8000/docs"
echo "   - Health Check: http://127.0.0.1:8000/health"
echo "   - Logs API: tail -f api/logs/api.log"
echo "   - Logs Learner: tail -f api/logs/learner.log"
echo ""
echo "🧪 Test rapide:"
echo "   curl -H 'Authorization: Bearer MyToken' http://127.0.0.1:8000/list"
echo ""
echo "🛑 Pour arrêter:"
echo "   bash stop_firewall.sh"
echo ""
