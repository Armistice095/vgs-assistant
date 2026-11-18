# Reconstruire la machine (squelette, à compléter à l'étape 2)

Objectif : refaire la machine de zéro en moins de 30 minutes (cible à confirmer par la mesure). Rien d'important ne vit sur la machine : la base est chez Neon, les pièces chez R2, le code sur GitHub, la configuration du tunnel et des accès chez Cloudflare.

## Ce qu'il faut avoir sous la main (gestionnaire de mots de passe)

- Le fichier d'environnement du cœur (`core.env`) : adresse de la base, clés du stockage, **clé maître** et son identifiant, secret de signature canal, clé de l'API d'IA.
- Le fichier d'environnement de la passerelle (`gateway.env`) : clé de chiffrement de la session WhatsApp.
- Le jeton du tunnel Cloudflare.
- La clé de déploiement GitHub (lecture seule).

## Étapes (à écrire et tester avec `infra/bootstrap.sh`)

1. Créer la machine (Oracle ; sinon plan B : petit VPS Linux, même script).
2. Coller le script d'amorçage dans la console de la machine.
3. Déposer les fichiers d'environnement (mode 600).
4. Démarrer les services : cœur, passerelle, tunnel.
5. Vérifier : page de santé, reconnexion WhatsApp **sans nouveau code QR** (la session est en base).
6. Vérifier la restauration d'une pièce de test avec la clé maître sauvegardée (`keytool fingerprint` doit donner l'empreinte notée dans le gestionnaire).

## Exercice

À la fin de l'étape 2 : détruire la machine, la refaire avec cette procédure, noter la durée et ce qui a manqué, corriger ce document.
