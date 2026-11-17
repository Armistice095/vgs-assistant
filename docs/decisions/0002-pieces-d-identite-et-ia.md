# ADR 0002 : Pièces d'identité, interdiction de lecture par l'IA, données envoyées au fournisseur

Statut : **proposé**, règle dure fixée par le chef technique
Date : 2026-11-17

## Contexte

La confidentialité est une promesse commerciale de VGS. Les pièces d'identité (CIP, carte biométrique, acte de naissance) sont les données les plus sensibles du projet. Décision du chef technique : **le modèle ne voit jamais le contenu d'une pièce jointe** (ni vision, ni OCR, ni envoi vers un service d'IA ou un tiers). Le texte des messages part, lui, vers le fournisseur d'IA.

## Décision

### 1. Aucun contenu de fichier ne quitte le serveur

- Les fichiers vont du canal vers le stockage chiffré (voir ADR 0003). Aucune bibliothèque d'OCR, aucun appel de vision, aucun service externe de traitement de fichier.
- Le seul contrôle automatique est **local, sans lire le contenu** : type MIME réel par octets magiques (liste blanche : JPEG, PNG, WebP, HEIC, PDF), taille maximale, rejet des types dangereux (exécutables, archives, documents à macros), détection de doublon par empreinte SHA-256, et, en option, un indicateur de netteté calculé localement sur les images (variance du laplacien). L'indicateur est indicatif : il n'est montré qu'à l'équipe et ne bloque rien. Décoder une image est une lecture de pixels par du code local, pas une lecture par un modèle ; garde-fou contre les « bombes de décompression » (limite de pixels).
- Les PDF ne sont jamais interprétés ni rendus côté serveur.
- Le nom d'origine du fichier peut contenir un nom de personne : il est stocké chiffré et **jamais** transmis au modèle.

### 2. Le modèle fait l'inventaire, l'orchestrateur attribue

1. Le modèle demande les pièces dans l'ordre du catalogue (`request_rank`).
2. À l'arrivée d'un fichier, l'orchestrateur l'attribue à la **pièce attendue courante** : la première pièce demandée encore en état `expected` (ou `to_redo`). La source est « ordre attendu ».
3. Le modèle voit pour chaque fichier un **marqueur sans contenu**, par exemple : `[fichier f3 : image, reçu, attribué à « Acte de naissance » (ordre attendu)]`.
4. Si le client écrit autre chose (« c'est ma carte d'identité »), le modèle appelle l'outil `reassign_document(document_ref, piece_code)`. La source devient « déclaré par le client ». Le client peut corriger autant de fois qu'il veut, par texte.
5. **Rafale** (plusieurs fichiers dans le même tour) : attribution dans l'ordre d'arrivée, `needs_review = true` (« attribution à vérifier »).
6. Plus de fichiers que de pièces attendues : les fichiers en trop restent **non attribués** et le modèle demande au client ce qu'ils sont.
7. Pour un groupe « un parmi N », le fichier occupe d'abord la place du groupe ; la pièce réelle (`requirement_item_id`) est fixée par déclaration du client ou par l'équipe.
8. Chaque attribution est historisée dans `piece_attributions` avec sa source.

### 3. États par pièce et dossier complet

`expected → received → seen_by_team → accepted`, avec `to_redo` (motif obligatoire).
- Le dossier passe en `documents_complete` quand **toutes les pièces requises sont `received`** ou mieux (un groupe « un parmi N » est satisfait avec `min_count` pièces).
- L'équipe est alertée (`dossier_complete`), ouvre les pièces et les vérifie.
- Une pièce `to_redo` déclenche un message du bot au client, avec le **motif saisi par l'équipe** (texte rédigé par un humain, reformulé par le modèle).

### 4. Ce qui part vers le fournisseur d'IA

Part vers le fournisseur : le **texte tapé par le client**, les marqueurs de fichier ci-dessus, et les résultats des outils (libellés du catalogue, montants).

Ne part **jamais** : numéro de téléphone, nom d'affichage du profil, nom de fichier, contenu ou métadonnées de fichier au-delà du type et du statut, identifiants de base de données.

Mesures de minimisation :
- Un **épurateur** de texte (`PromptSanitizer`) remplace avant envoi les suites purement numériques de 9 chiffres ou plus, les adresses e-mail et les motifs ressemblant à un numéro de pièce par un marqueur neutre. L'original reste en base. **C'est une heuristique, pas une garantie** : un numéro tapé dans un format inattendu passera. Les numéros de châssis (alphanumériques, 17 caractères) et les références de plaque ne sont pas masqués, car la TVM en a besoin.
- Le prompt système dit au client : « envoyez la photo de la pièce, inutile d'en écrire le numéro ». Cela réduit la fuite à la source.
- Journaux d'application : jamais de texte de message ; numéros masqués.
- Le résumé de conversation (modèle léger) passe par le même épurateur.

### 5. Conditions de conservation chez le fournisseur (vérifiées le 17/11/2026)

D'après des synthèses publiées en 2026, reprenant la page « privacy center » d'Anthropic datée du 1er juillet 2026 :
- les entrées et sorties de l'API sont **supprimées côté serveur sous 30 jours** par défaut ;
- aucun entraînement sur le contenu client de l'API par défaut (conditions commerciales) ;
- un **contrat de zéro conservation (ZDR)** existe, accordé par organisation, **sur approbation de l'équipe commerciale** d'Anthropic ;
- depuis le 9 juin 2026, les modèles désignés « Covered Models » (famille Fable et Mythos) exigent au moins 30 jours de conservation et ne sont pas disponibles en ZDR sans autorisation expresse ;
- les contenus signalés par les systèmes de sécurité peuvent être conservés **jusqu'à deux ans**, même sous ZDR.

Une des sources mentionne un délai de 7 jours à partir de septembre 2025 ; les sources plus récentes indiquent un retour à 30 jours. Je retiens 30 jours.

**Ce qui n'a pas été vérifié** : je n'ai pas pu ouvrir les pages officielles d'Anthropic ; les chiffres ci-dessus viennent de sources secondaires. Avant la mise en production : relire la page de conservation officielle, signer l'accord de traitement de données (DPA) et confirmer par écrit les conditions applicables au modèle retenu.

Conséquences pour VGS :
- Le texte des messages (donc ce que le client écrit) reste jusqu'à 30 jours chez le fournisseur, à l'étranger, même sans entraînement.
- Le texte de consentement du client doit le dire en clair.
- Si VGS veut le ZDR : démarche commerciale auprès d'Anthropic, et le **modèle de conversation ne doit pas être un Covered Model**.
- Conformité à la réglementation béninoise de protection des données (transfert hors du pays inclus) : **à faire vérifier par un juriste** ; je ne l'affirme pas.

### 6. Accès aux pièces

- Chiffrement par enveloppe : une clé de données par fichier, chiffrée par une clé maître (version portée par `enc_key_id`). Le fichier chiffré est dans R2 ; la clé maître n'est jamais dans la base ni dans R2.
- L'équipe ouvre une pièce via un **lien signé de courte durée** (valeur de départ : 120 s) qui pointe vers l'application. L'application écrit une ligne dans `audit_log` **avant** de servir le fichier, le déchiffre en mémoire, et le sert avec `Content-Disposition`, type fixe et `X-Content-Type-Options: nosniff`.
- Aucune pièce en clair dans les journaux, les messages d'erreur ou les métriques.
- Droit d'accès au rôle `can_view_documents`, désactivé par défaut.

## Conséquences

- **Le bot ne peut pas dire « cette photo est floue » ou « ce n'est pas la bonne pièce ».** C'est l'équipe qui voit les défauts, après coup. Le délai entre l'envoi et le retour client dépend donc de la réactivité humaine. Le message « à refaire » n'arrive qu'après revue.
- Si l'équipe veut un retour immédiat sur la netteté, l'indicateur local peut alimenter un message du bot (« la photo semble floue, pouvez-vous la renvoyer ? ») sans que le modèle voie quoi que ce soit : à décider plus tard.
- Plus de travail humain à la réception, mais une promesse de confidentialité simple à tenir.

## Questions ouvertes

1. **Messages vocaux (étape 7)** : une transcription envoie l'audio à un service tiers, ce qui entre en conflit avec la règle « jamais d'envoi vers un tiers » si les vocaux sont considérés comme des pièces jointes. Proposition : transcription locale (modèle ouvert sur la VM) ou vocaux refusés avec message poli. **Décision attendue avant l'étape 7.**
2. Le prénom du profil WhatsApp peut-il être envoyé au modèle pour saluer ? Par défaut : non.
3. Demande de ZDR : à lancer ou non (décision de l'entrepreneur, selon le coût et le volume).
4. **Paiement fait et pièce refusée** : question métier pour Vigo ; l'ordre « pièces puis paiement » est configurable (`payment_order`).

## Sources

Synthèses 2026 sur la conservation des données de l'API Anthropic : theregister.com (02/09/2026), companyscope.io, humla.team, sondero.ai, getvoibe.com, harriethq.com. À confirmer sur les pages officielles d'Anthropic.
