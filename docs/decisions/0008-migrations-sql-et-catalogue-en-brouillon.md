# ADR 0008 : Migrations en SQL, catalogue semé en brouillon, drapeau de développement

Statut : décidé
Date : 2026-11-18

## Problèmes et choix

**1. Comment écrire les migrations.** Le schéma utilise des fonctionnalités propres à Postgres (contrainte d'exclusion sur des intervalles, index uniques partiels, `UNIQUE NULLS NOT DISTINCT`, déclencheurs d'immuabilité). Les décrire avec un modèle objet masquerait ce qui est réellement créé.
Choix : Alembic gère l'ordre et l'historique ; le contenu de chaque révision est un fichier SQL lisible (`migrations/sql/NNNN_up.sql` et `_down.sql`). Révisions groupées par étape (R1 canaux, R2 catalogue, R3 alertes et audit). Test : montée, descente complète, remontée sur une base neuve.

**2. Accès aux données.** Les tests et le seed utilisent `psycopg` directement ; SQLAlchemy sera utilisé pour les couches de service des étapes suivantes si le besoin se confirme. Raison : pas de couche d'abstraction tant qu'elle n'apporte rien.

**3. Le seed du catalogue ne doit jamais écraser le travail de l'entreprise.** Il n'insère que si la version 1 n'existe pas ; réglages et modèles : `ON CONFLICT DO NOTHING`. Testé : une modification faite depuis le tableau de bord survit à un nouveau seed.

**4. Tout le catalogue est semé en brouillon**, version comprise (`draft`, non publiée). Raison : le chef technique a demandé que la grille et la table de la puissance fiscale restent en brouillon jusqu'à validation par Vigo, et la liste des pièces est une valeur de départ non validée elle aussi. Rien n'est inventé : la table de puissance fiscale de la TVM est **vide**, le délai « 3 à 7 jours » est un réglage global indicatif non confirmé (la source dit « la plupart des documents » sans les nommer), les durées de conservation et le budget sont `null`.

**5. Un seul point d'accès au catalogue pour le bot** (`vgs.catalog.reader`) : en production seules les entrées confirmées de la version **publiée** sont visibles ; une procédure confirmée mais dont le prix est en brouillon est listable, mais le prix n'est pas citable (→ alerte à l'équipe). Six tests couvrent les combinaisons.

**6. Drapeau `ALLOW_DRAFT_CATALOG`** (validé par le chef technique) : élargit la lecture à la dernière version, brouillons compris. Le démarrage échoue s'il est actif en `staging` ou `production`. Le chiffre cité en test est celui de la grille de départ, jamais un chiffre validé.

**7. Le numéro Baileys ne peut jamais être déclaré en production** : contrainte `CHECK` en base **et** refus au démarrage de `CHANNEL_ADAPTER=whatsapp_baileys` en production.

## Conséquence

Avant la mise en ligne, Vigo valide la grille et les pièces depuis le tableau de bord (étape 6), puis publie une version. D'ici là, l'assistant n'annonce aucun prix de production.
