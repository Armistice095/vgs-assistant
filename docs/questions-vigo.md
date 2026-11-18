# Questions pour Vigo Services (portées par l'entrepreneur)

Chaque point indique pourquoi il bloque et ce que je recommande en attendant. Rien n'est inventé : tant que Vigo n'a pas répondu, la valeur reste vide ou en brouillon.

## Tarifs et pièces

1. **Valider la grille tarifaire** (coût officiel, frais VGS, total) : tout est en brouillon. Sans validation, l'assistant n'annonce aucun prix en production.
2. **Table de la puissance fiscale de la TVM** : tranches de puissance et coût officiel correspondant (20 000 à 60 000 FCFA). Sans elle, impossible de chiffrer une TVM.
3. **Intitulés exacts** de la carte « C'est moi » et du certificat FID (acte de naissance sécurisé, à défaut des autres pièces).
4. **Certificat de résidence, variante « attestation fournie par Vigo »** : quelles informations ou pièces le client doit-il fournir dans ce cas ? Aucune n'est enregistrée pour l'instant.
5. **RCCM** : confirmer ma lecture. SARL ou SUARL = les pièces de l'entreprise individuelle plus les statuts, un bordereau de versement **ou** un tableau des apports, et la CIP de chaque associé. SA, SAS, GIE, SCI, SCP = pareil avec statuts notariés et dépôt d'au moins 1/4 du capital (noté comme condition, pas comme pièce).
6. **Certificat de nationalité, Béninois né à l'étranger** : l'assistant passe la main à un conseiller. Faut-il préciser quoi demander avant ?
7. **Délais** : « 3 à 7 jours ouvrables pour la plupart des documents » : lesquels exactement ? Stocké pour l'instant comme délai indicatif global, non confirmé.
8. **Livraison** : grille détaillée des prix (seul le plancher « à partir de 1 000 FCFA » est enregistré).

## Paiement

9. **Paiement avant ou après vérification des pièces ?** Par défaut : les pièces d'abord (`documents_first`), réglable globalement ou par démarche.
10. **Paiement fait et pièce refusée** : que se passe-t-il ? Schéma actuel : le paiement est enregistré, le dossier revient en « pièces à refaire », remboursement manuel.

## Textes

11. **Message d'urgence** envoyé au client si l'assistant échoue deux fois à répondre correctement (texte provisoire de développement autorisé).
12. **Textes des modèles de message hors fenêtre de 24 h** (dossier prêt, pièce à refaire, rappel de paiement) : à fournir, puis à faire approuver par Meta pour la production.
13. **Texte de consentement**. Il doit dire clairement : ce que le client écrit (texte et messages vocaux) est traité par un fournisseur d'intelligence artificielle situé à l'étranger et peut y être conservé jusqu'à 30 jours (chiffre à confirmer) ; les photos des pièces ne sont **jamais** envoyées à ce fournisseur ; comment demander l'effacement.

## Données

14. **Durées de conservation** des pièces et des messages.
15. **Conservation comptable** des montants et des événements de paiement après effacement d'un client.
16. **Souhaitez-vous demander un contrat de « zéro conservation »** auprès du fournisseur d'IA ? Démarche commerciale, avec une contrainte sur le choix du modèle (ADR 0002).
17. **Budget mensuel de l'API d'IA** (en attente depuis le début) : un plafond sera appliqué avec alerte à 80 %.
