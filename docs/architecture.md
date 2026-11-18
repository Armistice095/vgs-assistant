# Architecture

Document vivant : il décrit ce qui existe à la fin de l'étape 1 et ce qui est décidé pour la suite. Les décisions détaillées sont dans `decisions/`, le schéma dans `database-schema.md`.

## Flux

```
Canal (WhatsApp, puis Messenger)
  → passerelle de canal (Node/Baileys en dev ; API Cloud en production)
  → cœur Python : webhook (signature, enregistrement, réponse immédiate)
  → file d'attente (Postgres, derrière une interface)
  → orchestrateur (verrou par conversation, regroupement des messages rapprochés)
  → agent IA avec outils ↔ Postgres
  → module d'envoi (réessais, débit, fenêtre de 24 h) → canal

Agrégateur de paiement → webhook signé → module paiements → statut du dossier
Pièces → pipeline média (récupération immédiate, contrôles locaux, chiffrement) → stockage d'objets
Tableau de bord ↔ API ↔ Postgres
```

## Ce qui existe (étape 1)

| Module (`apps/core/src/vgs`) | Rôle |
|---|---|
| `config` | Configuration typée par variables d'environnement ; refus de démarrer si une règle est violée en staging ou production |
| `observability` | Journaux JSON avec identifiant de corrélation ; numéros, e-mails et champs de contenu masqués ; texte des exceptions jamais journalisé |
| `crypto` | Chiffrement par enveloppe (AES-256-GCM), rotation, outil de clé (`keytool`) |
| `catalog` | Données de départ (`seed_data`), seed idempotent, lecteur unique pour le bot |
| `privacy` | Registre de classification des colonnes, effacement, purge, scan de marqueur |
| `db` | Utilitaires |
| `migrations/` | Alembic, SQL lisible : R1 canaux et conversations, R2 catalogue, R3 alertes et audit |

Pas encore écrits : passerelle, file d'attente, orchestrateur, agent, module d'envoi, dossiers, paiements, tableau de bord.

## Règles qui structurent le code

1. Le webhook répond après avoir vérifié la signature et enregistré l'événement ; le reste est asynchrone.
2. Idempotence : `UNIQUE (canal, compte, clé de déduplication)` sur les événements entrants, `outbound_id` unique sur les envois.
3. Une conversation est traitée par un seul traitement à la fois (verrou consultatif Postgres).
4. L'IA comprend et rédige ; **elle ne décide pas des chiffres**. Prix, pièces, statuts viennent d'outils. Un garde-fou vérifie avant l'envoi que montants et listes de pièces cités viennent des outils du tour (ADR 0004).
5. L'état structuré du dossier est la source de vérité (machine à états, journal d'événements). L'historique de messages ne sert qu'au ton.
6. Le modèle ne voit **jamais** le contenu d'une pièce jointe (ADR 0002).
7. Seul le webhook de l'agrégateur ou l'équipe peut poser « payé ».
8. La fenêtre de réponse de 24 h est appliquée dans le cœur, jamais infinie, même avec Baileys (ADR 0003).
9. Le cœur ne connaît aucun détail d'un canal : changer de canal est un changement de configuration.

## Données personnelles

Quatre classes de colonnes (`client_data`, `staff_data`, `config`, `technical`), contrôlées par un test contre le schéma réel (ADR 0005). Les journaux applicatifs ne contiennent ni texte client ni numéro. Les journaux en base `audit_log` et `consent_events` sont immuables (déclencheurs) et n'ont que des colonnes techniques.

## Environnements

| Rôle | Où |
|---|---|
| Développement et tests | GitHub Codespaces (cloud), Postgres de test dans le conteneur |
| Base de développement | Neon |
| Pièces | Cloudflare R2, chiffrées par l'application |
| Test réel et exécution | VM Oracle Always Free : cœur et passerelle ensemble (ADR 0001) |
| Intégration continue | GitHub Actions (Postgres en service) |
