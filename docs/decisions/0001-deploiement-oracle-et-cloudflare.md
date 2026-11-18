# ADR 0001 : Déploiement sur Oracle Always Free, plan B et accès Cloudflare

Statut : **proposé** (décision du chef technique attendue sur la méthode de déploiement)
Date : 2026-11-17

## Contexte

Le chef technique a validé : passerelle Baileys sur Oracle Always Free, domaine chez Cloudflare avec tunnel nommé, et, pour le test réel de l'étape 2, **cœur et passerelle sur la même machine** (hors Docker local). La base de développement reste Neon. Tout état important doit rester hors de la machine. Il faut un plan B et une reconstruction rapide.

**Vérifié dans la documentation officielle d'Oracle (18/11/2026)** :
- l'offre Arm Always Free est de **2 OCPU et 12 Go** de mémoire au total (une seule instance, ou deux instances de 1 OCPU) ;
- une instance Always Free est jugée **inactive**, et peut être récupérée, si pendant 7 jours : le CPU au 95e centile reste sous 20 %, le réseau sous 20 % et, pour les formats A1, la mémoire sous 20 % (les trois conditions réunies) ;
- la page commerciale indique qu'un compte inactif 30 jours ou plus peut être considéré comme abandonné et suspendu ou supprimé ;
- OCI Vault : voir ADR 0006.

Reste de source tierce, à confirmer à l'ouverture du compte : le manque de capacité (« out of host capacity ») fréquent dans certaines régions, et la carte bancaire exigée.

La passerelle est presque inactive la nuit : le risque de récupération est réel pour elle (un petit service Node et un petit service Python resteront sous 20 % de mémoire sur 12 Go). Il est couvert par la reconstruction rapide plutôt que par un artifice de charge. À l'étape 2 : un contrôle de santé externe et une alerte quand la machine ne répond plus.

## Décision proposée

### 1. Méthode de déploiement : unités systemd (étape 2), conteneurs plus tard

Trois options étudiées :

| Option | Description | Avantages | Inconvénients |
|---|---|---|---|
| **A. systemd + `git pull` (recommandée pour l'étape 2)** | Trois unités : `vgs-core`, `vgs-gateway`, `cloudflared`. Le code vient d'un dépôt cloné avec une clé de déploiement en lecture seule. Script `deploy.sh`. | Peu de pièces mobiles, journaux via journald, reconstruction très simple, adapté à une petite machine Arm | Construction sur la machine (Python via `uv`, Node pinné) ; moins reproductible qu'une image |
| B. systemd + artefacts de la CI | La CI construit une archive (wheel + build Node), la machine la télécharge | Reproductible, rien à compiler sur place | Gestion d'un jeton de téléchargement, plus de mécanique |
| C. Conteneurs (Docker sur la VM, image construite par la CI) | Une image par service | Identique de la CI à la production | Démon Docker à maintenir sur la VM, plus de mémoire, une couche de plus à diagnostiquer |

Recommandation : **A pour l'étape 2** (le but est un test réel fiable, pas l'outillage). On passe à B ou C au moment du choix de l'hébergement de production. Un `Dockerfile` pourra être construit en CI dès que C sera retenue.

Garde-fous communs à toutes les options :
- versions épinglées (`.python-version`, `.nvmrc`, fichiers de verrouillage) ;
- le code est testé sur **arm64** dès l'étape 2 (dépendances natives de la passerelle) ; la CI ne le garantit pas par défaut, donc premier test réel sur la VM ;
- services lancés par un utilisateur système sans privilège, `Restart=always`, limites de ressources.

### 2. Tout l'état important reste hors de la machine

| État | Où |
|---|---|
| Données, file d'attente | Neon (dev) |
| Session Baileys | Postgres, chiffrée (`GATEWAY_AUTH_STATE_KEY`) |
| Pièces | Stockage d'objets (R2), chiffrées par l'application |
| Code, historique | GitHub |
| Configuration du tunnel, DNS, Access | Cloudflare |
| Secrets | Gestionnaire de mots de passe de l'entrepreneur ; fichier `/etc/vgs/*.env` (mode 600) créé à la reconstruction. **Jamais dans le dépôt.** |

Sur la machine, il n'y a rien à sauvegarder. Si elle disparaît, la session WhatsApp survit en base.

### 3. Reconstruction rapide et plan B

- `infra/bootstrap.sh` : script **idempotent** qui installe les paquets, crée l'utilisateur, installe `uv` et Node, clone le dépôt, pose les unités systemd et démarre le tout. Il ne dépend pas du fournisseur.
- `infra/cloud-init.yaml` : lance le script au premier démarrage.
- `docs/runbooks/rebuild-vm.md` : procédure pas à pas, avec la liste des secrets à retaper.
- **Exercice de reconstruction** à la fin de l'étape 2 : détruire la VM, la refaire, mesurer la durée. Objectif de départ : moins de 30 minutes (cible à confirmer par la mesure).
- Plan B : petit VPS Linux classique avec le même script. Le tunnel Cloudflare est sortant : **aucun changement de DNS ni d'adresse** à la bascule. Déclencheurs : capacité Oracle indisponible, carte refusée, ou instance récupérée deux fois.

### 4. Cloudflare : sous-domaines, tunnel nommé, Access

| Sous-domaine | Rôle | Protection |
|---|---|---|
| `api.<domaine>` | Webhooks publics (paiement à l'étape 5, API Cloud WhatsApp plus tard), santé | **Pas d'Access** sur les chemins `/webhooks/*` ; signature vérifiée par l'application. Règles d'entrée du tunnel limitées à ces chemins |
| `gw.<domaine>` | Page du code QR et état de la passerelle | **Cloudflare Access obligatoire** (e-mails nommés). Le QR donne le contrôle du compte WhatsApp : il ne doit jamais être public |
| `admin.<domaine>` | Tableau de bord (étape 6) | Cloudflare Access, plus rôles applicatifs |

- Le cœur et la passerelle **parlent par `127.0.0.1`**, pas par le tunnel. Les ports sont liés à l'adresse locale uniquement. La signature HMAC reste active entre eux, pour que le chemin soit identique à celui de la production (hôtes séparés).
- Le plan gratuit de Cloudflare Access couvre jusqu'à 50 utilisateurs (vérifié lors de la première recherche).
- Le jeton du tunnel vit dans l'environnement de la machine.

## Conséquences

- Aucun Docker local requis. Aucune ouverture de port entrant sur la VM, sauf SSH par clé (à restreindre ; option : SSH via le tunnel).
- Le premier test réel dépend de la création du compte Oracle : l'étape 2 reste réalisable via le plan B.
- Le déploiement manuel (A) est acceptable pour un seul développeur et un seul environnement.

## Questions ouvertes pour le chef technique

1. Valider l'option A pour l'étape 2.
2. Accès SSH à la VM : clé simple limitée par liste d'adresses, ou SSH via tunnel avec Access ?
3. Qui conserve le gestionnaire de mots de passe contenant les secrets (entrepreneur, chef technique, les deux) ?

## Sources

Offre Oracle et récupération des instances : synthèses tierces (snapdeploy.dev, 2026) ; à confirmer sur la documentation Oracle. Cloudflare Tunnel et Access : documentation Cloudflare.
