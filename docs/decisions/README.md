# Journal des décisions (ADR)

Un ADR est court : problème, choix, raison. Les décisions verrouillées par le chef technique ne se changent pas sans lui ; tout le reste est décidé par l'ingénieur et consigné ici.

| N° | Titre | Statut |
|---|---|---|
| 0001 | Déploiement sur Oracle Always Free, plan B et accès Cloudflare | validé (option A : systemd + `git pull`) |
| 0002 | Pièces d'identité, interdiction de lecture par l'IA, données envoyées au fournisseur | règle dure ; chiffres de conservation d'Anthropic **non confirmés** (sources secondaires) |
| 0003 | Contrat de canal, fenêtre de 24 heures configurable et médias | validé |
| 0004 | Garde-fou de cohérence des réponses | validé, extensions comprises |
| 0005 | Texte client en base : classification, purge, effacement | décidé |
| 0006 | Clé maître de chiffrement | décidé (étapes 1 à 2) |
| 0007 | Accès SSH par le tunnel Cloudflare | décidé |
| 0008 | Migrations SQL, catalogue en brouillon, drapeau de développement | décidé |

À venir : vocaux (avant l'étape 7), agrégateur de paiement (étape 5), base de production (avant la mise en production).
