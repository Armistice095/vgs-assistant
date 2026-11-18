# ADR 0006 : Clé maître de chiffrement : sauvegarde, rotation, compromission de la machine

Statut : décidé pour l'étape 1 à 2 ; l'hébergement de production sera revu à la décision de production
Date : 2026-11-18

## Problème

Les pièces sont chiffrées par enveloppe (une clé de données par fichier, enveloppée par une clé maître). Si la clé maître n'existe qu'à un endroit, deux risques : la machine est perdue et toutes les pièces deviennent illisibles, ou la machine est compromise et la clé fuit avec elle.

## Étude d'un gestionnaire de clés gratuit

| Option | Ce qui est vérifié | Verdict |
|---|---|---|
| **OCI Vault (Oracle)** | Documentation officielle d'Oracle : les clés de chiffrement protégées par logiciel sont gratuites sans limite ; 20 versions de clés protégées par HSM et 150 secrets sont inclus dans « Always Free » ; les coffres privés virtuels ne sont pas inclus ; 40 versions par secret | **Utilisable comme coffre de secrets**, pas comme détenteur de la clé (voir ci-dessous) |
| **Infisical (offre gratuite)** | Page officielle : 5 identités, 3 environnements par projet, pas de versions de secrets, pas de rotation, pas de rétention de journal d'audit ; pas d'option autohébergée gratuite listée | Écarté : une dépendance de plus chez un tiers, sans versions ni audit |
| Autres (Cloudflare Secrets Store, etc.) | **Non évalués** | Pas de recommandation |

Pourquoi OCI Vault comme **secret** et non comme **clé gérée** : une clé maître gérée par Vault ne peut pas être exportée. Si le compte Oracle est suspendu (la page commerciale d'Oracle indique qu'un compte inactif 30 jours peut être considéré comme abandonné) ou supprimé, toutes les pièces seraient perdues sans recours. Garder la clé comme valeur que **nous** contrôlons permet la sauvegarde hors d'Oracle.

## Choix

1. **Une clé générée par nous**, 32 octets aléatoires (`python -m vgs.crypto.keytool generate v1`). Elle est affichée une seule fois et n'est écrite nulle part automatiquement.
2. **Au moins deux exemplaires, jamais sur la même machine** :
   - exemplaire de service : variable d'environnement `MASTER_KEY_B64` du processus, fichier `/etc/vgs/core.env` en mode 600 (étapes 1 et 2 : développement et test) ;
   - exemplaire de sauvegarde : gestionnaire de mots de passe de l'entrepreneur, avec l'identifiant de la clé et son empreinte.
3. **Vérification sans révéler la clé** : `keytool fingerprint` donne une empreinte de 8 caractères ; `keytool verify <copie>` confirme que la copie sauvegardée correspond à la clé utilisée. À faire à la création, puis à chaque rotation.
4. **Rotation** : générer `v2`, mettre `MASTER_KEY_ID=v2`, ancienne clé dans `MASTER_KEYS_RETIRED_JSON`, redémarrer (les anciennes pièces restent lisibles), exécuter la tâche de réenveloppement (seules les clés de données sont rechiffrées, jamais les fichiers), puis retirer l'ancienne clé de la configuration. Testé : lecture avant et après réenveloppement, fichier stocké inchangé, ancienne clé inutile ensuite. La tâche de réenveloppement de la table des documents sera écrite avec cette table.
5. **Restauration après reconstruction de la machine** : testée (`test_vm_rebuild_restores...`) : seuls survivent les objets chiffrés, les lignes de base et la copie du gestionnaire de mots de passe ; une pièce est relue. Sans la copie, la pièce est irrécupérable (testé aussi). Le même exercice sera joué sur la vraie machine à la fin de l'étape 2 (runbook).
6. **Production** : revoir à la décision de production s'il faut lire la clé depuis un secret OCI Vault au démarrage (instance principal limité à ce seul secret). Gain réel : la clé n'est plus sur le disque de la machine, journal d'accès, révocation centralisée. Gain limité : quelqu'un qui contrôle la machine peut toujours demander le secret. L'interface `KeyProvider` permet ce changement sans toucher au reste.

## Risque : la machine est compromise

Quelqu'un qui contrôle la machine peut lire la clé dans la mémoire du processus et les accès de service (stockage, base). **Le chiffrement ne protège pas contre ce cas.** Il protège contre : une fuite du stockage ou de la base, une sauvegarde perdue, un accès du fournisseur de stockage.

Réduction du risque (déjà décidée ailleurs) : aucun port entrant, accès par tunnel avec authentification (ADR 0007), services sans privilège, clés de service au moindre privilège (jeton de stockage limité au seul bucket, rôle de base sans droit de modifier les journaux), liens de pièces de 120 secondes, audit de chaque ouverture, alerte sur un volume d'accès anormal (à construire à l'étape 6).

Si la compromission est avérée : (1) couper le tunnel et arrêter les services, (2) révoquer le jeton de stockage et changer le mot de passe de la base, (3) **générer une nouvelle clé et rechiffrer entièrement les fichiers** (nouvelles clés de données). Réenvelopper ne suffit pas : l'ancienne clé volée déchiffrerait les clés de données déjà copiées. (4) Informer Vigo : notification possible à l'autorité de protection des données selon la réglementation, à faire confirmer par un juriste. Cette procédure est une action irréversible et reste soumise à validation du chef technique et de Vigo (cas e du cadre).

## Limites

- Les fichiers sont chiffrés d'un seul bloc en mémoire : adapté à des fichiers de quelques dizaines de Mo (plafond de départ 20 Mo). Au-delà, il faudrait un chiffrement par flux.
- Le test de restauration sur de vrais objets R2 est reporté à l'étape 2, quand le stockage sera branché.
- Les limites d'Oracle citées viennent de la documentation officielle consultée le 18/11/2026 ; elles peuvent changer.
