#!/bin/bash
# setup.sh - Script de configuration initiale

set -e

echo "⚙️  Configuration du Firewall Dynamique..."
echo ""

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 1. Créer les répertoires nécessaires
echo "[1] Création des répertoires..."
mkdir -p api/logs
mkdir -p /var/lib/dynfw 2>/dev/null || sudo mkdir -p /var/lib/dynfw
touch api/logs/api.log
touch api/logs/learner.log
echo "    ✅ Répertoires créés"

# 2. Installer les dépendances Python
echo ""
echo "[2] Installation des dépendances Python..."
pip3 install --user \
    fastapi \
    uvicorn \
    requests \
    pydantic \
    2>/dev/null || sudo pip3 install \
    fastapi \
    uvicorn \
    requests \
    pydantic
echo "    ✅ Dépendances installées"

# 3. Rendre les scripts exécutables
echo ""
echo "[3] Configuration des permissions..."
chmod +x start_firewall.sh
chmod +x stop_firewall.sh
chmod +x api/log_analyzer_improved.py
chmod +x api/firewall_api_improved.py
echo "    ✅ Permissions configurées"

# 4. Vérifier iptables
echo ""
echo "[4] Vérification d'iptables..."
if ! command -v iptables &> /dev/null; then
    echo "    ❌ iptables non installé"
    exit 1
fi
echo "    ✅ iptables disponible"

# 5. Configurer sudo sans mot de passe pour iptables
echo ""
echo "[5] Configuration sudo pour iptables..."
echo ""
echo "    ⚠️  Vous devez configurer sudo sans mot de passe."
echo "    Exécutez: sudo visudo"
echo ""
echo "    Puis ajoutez à la fin:"
echo "    $USER ALL=(ALL) NOPASSWD: /usr/sbin/iptables"
echo ""
read -p "    Continuer? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo visudo
else
    echo "    ⚠️  Passer cette étape (vous devrez faire sudo manuellement)"
fi

# 6. Variables d'environnement
echo ""
echo "[6] Variables d'environnement"
echo ""
echo "    Créez un fichier .env dans le répertoire du projet avec:"
echo ""
echo "    DYNFW_API_URL=http://127.0.0.1:8000/block"
echo "    DYNFW_API_TOKEN=votre_token_secure"
echo "    DYNFW_LOGFILE=/var/log/auth.log"
echo "    DYNFW_DB=/var/lib/dynfw/dynfw.db"
echo "    DYNFW_THRESHOLD=5"
echo "    DYNFW_WINDOW=300"
echo "    DYNFW_BLOCK_TTL=7200"
echo ""

# Créer un exemple .env
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Configuration du Firewall Dynamique
DYNFW_API_URL=http://127.0.0.1:8000/block
DYNFW_API_TOKEN=change_me_in_production
DYNFW_LOGFILE=/var/log/auth.log
DYNFW_DB=/var/lib/dynfw/dynfw.db
DYNFW_THRESHOLD=5
DYNFW_WINDOW=300
DYNFW_BLOCK_TTL=7200
EOF
    echo "    ✅ Fichier .env créé (à personnaliser)"
fi

echo ""
echo "✅ Configuration terminée!"
echo ""
echo "🚀 Prochaines étapes:"
echo "   1. Éditez les variables d'environnement dans .env"
echo "   2. Exécutez: ./start_firewall.sh"
echo "   3. Consultez: http://127.0.0.1:8000/docs"
echo ""
