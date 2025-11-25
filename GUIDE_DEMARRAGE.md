# Guide de Démarrage - Firewall Dynamique

## 🚀 Démarrage Rapide (3 étapes)

### 1️⃣ Configuration Initiale
```bash
cd /home/mamy/Desktop/Firewall_project
bash setup.sh
```

Cela va:
- ✅ Créer les répertoires nécessaires
- ✅ Installer les dépendances Python (fastapi, uvicorn, requests)
- ✅ Rendre les scripts exécutables
- ✅ Vérifier iptables

### 2️⃣ Configurer les Variables d'Environnement
```bash
nano .env
```

Modifier au besoin:
```env
DYNFW_API_URL=http://127.0.0.1:8000/block
DYNFW_API_TOKEN=votre_token_secure
DYNFW_LOGFILE=/var/log/auth.log
DYNFW_DB=/var/lib/dynfw/dynfw.db
DYNFW_THRESHOLD=5          # Nombre de tentatives avant blocage
DYNFW_WINDOW=300           # Fenêtre de temps en secondes
DYNFW_BLOCK_TTL=7200       # Durée du blocage en secondes (2 heures)
```

### 3️⃣ Démarrer le Firewall
```bash
bash start_firewall.sh
```

Vous verrez:
```
🚀 Démarrage du Firewall Dynamique...
✅ Configuration:
   API URL: http://127.0.0.1:8000/block
   Log File: /var/log/auth.log
   DB Path: /var/lib/dynfw/dynfw.db
   ...
✅ Firewall Dynamique démarré avec succès!
```

---

## 📚 Détail du Démarrage

### Composants lancés:

#### 1. **API FastAPI** (firewall_api_improved.py)
```
Port: 8000
Endpoints:
  - POST /block         → Bloquer une IP
  - POST /unblock       → Débloquer une IP
  - GET /list           → Lister les IPs bloquées
  - POST /cleanup       → Nettoyer les blocs expirés
  - GET /health         → Vérifier la santé de l'API
  - GET /docs           → Documentation Swagger

Docs: http://127.0.0.1:8000/docs
ReDoc: http://127.0.0.1:8000/redoc
```

#### 2. **Auto-Learner** (log_analyzer_improved.py)
```
Fonction: Analyser les logs SSH en temps réel
Recherche: Tentatives échouées dans /var/log/auth.log
Action: Si seuil atteint → appel API /block
```

---

## 🔧 Configuration Sudo (Important!)

Le firewall a besoin de droits sudo pour iptables. Configurez sudo sans mot de passe:

```bash
sudo visudo
```

Allez à la fin du fichier et ajoutez:
```
# Autoriser l'utilisateur à utiliser iptables sans mot de passe
your_username ALL=(ALL) NOPASSWD: /usr/sbin/iptables
```

**Remplacez `your_username` par votre nom d'utilisateur.**

---

## 📊 Vérifier l'État

### Consulter les logs:
```bash
# Logs de l'API
tail -f api/logs/api.log

# Logs de l'auto-learner
tail -f api/logs/learner.log

# Logs système
tail -f /var/log/syslog | grep dynfw
```

### Vérifier les processus:
```bash
ps aux | grep firewall_api
ps aux | grep log_analyzer
```

### Tester l'API:
```bash
# Vérifier la santé
curl http://127.0.0.1:8000/health

# Lister les IPs bloquées (remplacer TOKEN)
curl -H "Authorization: Bearer change_me" http://127.0.0.1:8000/list

# Bloquer une IP
curl -X POST http://127.0.0.1:8000/block \
  -H "Authorization: Bearer change_me" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.1.100","ttl_seconds":3600,"reason":"test"}'

# Débloquer une IP
curl -X POST http://127.0.0.1:8000/unblock \
  -H "Authorization: Bearer change_me" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.1.100"}'
```

### Vérifier les blocs iptables:
```bash
# Voir les règles de blocage
sudo iptables -t filter -S DYN_BLOCK

# Voir les IPs bloquées
sudo iptables -t filter -L DYN_BLOCK -n
```

---

## 🛑 Arrêter le Firewall

```bash
bash stop_firewall.sh
```

Cela va:
- ✅ Arrêter l'API FastAPI
- ✅ Arrêter l'auto-learner
- ✅ Garder les règles iptables en place

---

## ⚙️ Mode Manuel

Si vous préférez démarrer manuellement:

### Terminal 1 - Démarrer l'API:
```bash
cd /home/mamy/Desktop/Firewall_project/api
python3 firewall_api_improved.py
```

### Terminal 2 - Démarrer l'auto-learner:
```bash
export DYNFW_API_URL="http://127.0.0.1:8000/block"
export DYNFW_API_TOKEN="change_me"
export DYNFW_LOGFILE="/var/log/auth.log"

cd /home/mamy/Desktop/Firewall_project/api
python3 log_analyzer_improved.py
```

---

## 🔒 Mode Systemd (Production)

Pour un démarrage automatique au boot, créez un service systemd:

### 1. Créer le fichier de service:
```bash
sudo tee /etc/systemd/system/dynfw.service > /dev/null << 'EOF'
[Unit]
Description=Dynamic Firewall Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/mamy/Desktop/Firewall_project
EnvironmentFile=/home/mamy/Desktop/Firewall_project/.env
ExecStart=/bin/bash /home/mamy/Desktop/Firewall_project/start_firewall.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 2. Activer et démarrer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dynfw
sudo systemctl start dynfw
```

### 3. Vérifier le statut:
```bash
sudo systemctl status dynfw
```

---

## 🐛 Dépannage

### L'API ne démarre pas:
```bash
python3 api/firewall_api_improved.py
# Vérifier les messages d'erreur
```

### L'auto-learner ne démarre pas:
```bash
python3 api/log_analyzer_improved.py
# Vérifier les messages d'erreur
```

### Erreur de permission sudo:
```bash
# Vérifier les permissions sudo
sudo -l | grep iptables

# Reconfigurer si nécessaire
sudo visudo
```

### Le fichier de log n'existe pas:
```bash
# Créer le fichier de log SSH
sudo touch /var/log/auth.log
sudo chmod 644 /var/log/auth.log
```

### Port 8000 déjà utilisé:
```bash
# Trouver quel processus utilise le port
sudo lsof -i :8000

# Tuer le processus
sudo kill -9 <PID>
```

---

## 📝 Notes Importantes

1. **Token d'authentification**: Changez `change_me` par un token sécurisé en production
2. **Permissions sudo**: Sans sudo configuré, le firewall ne fonctionnera pas
3. **Fichier de log SSH**: Le path dépend de votre configuration
4. **Sauvegardes DB**: La base de données SQLite est en `/var/lib/dynfw/dynfw.db`
5. **Nettoyage**: Les blocs expirés sont automatiquement nettoyés via l'endpoint `/cleanup`

---

## ✅ Checklist de Démarrage

- [ ] Dépendances Python installées
- [ ] Permissions sudo configurées pour iptables
- [ ] Variables d'environnement définies dans `.env`
- [ ] Répertoire `/var/lib/dynfw` créé
- [ ] Fichier `/var/log/auth.log` accessible
- [ ] Firewall démarré avec `./start_firewall.sh`
- [ ] API répond sur `http://127.0.0.1:8000/health`
- [ ] Auto-learner en cours d'exécution
- [ ] Logs consultables en temps réel

---

**Besoin d'aide?** Consultez les logs pour plus de détails! 📊
