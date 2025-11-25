# 🔥 Firewall Dynamique - Guide de Démarrage Complet

## ✅ Installation et Démarrage

### 1️⃣ **Installation des Dépendances** (une seule fois)

```bash
# Installer iptables
sudo apt update
sudo apt install -y iptables

# Installer Python et les dépendances
sudo apt install -y python3 python3-pip curl

# Installer les paquets Python
pip3 install fastapi uvicorn requests pydantic
```

### 2️⃣ **Démarrer le Firewall** (recommandé: version simple)

```bash
cd /home/mamy/Desktop/Firewall_project
bash start_firewall_simple.sh
```

**Cela va:**
- ✅ Lancer l'API FastAPI (port 8000)
- ✅ Lancer l'auto-learner pour surveiller les logs SSH
- ✅ Afficher les infos de démarrage
- ✅ Créer les répertoires logs

### 3️⃣ **Vérifier que ça fonctionne**

```bash
# Dans un autre terminal
curl http://127.0.0.1:8000/health
```

Vous devriez voir:
```json
{"status":"healthy","timestamp":1234567890}
```

---

## 📊 Consulter les Logs

```bash
# Logs de l'API
tail -f /home/mamy/Desktop/Firewall_project/api/logs/api.log

# Logs de l'auto-learner
tail -f /home/mamy/Desktop/Firewall_project/api/logs/learner.log

# Voir les processus en cours
ps aux | grep firewall
ps aux | grep log_analyzer
```

---

## 🧪 Tester l'API

### Voir les IPs bloquées:
```bash
curl -H "Authorization: Bearer change_me" http://127.0.0.1:8000/list
```

### Bloquer une IP manuellement:
```bash
curl -X POST http://127.0.0.1:8000/block \
  -H "Authorization: Bearer change_me" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.1.100","ttl_seconds":3600,"reason":"test"}'
```

### Débloquer une IP:
```bash
curl -X POST http://127.0.0.1:8000/unblock \
  -H "Authorization: Bearer change_me" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.1.100"}'
```

### Voir la documentation complète:
```
Ouvrez: http://127.0.0.1:8000/docs
```

---

## 🛑 Arrêter le Firewall

```bash
cd /home/mamy/Desktop/Firewall_project
bash stop_firewall.sh
```

---

## ⚙️ Configuration Avancée

### Éditer les variables d'environnement:

```bash
# Créer un fichier .env
cat > /home/mamy/Desktop/Firewall_project/.env << 'EOF'
DYNFW_API_URL=http://127.0.0.1:8000/block
DYNFW_API_TOKEN=votre_token_securise
DYNFW_LOGFILE=/var/log/auth.log
DYNFW_DB=/var/lib/dynfw/dynfw.db
DYNFW_THRESHOLD=5
DYNFW_WINDOW=300
DYNFW_BLOCK_TTL=7200
EOF

# Sourcer le fichier avant de démarrer
source /home/mamy/Desktop/Firewall_project/.env
bash /home/mamy/Desktop/Firewall_project/start_firewall_simple.sh
```

---

## 🔒 Vérifier les Blocs iptables

```bash
# Voir les règles de blocage
sudo iptables -t filter -S DYN_BLOCK

# Voir les IPs bloquées en format lisible
sudo iptables -t filter -L DYN_BLOCK -n

# Voir le nombre de paquets bloqués
sudo iptables -t filter -L DYN_BLOCK -n -v
```

---

## 🐛 Dépannage

### L'API ne démarre pas:
```bash
python3 /home/mamy/Desktop/Firewall_project/api/firewall_api_improved.py
# Regarder les messages d'erreur
```

### L'auto-learner ne démarre pas:
```bash
python3 /home/mamy/Desktop/Firewall_project/api/log_analyzer_improved.py
# Regarder les messages d'erreur
```

### Port 8000 déjà utilisé:
```bash
# Voir quel processus utilise le port
sudo lsof -i :8000

# Tuer le processus
sudo kill -9 <PID>
```

