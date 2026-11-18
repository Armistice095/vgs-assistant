# ADR 0007 : Accès SSH à la machine par le tunnel Cloudflare, sans port 22 ouvert

Statut : décidé (choix final laissé à l'ingénieur par le chef technique)
Date : 2026-11-18

## Problème

La machine Oracle doit pouvoir être administrée sans exposer le port 22 à Internet (attaques par force brute permanentes, et la machine héberge des pièces d'identité).

## Choix

- **Aucune règle d'entrée** dans le pare-feu Oracle : ni 22, ni 80, ni 443. Tout passe par la connexion **sortante** de `cloudflared`.
- SSH est exposé par le tunnel sur un sous-domaine dédié (`ssh.<domaine>`), protégé par **Cloudflare Access** (accès limité à des adresses e-mail nommées, authentification à usage unique par e-mail, durée de session courte). Le client SSH se connecte avec `cloudflared access ssh` comme commande de proxy.
- Authentification SSH par **clé uniquement**, mot de passe désactivé, connexion root désactivée, un utilisateur d'administration distinct de l'utilisateur des services.
- **Secours** si `cloudflared` ne démarre plus : la console de connexion à l'instance d'Oracle (accès par le navigateur, hors réseau de la machine), puis la reconstruction (runbook). Une reconstruction doit rester plus rapide qu'un dépannage à l'aveugle.

## Raisons

- Surface d'attaque réduite à zéro port entrant.
- Même mécanisme que pour la page du code QR : une seule technologie à comprendre et à surveiller.
- Gratuit : l'offre gratuite de Cloudflare Zero Trust couvre jusqu'à 50 utilisateurs (vérifié lors de la première recherche).

## Inconvénients et points à vérifier au montage (étape 2)

- Dépend de Cloudflare : si le service tombe, plus d'accès distant (secours ci-dessus).
- À vérifier à la mise en place : la façon exacte de déclarer le service SSH dans le tunnel et la politique d'accès, selon la documentation Cloudflare du moment ; la demande éventuelle d'un moyen de paiement à l'activation de Zero Trust.
- **Je n'ai pas moi-même d'accès réseau à la machine** (mon environnement de travail ne peut joindre que les registres de paquets et GitHub). La première installation et les mises à jour passent donc par un script d'amorçage lancé par l'entrepreneur depuis la console d'Oracle, puis par une mise à jour automatique depuis GitHub (ADR 0001, option A). Voir le compte rendu de l'étape.
