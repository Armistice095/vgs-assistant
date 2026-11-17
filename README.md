# VGS Assistant

Assistant IA de relation client pour Vigo Services (WhatsApp, puis Messenger).
Le code et les noms sont en anglais, la documentation en français.

## Démarrage (tout se fait dans le cloud)

1. Ouvrir le dépôt dans GitHub Codespaces. Le devcontainer installe Python, Node, un
   Postgres local de test et les dépendances (`.devcontainer/post-create.sh`).
2. Compléter `.env` (copié depuis `.env.example`). Aucun secret n'entre dans le dépôt.
3. Lancer `make check` : lint, types stricts et tests.

Commandes utiles : `make help`.

## Organisation

- `apps/core` : cœur Python (FastAPI, orchestrateur, agent, dossiers, paiements).
- `apps/gateway-baileys` : passerelle Node (étape 2, développement uniquement).
- `contracts/` : contrat de canal (JSON Schema), source unique Python et Node.
- `docs/` : architecture, journal des décisions (`docs/decisions/`), schéma de base.
- `evals/` : conversations rejouables (à partir de l'étape 3).

## Règles à retenir

- Le modèle d'IA ne voit jamais le contenu d'une pièce jointe (ADR 0002).
- Le numéro Baileys ne sert qu'au développement, jamais au numéro public de VGS.
- Le statut « payé » ne vient que du webhook de l'agrégateur ou d'une validation de l'équipe.