### Pas de permissions sudo:
```bash
# Les commandes iptables nécessitent sudo
# Si vous êtes en root, pas besoin
sudo su
# Puis relancer le script
```

### Le fichier de log SSH n'existe pas:
```bash
# Créer le fichier s'il n'existe pas
sudo touch /var/log/auth.log
```

---

## 📁 Structure du Projet

```
Firewall_project/
├── api/
│   ├── firewall_api_improved.py      # API FastAPI
│   ├── log_analyzer_improved.py      # Auto-learner
│   ├── ipTables_manager_improved.py  # Gestion iptables
│   └── logs/                         # Logs (créé automatiquement)
│       ├── api.log
│       └── learner.log
├── start_firewall_simple.sh          # ✅ Utiliser celui-ci
├── start_firewall.sh                 # Alternative
├── stop_firewall.sh                  # Arrêter
├── setup.sh                          # Configuration
├── GUIDE_DEMARRAGE.md                # Documentation complète
├── AMÉLIORATIONS.md                  # Détail des améliorations
└── .env.example                      # Exemple de config
```

---

## 🚀 Versions des Scripts

### `start_firewall_simple.sh` ✅ RECOMMANDÉ
- Sans interaction sudo
- Plus facile à utiliser
- Idéal pour démarrage manuel

### `start_firewall.sh`
- Version avec gestion sudo
- Plus complète
- À utiliser si vous avez configuré sudo sans mot de passe

### Démarrage Manuel (Alternativif)

Terminal 1:
```bash
cd /home/mamy/Desktop/Firewall_project/api
python3 firewall_api_improved.py
```

Terminal 2:
```bash
cd /home/mamy/Desktop/Firewall_project/api
python3 log_analyzer_improved.py
```

---

## 🎯 Fonctionnement du Firewall

```
┌─────────────────────────────────────────────────────┐
│         /var/log/auth.log (SSH logs)               │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│      log_analyzer_improved.py (Auto-learner)       │
│  - Surveille les tentatives échouées SSH            │
│  - Compte les tentatives par IP                     │
│  - Déclenche blocage si seuil atteint              │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│     firewall_api_improved.py (API FastAPI)          │
│  - Reçoit requête de blocage/déblocage              │
│  - Stocke dans base de données SQLite               │
│  - Envoie commandes iptables                        │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│   ipTables_manager_improved.py (Gestion iptables)  │
│  - Crée chaîne DYN_BLOCK                            │
│  - Ajoute/supprime règles de blocage               │
│  - Gère les IPs bloquées                            │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│          Kernel iptables/Netfilter                  │
│  - Bloque les IPs au niveau réseau                  │
└─────────────────────────────────────────────────────┘
```

---

## 💡 Conseils d'Utilisation

1. **Lancez d'abord l'API**, puis l'auto-learner
2. **Consultez les logs** pour voir ce qui se passe
3. **Testez l'API** avec curl avant utilisation réelle
4. **Gardez les logs affichés** pour le monitoring en temps réel
5. **Changez le token** en production

---

## 🔗 Ressources

- API Docs: http://127.0.0.1:8000/docs (Swagger)
- ReDoc: http://127.0.0.1:8000/redoc
- Health: http://127.0.0.1:8000/health

---

## ✅ Checklist de Démarrage Rapide

- [ ] `iptables` installé (`apt install iptables`)
- [ ] Python 3 et pip3 disponibles
- [ ] Dépendances Python installées (`pip3 install fastapi uvicorn requests pydantic`)
- [ ] `/var/log/auth.log` accessible
- [ ] Firewall lancé avec `bash start_firewall_simple.sh`
- [ ] Vérification: `curl http://127.0.0.1:8000/health` retourne OK
- [ ] Logs consultables: `tail -f api/logs/api.log`

---

**Vous êtes prêt! 🎉 Lancez: `bash start_firewall_simple.sh`**
