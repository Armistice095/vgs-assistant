# Compte rendu de l'étape 1 : fondations

Date : 2026-11-18. Commits : `1ee9214` à `44e4d5e` (5 commits locaux, pas encore de dépôt distant).

## Verdict

**Étape 1 terminée en local, pas encore close** : 3 critères d'achèvement ne peuvent être vérifiés qu'avec des comptes que seul l'entrepreneur peut créer (voir « Reste à vérifier »). Je n'enchaîne pas sur l'étape 2 tant qu'ils ne sont pas vérifiés, sauf le travail non bloquant décrit en bas.

## Ce qui est fait et comment c'est vérifié (résultats réels)

Vérifié sur un Postgres 16 réel, y compris depuis un **clone neuf** du dépôt : `ruff check`, `ruff format --check`, `mypy --strict` (33 fichiers) et **100 tests passent**, 0 ignoré.

| Critère du plan | Résultat |
|---|---|
| Migrations : montée, descente complète, remontée sur base vide | OK, testé sur une base temporaire (21 tables) |
| Seed idempotent (deux exécutions, contenu identique) | OK ; une modification de l'entreprise survit à un nouveau seed |
| Pièces et totaux conformes à vos données | OK : 11 tarifs (dont 3 variantes RCCM) vérifiés un à un ; TVM sans tranche inventée ; pièces du casier, des passeports, du RCCM vérifiées |
| Une entrée en brouillon n'est jamais utilisable en production | OK : 6 tests sur les combinaisons brouillon, confirmé, publié |
| Journaux immuables | OK pour `audit_log` et `consent_events` (modification, suppression, `TRUNCATE` refusés) ; `dossier_events` n'existe pas encore |
| Numéro Baileys jamais en production | OK : contrainte en base **et** refus au démarrage |
| Refus de démarrer avec brouillons en staging/production | OK, testé |
| `.env.example` complet, sans secret | OK, testé ; aucun motif de secret dans les fichiers |
| Documentation | README, architecture, journal des décisions, runbook (squelette), questions pour Vigo |

### Corrections demandées par le chef technique

- **A, texte client** : registre de 48 colonnes de texte libre, test qui échoue si une colonne n'est pas classée, purge du payload brut après traitement, effacement complet. Test avec marqueur : présent uniquement dans les colonnes prévues, **absent de toute la base après effacement** (numéro de téléphone compris), autre client intact. Ce test a trouvé un défaut dans ma propre fixture, corrigé. → ADR 0005.
- **B, clé maître** : outil de génération et de vérification d'empreinte, rotation, restauration d'une pièce après perte de la machine, avec la copie du gestionnaire de mots de passe (testée, et testée impossible sans elle). Étude des gestionnaires gratuits sur documents officiels. → ADR 0006.
- **C** : `documents_first` par défaut, configurable, en place dans le catalogue ; la question à Vigo est posée.

## Décisions prises (ADR)

0005 texte client et effacement · 0006 clé maître · 0007 SSH par le tunnel Cloudflare sans port 22 · 0008 migrations SQL, catalogue en brouillon. L'ADR 0001 est mis à jour avec les chiffres officiels d'Oracle. Écarts entre le schéma validé et les migrations : `database-schema.md`, section 12.

## Reste à vérifier (dépend de l'entrepreneur)

1. **CI GitHub** : jamais lancée (pas de dépôt distant). Versions des actions à confirmer. L'action de scan de secrets peut demander une licence selon le type de compte : à vérifier.
2. **Devcontainer dans Codespaces** : jamais lancé ; il faut le dépôt.
3. **`btree_gist` sur Neon** : fonctionne en Postgres 16 local ; non confirmé sur Neon (sinon, contrôle des chevauchements dans le code).
4. **arm64** : mon environnement est en x86-64 ; rien n'est vérifié sur Arm. Premier test sur la machine Oracle.

## Risques et découverte importante

- **Je ne peux pas joindre la machine Oracle depuis mon environnement** (réseau limité aux registres de paquets et à GitHub). Conséquence pour l'étape 2 : la première installation et le scan du code QR demandent un humain ; ensuite les mises à jour peuvent se faire par `git pull` automatique depuis GitHub, si je peux pousser sur le dépôt (à confirmer quand il existera). Le calendrier de l'étape 2 dépend donc de la disponibilité de l'entrepreneur. (ADR 0007)
- **Oracle** : instance récupérable si l'usage reste sous 20 % pendant 7 jours (officiel) ; couvert par la reconstruction, runbook à tester à l'étape 2.
- **Conservation chez le fournisseur d'IA** : chiffres de l'ADR 0002 toujours de sources secondaires, à ne pas présenter comme confirmés.

## Attendu de l'entrepreneur

`taches-entrepreneur.md`, dans cet ordre : gestionnaire de mots de passe, dépôt GitHub privé, base Neon (ces trois-là clôturent l'étape 1), puis R2, numéro WhatsApp de test, Oracle, tunnel Cloudflare, enfin compte Anthropic avec plafond de dépense.
Questions pour Vigo : `questions-vigo.md` (17 points ; le budget de l'API est en attente depuis le début).

## Travail non bloquant que je peux faire en attendant

Début de l'étape 2 sans comptes externes : schémas JSON du contrat de canal, point d'entrée signé du cœur, adaptateur « console », verrou par conversation et regroupement, module d'envoi avec fenêtre de 24 h, passerelle Node avec tests (sans connexion réelle à WhatsApp).
