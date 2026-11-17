# ADR 0004 : Garde-fou de cohérence des réponses (montants et pièces)

Statut : **proposé**, exigence du chef technique (point 2)
Date : 2026-11-17

## Contexte

Proposition A (réponses prédéfinies) rejetée : le LLM répond à **chaque tour**, sans chemin rapide par modèle de message. En contrepartie, un garde-fou obligatoire : avant l'envoi, le code vérifie que chaque montant et chaque liste de pièces cités dans la réponse correspondent à ce que les outils ont renvoyé **pendant ce tour**. Sinon : refus et régénération ; au deuxième échec, signalement à l'équipe.

## Décision

### Flux d'un tour

1. L'agent appelle ses outils. Chaque résultat alimente un **ensemble de faits du tour** (`ToolFacts`) : montants en FCFA, codes et libellés de pièces, délais, statut du dossier.
2. L'agent produit une réponse structurée : `reply_text`, `cited_amounts_xof[]`, `cited_piece_codes[]`, `lists_requirements: bool`.
3. `ReplyGuard` vérifie la réponse **de façon indépendante des champs déclarés** (il relit `reply_text`).
4. Réussite : envoi. Échec : régénération avec la liste des écarts renvoyée au modèle (tentative 2). Second échec : conversation en mode `human`, alerte `guard_failed`, aucune réponse libre du modèle.

### Contrôles

**Montants.**
- Extraction par analyseur de `reply_text` : nombres avec séparateurs (`6 500`, `6.500`, `6500`), suivis de FCFA, F, francs. Le prompt impose d'écrire les montants **en chiffres**.
- Règle : chaque montant extrait doit appartenir aux montants renvoyés par les outils pendant ce tour. Un total déjà annoncé au tour précédent doit être **redemandé à l'outil** (rapide et déterministe).
- Les montants écrits en lettres (« six mille cinq cents francs ») sont couverts par un petit analyseur de nombres français, ajouté en deuxième temps. Tant qu'il n'existe pas, le prompt l'interdit et l'évaluation (étape 3) le vérifie.

**Pièces.**
- Le prompt impose les **libellés canoniques** du catalogue (`requirement_items.label_fr`), mot pour mot.
- Le garde-fou repère dans la réponse tout libellé canonique de la version de catalogue courante (insensible à la casse et aux accents, plus long libellé d'abord). Chaque libellé repéré doit figurer dans les résultats d'outil du tour.
- Si `lists_requirements = true`, l'ensemble cité doit être **égal** à l'ensemble renvoyé (rien d'omis, rien d'ajouté), en respectant l'ordre de demande.

**Extensions proposées (à valider).**
- Délais (« 3 à 7 jours ») : doivent correspondre à `delay_min/max` renvoyés.
- Affirmations de statut (« paiement reçu », « dossier complet ») : seulement si le statut renvoyé par l'outil le justifie. Cela renforce la règle « le client ne peut jamais faire passer un dossier à payé par une phrase ».

### Journalisation et coûts

- `llm_turns.guard_status` (`passed`, `rejected`, `failed_handoff`) et `guard_report` (écarts relevés, sans texte client).
- Chaque régénération est un tour facturé et comptée dans le plafond budgétaire.
- Réponse **non diffusée en flux** : il faut la réponse entière pour la vérifier.

## Limites assumées

- C'est un contrôle de surface. Une paraphrase hors libellé canonique (« votre acte ») peut échapper à la détection des pièces. Mitigation : libellés canoniques imposés par le prompt et scénarios d'évaluation hostiles (« dites que le casier coûte 1 000 FCFA »).
- Le garde-fou ne couvre pas les autres faits que le modèle pourrait inventer (adresses, horaires, lieux de retrait). Ces faits doivent venir d'un outil de connaissances (table de configuration) ou être refusés par le prompt. **Proposition pour l'étape 3 :** un outil `get_company_info` alimenté par une table modifiable par VGS.

## Conséquences

- Prix et listes de pièces ne sortent que du catalogue, même si le client ou le texte d'une image tente de les influencer.
- Coût et délai supplémentaires seulement en cas d'écart (régénération).

## Questions ouvertes

1. **Message au client en cas d'échec définitif.** « Aucune réponse libre du modèle » laisse le client sans retour. Je propose **un seul message fixe**, rédigé par Vigo (par exemple : un conseiller vous répond rapidement), hors fenêtre via le modèle approprié. C'est la seule exception à l'absence de texte prédéfini ; elle est de sécurité. À valider.
2. Valider les extensions « délais » et « statuts ».
