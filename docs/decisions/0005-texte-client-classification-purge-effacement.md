# ADR 0005 : Texte client en base : classification, purge des événements bruts, effacement

Statut : décidé (correction A du chef technique)
Date : 2026-11-18

## Problème

Le schéma interdisait les données personnelles dans les journaux techniques, mais `inbound_events.payload` contient le texte des messages et l'identifiant du client. D'autres colonnes peuvent aussi contenir du texte client (`conversations.summary`, `alerts.summary`, le futur `payment_webhook_events.payload`). L'effacement à la demande devait toutes les couvrir, et rien ne garantissait qu'une nouvelle colonne ne laisserait pas passer du texte client.

## Choix

1. **Purge du contenu après traitement.** Le payload brut d'un événement n'est utile que pour le traiter. Il est vidé dès que l'événement est `done` (`mark_inbound_event_done`, même instruction SQL). Les identifiants et statuts restent : ce sont eux qui rendent le traitement idempotent.
   - Événements en échec (`failed`, `dead`) : payload gardé 7 jours pour le diagnostic, puis vidé.
   - Événements bloqués dans un état non final : payload vidé après 2 jours et événement passé en `dead` (filet de sécurité).
2. **Registre de classification** (`vgs.privacy.classification`) : chaque colonne de texte libre (text, json, jsonb, bytea, tableaux, inet) a une classe : `client_data`, `staff_data`, `config` ou `technical`. Les colonnes limitées par un `CHECK` à une liste de valeurs (statuts, types) sont des énumérations et ne peuvent pas contenir de texte.
3. **Le test de schéma échoue** si une colonne de texte libre n'est pas classée, ou si le registre cite une colonne qui n'existe plus. Les colonnes des tables des étapes 2 à 5 sont déjà classées dans `PLANNED` : à la création de la table, le test échoue tant qu'elles ne sont pas déplacées dans le registre.
4. **Effacement** (`erase_contact`), dans la transaction de l'appelant : texte des messages, résumé et motif de la conversation, résumés d'alertes, payloads bruts retrouvés par l'identifiant du client où qu'il apparaisse, nom d'affichage. Le numéro est remplacé par `erased:<id du contact>`, **pas par un hachage** : un hachage d'un numéro de téléphone se retrouve par force brute, l'espace des numéros étant petit. Une ligne d'audit sans contenu est écrite. L'opération est idempotente.
5. **Tables append-only** (`audit_log`, `consent_events`) : elles ne peuvent ni être modifiées ni être effacées, donc elles n'ont que des colonnes `technical` (ids et codes). Le test le vérifie.

## Vérification

- Test avec un marqueur : on le place dans toutes les colonnes `client_data`, on vérifie qu'il n'apparaît **que** là, puis qu'après l'effacement il n'apparaît **nulle part** dans toute la base, y compris le numéro de téléphone. Un autre client n'est pas touché.
- Test de la garde elle-même : un marqueur inséré dans une colonne de configuration est bien signalé comme « hors liste ».
- Ce test a déjà trouvé un défaut dans ma propre fixture (numéro de téléphone dans une clé de déduplication). La règle « la clé de déduplication n'est jamais un identifiant de client » est donc inscrite dans le registre.

## Limites assumées

- Les documents (fichiers et noms chiffrés) ne sont pas encore couverts : la table arrive aux étapes 2 et 4. Leur effacement (objets du stockage inclus) est une condition de fin de l'étape 4.
- Le test ne voit que ce que le code de test écrit. Quand les vrais chemins d'écriture existeront (étapes 2 et 3), un test de bout en bout rejouera le marqueur à travers eux.
- Durées de conservation des messages et des documents : valeurs à fournir par Vigo (stockées `null` dans `settings`, jamais devinées). La conservation comptable des montants après anonymisation est à confirmer.
