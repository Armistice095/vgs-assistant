# Ce que seul l'entrepreneur peut faire

Liste courte et ordonnée. Pour chaque point : à quoi ça sert, ce qu'il faut faire, ce qu'il faut me renvoyer. **Ne jamais envoyer un mot de passe ou une clé par message** : on les range dans le gestionnaire de mots de passe, et on m'indique seulement le nom de l'entrée.

## Avant la fin de l'étape 1 (pour vérifier que tout marche chez vous)

**1. Un gestionnaire de mots de passe** (Bitwarden, gratuit)
- À quoi ça sert : c'est le coffre où vivent toutes les clés du projet, et la copie de secours de la clé qui protège les pièces d'identité. Si la machine disparaît, c'est ce coffre qui permet de tout retrouver.
- À faire : créer un compte, activer la double authentification, créer un espace partagé avec le chef technique.
- Me renvoyer : rien (juste confirmer que c'est fait).

**2. Un dépôt GitHub privé**
- À quoi ça sert : c'est là que le code vit et que les vérifications automatiques tournent à chaque modification.
- À faire : créer un compte GitHub si besoin, puis un dépôt **privé** vide nommé `vgs-assistant` (sans fichier README).
- Me renvoyer : le nom du dépôt (`compte/vgs-assistant`). Le chef technique sait comment m'y donner accès.

**3. Une base de données Neon**
- À quoi ça sert : la base où sont stockés dossiers, messages et catalogue pendant le développement.
- À faire : créer un compte sur neon.com, un projet `vgs-dev`, choisir une région en Europe. Copier la « connection string » en choisissant la connexion **directe** (pas « pooled »).
- Me renvoyer : dans le gestionnaire de mots de passe, une entrée nommée `neon-vgs-dev`. Me donner son nom.

## Avant le test réel de l'étape 2

**4. Un compartiment de stockage R2 (Cloudflare)**
- À quoi ça sert : l'endroit où les photos et scans des clients sont rangés, chiffrés.
- À faire : dans Cloudflare, activer R2, créer un compartiment **privé** nommé `vgs-documents-dev`, puis créer un jeton d'accès limité à ce seul compartiment (lecture et écriture). Cloudflare peut demander un moyen de paiement même pour l'offre gratuite.
- Me renvoyer : dans le gestionnaire de mots de passe, une entrée `r2-vgs-dev` avec l'identifiant de compte, le nom du compartiment, la clé d'accès et la clé secrète.

**5. Un numéro WhatsApp de test**
- À quoi ça sert : le numéro avec lequel on essaie l'assistant pendant le développement. Il peut être banni par WhatsApp : ce ne doit **jamais** être le numéro public de Vigo.
- À faire : une carte SIM dédiée, installer WhatsApp Business dessus, créer le compte.
- Me renvoyer : rien pour l'instant. Le jour du test, quelqu'un devra scanner un code QR avec ce téléphone.

**6. Un compte Oracle Cloud et la machine**
- À quoi ça sert : la machine gratuite qui fait tourner l'assistant pendant le test.
- À faire : créer le compte (une carte bancaire est demandée). **Choisir la région avec soin : elle ne peut plus être changée.** Créer une machine « Ampere A1 » avec 2 cœurs et 12 Go, système Ubuntu. Si Oracle répond « out of capacity », réessayer plus tard ou me le dire : j'ai un plan B (petit serveur payant, quelques dollars par mois).
- Me renvoyer : la région choisie, et la confirmation que la machine existe. L'installation se fera avec un script que je vous fournirai, à coller dans la console de la machine.

**7. Le tunnel Cloudflare et les accès protégés**
- À quoi ça sert : une porte d'entrée sécurisée vers la machine, sans ouvrir aucun port. Elle protège aussi la page du code QR (qui donne le contrôle du compte WhatsApp).
- À faire : dans Cloudflare « Zero Trust », créer un tunnel nommé, créer les adresses `api.`, `gw.` et `ssh.` de votre domaine, et protéger `gw.` et `ssh.` par Cloudflare Access pour vos adresses e-mail. Je fournirai un pas-à-pas illustré à ce moment-là.
- Me renvoyer : le nom de domaine et, dans le gestionnaire de mots de passe, le jeton du tunnel (`cloudflare-tunnel-token`).

## Avant l'étape 3

**8. Un compte pour l'API d'intelligence artificielle (Anthropic)**
- À quoi ça sert : le « cerveau » de l'assistant. Chaque conversation coûte un peu d'argent : ce n'est pas gratuit.
- À faire : créer un compte sur la console Anthropic, **fixer une limite de dépense mensuelle**, créer une clé d'API.
- Me renvoyer : le montant du plafond mensuel choisi (j'applique un second plafond dans le code avec une alerte à 80 %), et l'entrée `anthropic-api-key` dans le gestionnaire de mots de passe.
