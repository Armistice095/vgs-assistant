# Plan de l'étape 1 (mis à jour) et impacts sur l'étape 2

Date : 2026-11-17

## 1. Où en est-on

Fait, avant validation (ne dépend pas du schéma) :
- dépôt, `.gitignore`, `.env.example`, `Makefile`, `README` ;
- `apps/core` : `pyproject.toml` (Python 3.12+, ruff, `mypy --strict`, pytest), un test de fumée ;
- `.devcontainer` (Codespaces, avec un Postgres de test dans le conteneur) ;
- `.github/workflows/ci.yml` : lint, types, tests sur Postgres, scan des secrets, et un job Node qui démarre dès que la passerelle existe.

**Vérifié :** `ruff check`, `ruff format --check`, `mypy --strict` et `pytest` passent en local (1 test).
**Non vérifié :** la CI sur GitHub (aucun dépôt distant pour l'instant : les versions des actions sont à confirmer au premier lancement) et le devcontainer dans Codespaces (jamais lancé).

Livré dans ce message : schéma détaillé (`database-schema.md`), ADR 0001 à 0004, ce plan.
Aucune migration, aucun seed et aucune logique métier n'est écrit avant validation.

## 2. Décisions du chef technique et où elles atterrissent

| Décision | Impact |
|---|---|
| Oracle + plan B + reconstruction + état hors machine | ADR 0001 ; `infra/bootstrap.sh`, runbook (étape 2) |
| Cloudflare : sous-domaines, tunnel nommé, Access | ADR 0001 ; QR derrière Access dès l'étape 2 |
| Cœur et passerelle ensemble sur Oracle | ADR 0001 ; test réel hors Codespaces |
| Proposition A rejetée, LLM à chaque tour | ADR 0004 ; garde-fou à l'étape 3 |
| Pièces : le modèle ne voit jamais le contenu | ADR 0002 ; schéma `dossier_pieces`, `documents`, `piece_attributions` |
| Ordre « pièces puis paiement » configurable | `settings.payment_order`, surcharge par procédure, copie figée dans `dossiers` |
| B, C, D, E validées | schéma (`dossier_events`, `quotes`), ADR 0003 (D), évaluations à l'étape 3 |
| Fenêtre de 24 h non infinie pour Baileys | ADR 0003 ; `CHECK > 0`, modèles rendus par le cœur |
| Médias récupérés dès réception | ADR 0003 ; `media_fetch_jobs` |
| Plafond de coût LLM, alerte à 80 % | `settings` + vues `llm_cost_*` ; configuration à l'étape 3 |
| Entrées en brouillon tant que Vigo n'a pas validé | catalogue : `status = draft` ; voir 4.3 |

## 3. Étape 1 : fondations (après validation)

Les migrations sont groupées **par étape** ; seules les tables utiles à l'étape en cours sont créées.

### 3.1 Travail

1. **Configuration typée** (`vgs.config`) : lecture de l'environnement, échec immédiat et explicite si une variable manque hors développement. Le démarrage **refuse** `ALLOW_DRAFT_CATALOG=true` quand `VGS_ENV` vaut `staging` ou `production`.
2. **Journaux structurés** (`vgs.observability`) : identifiant de corrélation, numéros masqués, jamais de texte de message ; test automatique qui échoue si un numéro ou un contenu apparaît dans une sortie de journal.
3. **Migrations Alembic**, révisions de l'étape 1 :
   - R1 : canaux, contacts, conversations, `inbound_events`, `messages`, `message_templates`, `consent_events`.
   - R2 : catalogue versionné (`catalog_versions`, `procedures`, `procedure_variants`, `fee_rules`, `fee_parameter_bands`, `requirement_groups`, `requirement_items`) et `settings`.
   - R3 : `staff_users`, `alerts`, `alert_recipients`, `alert_deliveries`, `audit_log` et triggers d'immuabilité.
   - Étape 2 ajoutera : `media_fetch_jobs`, `documents`. Étape 3 : `dossiers`, `dossier_events`, `dossier_inputs`, `quotes`, `llm_*`. Étape 4 : `dossier_pieces`, `piece_attributions`, `document_access_links`. Étape 5 : paiements.
4. **Seed du catalogue** idempotent, à partir de vos données de départ (voir 4).
5. **Intégration continue complète** : migrations montantes puis descendantes sur Postgres neuf, seed deux fois de suite, tests d'intégration sur vraie base.
6. **Documentation** : `architecture.md`, index des ADR, squelette du runbook.

### 3.2 Critères d'achèvement

- `make check` vert dans un Codespace neuf, sans manipulation manuelle (devcontainer vérifié).
- CI GitHub verte (lint, types, tests, scan des secrets).
- `alembic upgrade head`, puis `downgrade base`, puis `upgrade head` : sans erreur, base vide.
- **Seed idempotent** : deux exécutions donnent exactement le même contenu.
- **Test de conformité des données** : chaque procédure reproduit vos pièces et vos totaux (casier 1 900 + 2 000 = 3 900 ; TVM : frais VGS 3 000, officiel variable ; RCCM en trois variantes 25 000, 52 000, 97 000 ; livraison « à partir de 1 000 »).
- **Test des brouillons** : une entrée `draft` n'est jamais renvoyée par la lecture « utilisable par le bot » en mode production.
- **Test d'immuabilité** : `UPDATE`/`DELETE` refusés sur `dossier_events` (quand elle existe), `audit_log` et `consent_events`.
- **Test de la contrainte Baileys** : un compte `whatsapp_baileys` ne peut pas être marqué `is_production`.
- Aucun secret dans le dépôt (scan en CI) ; `.env.example` complet.
- Documentation initiale relue.

## 4. Données de départ et brouillons

### 4.1 Ce qui est seedé

Vos pièces par démarche et votre grille tarifaire, exactement comme fournies. Rien n'est inventé.

### 4.2 Ce qui reste vide ou à confirmer

- **Table de puissance fiscale de la TVM** : `fee_parameter_bands` reste vide. Un devis TVM est impossible tant que Vigo ne l'a pas fournie ; l'équipe est alertée.
- **Intitulés « C'est moi » et certificat FID** : entrées marquées `draft`.
- **Grille tarifaire** : toutes les `fee_rules` en `draft` jusqu'à validation par Vigo.
- **Livraison** : seul le plancher « à partir de 1 000 » est enregistré ; la grille détaillée viendra de l'entreprise.
- Modèles de message hors fenêtre : aucun, à fournir.

### 4.3 Question pour le chef technique : tester avec des brouillons

Si tout est en `draft`, l'assistant ne cite rien et l'étape 3 devient impossible à tester. Proposition : un drapeau **`ALLOW_DRAFT_CATALOG`**, autorisé seulement en `development` et en tests. Le démarrage échoue s'il est actif en `staging` ou `production`. Les chiffres cités en test sont ceux de la grille de départ, pas des chiffres validés. **À valider.** Sans ce drapeau, l'étape 3 ne pourra s'appuyer que sur des données de test distinctes.

## 5. Impacts sur l'étape 2

Ajouts au plan précédent :
- **Déploiement** (ADR 0001) : passerelle et cœur sur la VM Oracle, unités systemd, `infra/bootstrap.sh`, runbook de reconstruction, exercice de reconstruction à la fin de l'étape.
- **Cloudflare** : tunnel nommé, sous-domaines `api.` et `gw.`, Access sur la page du QR.
- **Fenêtre de 24 h** : testée dès l'écho, y compris le modèle simulé hors fenêtre.
- **Médias** : récupération immédiate par le cœur ; mesure de la durée de disponibilité d'un média Baileys, consignée dans l'ADR 0003.
- **Critères supplémentaires** :
  - un client qui écrit 25 h après son dernier message reçoit le modèle de test, pas du texte libre ;
  - un média redémarré à mi-téléchargement est récupéré après le redémarrage de la passerelle ;
  - un média expiré (simulé) produit `media_expired` sans bloquer la conversation ;
  - la page du QR n'est pas accessible sans Access ;
  - **reconstruction de la VM** réussie, durée mesurée et consignée.

## 6. Risques et points de vigilance

- **Oracle** : compte, capacité, récupération des instances peu utilisées. Couvert par le plan B et la reconstruction.
- **Baileys sur arm64** : dépendances natives à tester sur la machine.
- **Neon** : démarrage à froid de quelques secondes et consommation des heures de calcul par la file d'attente (intervalle d'interrogation à régler).
- **Pièces non lues par le modèle** : plus de charge pour l'équipe, retour client plus lent (ADR 0002).
- **Coût de l'API** : plafond configurable dès l'étape 3 ; budget en attente de l'entrepreneur.
- **Épurateur de texte** : heuristique, pas une garantie (ADR 0002).

## 7. Questions regroupées pour le chef technique

1. Méthode de déploiement : option A (systemd + `git pull`) pour l'étape 2 ? (ADR 0001)
2. Accès SSH à la VM : clé simple limitée ou SSH via tunnel ? (ADR 0001)
3. Drapeau `ALLOW_DRAFT_CATALOG` en développement : accord ? (section 4.3)
4. Message fixe de sécurité en cas d'échec du garde-fou, rédigé par Vigo : accord ? (ADR 0004)
5. Extensions du garde-fou (délais, statuts) : accord ? (ADR 0004)
6. Vocaux (étape 7) : transcription locale ou vocaux refusés ? (ADR 0002)
7. Prénom du profil envoyé au modèle : non par défaut, d'accord ? (ADR 0002)
8. Migrations groupées par étape (section 3.1) : accord ?

Questions pour Vigo (via l'entrepreneur) : paiement fait et pièce refusée, texte des modèles hors fenêtre, textes de consentement, durées de conservation, conservation comptable après anonymisation, demande de ZDR.
