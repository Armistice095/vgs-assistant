# ADR 0003 : Contrat de canal, fenêtre de 24 heures configurable et récupération des médias

Statut : **proposé**, ajustements demandés par le chef technique (point 5)
Date : 2026-11-17

## Contexte

Le contrat de canal v1 (première livraison) doit changer sur deux points : la fenêtre de 24 heures ne doit pas être infinie pour Baileys, et les médias WhatsApp expirent, donc le cœur doit les récupérer tout de suite.

## Décision

### 1. Fenêtre de réponse configurable, jamais infinie

- `channel_accounts.reply_window_hours`, valeur de départ **24**, `CHECK > 0`. Réglage par défaut dans `REPLY_WINDOW_HOURS`.
- La règle vit dans le **cœur** (module d'envoi) : si `now - conversations.last_inbound_at <= fenêtre`, texte libre autorisé ; sinon, **modèle de message** obligatoire. Le calcul utilise une horloge injectable pour pouvoir tester le passage à 25 heures sans attendre.
- L'adaptateur Baileys déclare `capabilities.reply_window_hours = 24`, comme l'API Cloud. Le chemin « hors fenêtre » est donc exercé dès le développement.
- Le cœur **refuse** d'envoyer du texte libre hors fenêtre : erreur `window_closed` testée.

### 2. Modèles de message : le cœur rend le texte, l'adaptateur l'envoie

Baileys ne connaît pas les modèles approuvés par Meta. Le chef technique demande de les simuler par un texte tiré d'un registre. Pour garder la passerelle sans logique métier (décision D), **le cœur résout et rend le modèle** avant l'envoi :

```jsonc
"content": {
  "kind": "template",
  "template": {
    "name": "dossier_pret",          // clé du registre message_templates
    "language": "fr",
    "params": ["…"],
    "rendered_text": "…"             // texte déjà rendu par le cœur
  }
}
```
- L'adaptateur Baileys envoie `rendered_text`.
- L'adaptateur Cloud enverra le modèle natif (`name`, `language`, `params`) et ignorera `rendered_text`.
- Le registre `message_templates` porte `meta_status` (`local`, `submitted`, `approved`, `rejected`). En production, seuls les modèles `approved` sont utilisables.
- **L'IA ne rédige pas ces messages** : un événement (dossier prêt, pièce à refaire, rappel de paiement) est associé à un modèle du registre. S'il n'existe aucun modèle adapté hors fenêtre, le message n'est pas envoyé et l'équipe est alertée.
- Contenu des modèles : à fournir par Vigo. Je n'en invente aucun. À l'étape 2 un seul modèle de test, marqué `local`.

### 3. Récupération immédiate des médias

Données vérifiées dans la documentation de Meta (API Cloud) :
- l'URL de téléchargement expire **après 5 minutes** et doit être redemandée ;
- l'identifiant d'un média reçu par webhook n'est téléchargeable que **7 jours** ;
- plafonds de taille : image 5 Mo, document 100 Mo, audio 16 Mo, vidéo 16 Mo.

Pour Baileys, la durée de disponibilité d'un média sur les serveurs WhatsApp n'est pas documentée : **je la mesure à l'étape 2** et je la consigne ici.

Fonctionnement :
1. À réception d'un message avec média, le cœur enregistre l'événement (réponse 200 immédiate) et crée un `media_fetch_job` **dans la même transaction**.
2. Un worker récupère le fichier via l'adaptateur (`MediaFetcher.fetch(media_ref)`, flux), calcule le SHA-256, vérifie la taille et le type réel, chiffre, puis stocke (ADR 0002).
3. Cloud : l'adaptateur redemande l'URL à chaque tentative. Baileys : la passerelle conserve, dans son outbox chiffrée en base, ce qu'il faut pour retélécharger (clé du message, clé média) ; un redémarrage ne perd donc pas le média.
4. Erreurs classées : `transient` (réessai), `expired` (définitif), `too_large`, `forbidden_type`, `forbidden` (jeton). Reprise avec délais croissants ; échéance `deadline_at` configurable (valeurs de départ : hypothèses, à mesurer).
5. **Média expiré ou échec définitif** : `documents.status = media_expired` (ou `failed`), la pièce reste `expected`, le modèle reçoit un résultat d'outil `media_unavailable` et demande au client de renvoyer. L'équipe est alertée si l'échec se répète.
6. Le tour de l'assistant **attend l'issue des jobs** (délai maximal configurable) avant de répondre, pour ne jamais annoncer « bien reçu » avant que le fichier soit stocké.

Le module média devient : **réception, vérification locale (MIME, taille, doublon), chiffrement, stockage. Sans vision.**

### 4. Changements du contrat v1 (devient v1.1)

| Élément | Avant | Maintenant |
|---|---|---|
| `capabilities.reply_window_hours` | 24 pour Cloud, infini pour Baileys | 24 pour les deux, configurable |
| `content.template.rendered_text` | absent | ajouté, rendu par le cœur |
| Erreur de récupération de média | non définie | `transient`, `expired`, `too_large`, `forbidden_type`, `forbidden` |
| `media.media_ref` | opaque | opaque, **doit rester résoluble après redémarrage** de la passerelle |
| Cadre de réception | message seul | message + `media_fetch_job` créé dans la même transaction |

## Tests

- Contrat (Python et Node, mêmes JSON Schema) : modèle avec `rendered_text`, erreurs de média.
- Fenêtre : client à 23 h 59 (texte libre accepté), à 24 h 01 (modèle obligatoire, texte libre refusé), fenêtre modifiée par configuration.
- Média : récupération immédiate, URL expirée puis renouvelée (Cloud, simulé), média définitivement expiré, fichier trop gros, type refusé, doublon, redémarrage de la passerelle pendant un téléchargement.

## Questions ouvertes

1. Texte des modèles hors fenêtre : à fournir par Vigo (dossier prêt, pièce à refaire, rappel de paiement…).
2. Plafond de taille du cœur : valeur de départ proposée 20 Mo, configurable (hypothèse).

## Sources

Documentation WhatsApp Business Platform (Meta), pages « Media » (mises à jour avril et juin 2026).
