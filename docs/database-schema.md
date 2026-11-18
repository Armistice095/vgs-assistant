# Schéma de base de données (étapes 1 à 5)

Statut : **proposition, en attente de validation**. Aucune migration n'est écrite avant accord.

## Conventions

- Postgres 16, accès SQLAlchemy 2.x, migrations Alembic.
- Clés primaires `uuid` générées par l'application (UUIDv7, triables dans le temps). Exceptions : tables de journal (`bigint identity`).
- Horodatages `timestamptz` en UTC. Colonnes `created_at` partout, `updated_at` sur les tables modifiables.
- Montants en **entiers FCFA** (`*_xof integer`), jamais de décimaux. Contrainte `>= 0`.
- Énumérations en `text` + contrainte `CHECK` (plus simple à migrer qu'un type `ENUM`).
- Suppression : pas de `ON DELETE CASCADE` sur les données métier. L'effacement d'un client passe par une procédure d'anonymisation (section 9), pas par un `DELETE` en cascade.
- Aucune donnée personnelle dans les colonnes `meta`/`payload` des journaux techniques (règle vérifiée par test).
- Extension requise : `btree_gist` (contrainte d'exclusion sur `fee_parameter_bands`). Les contraintes suivantes ont été testées sur un Postgres 16 local : exclusion des tranches qui se chevauchent, version de catalogue publiée unique, `CHECK` du total d'un devis, immuabilité par trigger, `CHECK` du numéro Baileys. **Non vérifié : la disponibilité de `btree_gist` sur Neon** (à confirmer à la première migration ; sinon, contrôle des chevauchements dans le code).
- La file d'attente utilise ses propres tables (bibliothèque type procrastinate, gérées par ses migrations), derrière l'interface `queue/`. Elles ne figurent pas ici.

## Vue d'ensemble des relations

```
channel_accounts 1─n contacts 1─1 conversations 1─n messages
                                      │               │
                                      │               └─ n─1 documents (pièce jointe)
                                      └─ 1─n dossiers ─ n─1 procedures (version de catalogue)
dossiers 1─n dossier_pieces 1─n piece_attributions ─ n─1 documents
dossiers 1─n quotes · 1─n payment_attempts · 1─n payments · 1─n dossier_events
conversations 1─n llm_turns 1─n llm_tool_calls
alerts 1─n alert_deliveries ─ n─1 alert_recipients
catalog_versions 1─n procedures 1─n (variants, fee_rules, requirement_groups 1─n requirement_items)
```

## 1. Canaux, contacts, conversations

### `channel_accounts`
Un numéro ou une page que VGS exploite.
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| channel | text | `whatsapp_baileys`, `whatsapp_cloud`, `messenger`, `console` |
| external_account_id | text | numéro ou identifiant de page |
| label | text | |
| is_production | bool | défaut `false` |
| reply_window_hours | int | défaut 24, `CHECK (reply_window_hours > 0)` (jamais infini) |
| created_at | timestamptz | |

Contraintes : `UNIQUE (channel, external_account_id)` ; `CHECK (channel <> 'whatsapp_baileys' OR is_production = false)` (le numéro Baileys ne peut jamais être déclaré en production).

### `contacts`
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| channel_account_id | uuid FK | |
| channel_contact_id | text | E.164 ou PSID. **Masqué dans tous les journaux.** |
| display_name | text null | |
| consent_status | text | `unknown`, `granted`, `refused`, `withdrawn` |
| consent_text_version | text null | version du texte accepté |
| consent_at | timestamptz null | |
| erasure_requested_at | timestamptz null | |
| anonymized_at | timestamptz null | |
| created_at | timestamptz | |

Contraintes : `UNIQUE (channel_account_id, channel_contact_id)`.

### `consent_events` (journal)
`id bigint`, `contact_id FK`, `status`, `text_version`, `message_id FK null`, `created_at`. Append-only.

### `conversations`
Une conversation par contact.
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| contact_id | uuid FK UNIQUE | |
| mode | text | `bot` ou `human`, défaut `bot` |
| mode_changed_at / mode_changed_by / mode_reason | timestamptz / uuid null / text null | `mode_changed_by` référence `staff_users` ou `null` (client, système) |
| current_dossier_id | uuid FK null | dossier actif |
| last_inbound_at | timestamptz null | base de la **fenêtre de 24 h** |
| last_outbound_at | timestamptz null | |
| batch_not_before | timestamptz null | fin de l'attente de regroupement |
| summary | text null | résumé glissant, sert au ton uniquement |
| summary_upto_message_id | uuid null | |
| created_at, updated_at | timestamptz | |

Index : `(mode)`, `(last_inbound_at)`, `(batch_not_before) WHERE batch_not_before IS NOT NULL`.
Le verrou par conversation est un verrou consultatif Postgres (`pg_advisory_xact_lock` sur un hachage de `id`), pas une colonne.

### `inbound_events`
Tout ce que la passerelle envoie. Sert à l'idempotence et à la reprise.
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| channel_account_id | uuid FK | |
| dedupe_key | text | `channel_message_id` pour un message, sinon `type:id` |
| event_type | text | `message`, `delivery_status`, `connection` |
| payload | jsonb | contenu normalisé, sans binaire ni jeton |
| status | text | `received`, `queued`, `processing`, `done`, `failed`, `dead` |
| attempts | int | défaut 0 |
| error_code | text null | |
| correlation_id | uuid | |
| received_at, processed_at | timestamptz | |

Contraintes : **`UNIQUE (channel_account_id, dedupe_key)`**. L'insertion utilise `ON CONFLICT DO NOTHING` : un doublon est sans effet.
Index : `(status, received_at)`.

### `messages`
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| conversation_id | uuid FK | |
| direction | text | `in` ou `out` |
| sender | text | `client`, `bot`, `human_agent`, `system` |
| channel_message_id | text null | |
| inbound_event_id | uuid FK null | |
| outbound_id | uuid null | clé d'idempotence d'envoi |
| kind | text | `text`, `image`, `document`, `audio`, `video`, `sticker`, `location`, `contact`, `reaction`, `template`, `unsupported` |
| text | text null | |
| document_id | uuid FK null | pièce jointe stockée |
| reply_to_message_id | uuid FK null | |
| template_name | text null | si envoi hors fenêtre |
| delivery_status | text null | `pending`, `sent`, `delivered`, `read`, `failed` (sortants) |
| error_code | text null | |
| attempts | int | |
| batch_id | uuid null | messages traités dans le même tour |
| channel_sent_at | timestamptz null | |
| created_at | timestamptz | |

Contraintes : `UNIQUE (conversation_id, channel_message_id) WHERE channel_message_id IS NOT NULL` ; `UNIQUE (outbound_id) WHERE outbound_id IS NOT NULL` ; `CHECK (direction = 'out' OR sender = 'client')`.
Index : `(conversation_id, created_at)`, `(delivery_status) WHERE delivery_status IN ('pending','failed')`.

### `message_templates`
Registre des modèles pour l'envoi hors fenêtre (approuvés chez Meta en production, simulés par texte avec Baileys).
`id`, `name`, `language` (défaut `fr`), `body_fr`, `params_count`, `purpose`, `meta_status` (`local`, `submitted`, `approved`, `rejected`), `created_at`. `UNIQUE (name, language)`.

## 2. Catalogue (configuration modifiable, versionnée)

Le catalogue est **publié par versions**. Une version `published` est immuable ; on modifie une copie `draft`, puis on la publie. Cela permet le **prix figé au devis** (décision C).

### `catalog_versions`
`id`, `version int UNIQUE`, `status` (`draft`, `published`, `archived`), `note`, `created_by`, `published_at`, `published_by`.
Contrainte : **un seul `published`** (`UNIQUE (status) WHERE status = 'published'`).

### `procedures`
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| catalog_version_id | uuid FK | |
| code | text | identifiant stable (`criminal_record`, `passport_renewal`…) |
| name_fr | text | |
| description_fr | text null | |
| delay_min_days / delay_max_days | int null | jours ouvrables |
| needs_valid_phone | bool | |
| handoff_only | bool | cas à passer à un conseiller (ex. certificat de nationalité, né à l'étranger) |
| payment_order | text null | `documents_first`, `payment_first`, ou `null` = valeur globale |
| status | text | `draft` ou `confirmed` |
| sort_order | int | |

Contraintes : `UNIQUE (catalog_version_id, code)`.
**Règle : l'assistant ne cite jamais une entrée `draft`.** Il alerte l'équipe (type `unusual_request`).

### `procedure_variants`
Pour RCCM (forme juridique) et TVM. `id`, `procedure_id FK`, `code`, `label_fr`, `selector_question_fr`, `status`, `sort_order`. `UNIQUE (procedure_id, code)`.

### `fee_rules`
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| procedure_id | uuid FK | |
| variant_id | uuid FK null | |
| pricing_mode | text | `fixed` ou `by_parameter` |
| parameter_code | text null | `fiscal_power` pour la TVM |
| official_fee_xof | int null | requis si `fixed` |
| vigo_fee_xof | int | |
| status | text | `draft` ou `confirmed` |

Contraintes : `CHECK (pricing_mode <> 'fixed' OR official_fee_xof IS NOT NULL)` ; `UNIQUE (procedure_id, variant_id)`.

### `fee_parameter_bands`
Tranches pour `by_parameter`. `id`, `fee_rule_id FK`, `min_value int`, `max_value int`, `official_fee_xof int`. Contrainte d'exclusion : pas de tranches qui se chevauchent pour un même `fee_rule_id` (`EXCLUDE USING gist (fee_rule_id WITH =, int4range(min_value, max_value, '[]') WITH &&)`).
**La table de la puissance fiscale de la TVM reste vide tant que Vigo ne l'a pas fournie.** Un devis TVM est alors impossible et l'équipe est alertée.

### `requirement_groups`
Une procédure demande ses pièces dans un **ordre**.
`id`, `procedure_id FK`, `variant_id FK null`, `position int` (ordre de demande), `label_fr`, `rule` (`all_of` ou `one_of`), `min_count int` (défaut 1), `condition_note_fr text null`. `UNIQUE (procedure_id, variant_id, position)`.

### `requirement_items`
`id`, `group_id FK`, `code`, `label_fr` (**libellé canonique, utilisé mot pour mot par l'assistant**), `capture_mode` (`file` ou `text`), `doc_kind` (`identity`, `civil_status`, `attestation`, `vehicle`, `photo`, `other`), `is_sensitive bool`, `is_fallback bool` (le « à défaut »), `help_fr text null`, `position int`. `UNIQUE (group_id, code)`.
`capture_mode = 'text'` couvre le numéro de châssis et la référence de plaque : valeur saisie, pas un fichier.

### `settings`
`key text PK`, `value jsonb`, `updated_by uuid null`, `updated_at`. Valeurs de départ : `payment_order` (`documents_first`), `batch_window_ms`, `retention_days_documents`, `retention_days_messages`, `llm_monthly_budget_usd`, `llm_budget_alert_pct` (80), `quote_validity_hours`.

## 3. Dossiers

### `dossiers`
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| conversation_id | uuid FK | |
| contact_id | uuid FK | |
| procedure_id | uuid FK | procédure **de la version de catalogue utilisée** |
| variant_id | uuid FK null | |
| catalog_version_id | uuid FK | figée à l'ouverture |
| status | text | voir machine à états ci-dessous |
| payment_order | text | copie résolue à l'ouverture (`documents_first` ou `payment_first`) |
| assigned_to | uuid FK null | `staff_users` |
| version | int | verrou optimiste |
| opened_at, closed_at | timestamptz | |
| closed_reason | text null | |

Index : `(status)`, `(conversation_id)`, `(contact_id, status)`.
Contrainte : au plus un dossier non terminé par conversation pour une même procédure (index unique partiel sur `(conversation_id, procedure_id) WHERE status NOT IN ('closed','cancelled')`).

### Machine à états

États : `intake`, `quoted`, `collecting_documents`, `documents_complete`, `team_review`, `rework_needed`, `awaiting_payment`, `paid`, `ready_to_file`, `filed`, `closed`, `cancelled`, `handed_off`.

Deux chemins, choisis par `dossiers.payment_order` :
- `documents_first` : `intake → quoted → collecting_documents → documents_complete → team_review → awaiting_payment → paid → ready_to_file → filed → closed`
- `payment_first` : `intake → quoted → awaiting_payment → paid → collecting_documents → documents_complete → team_review → ready_to_file → filed → closed`

Boucle : `team_review → rework_needed → collecting_documents` (pièce « à refaire »). `handed_off` et `cancelled` sont accessibles depuis tout état non terminal.

Gardes appliquées **dans le code et par trigger** :
- Vers `paid` : l'acteur du journal est `payment_webhook` ou `team_user` (espèces ou virement validés dans le tableau de bord). Jamais `client` ni `bot`.
- Vers `documents_complete` : toutes les pièces requises sont `received` ou mieux.
- Vers `awaiting_payment` : un devis `issued` existe.

### `dossier_events` (journal, append-only)
`id bigint identity`, `dossier_id FK`, `seq int`, `type`, `from_status`, `to_status`, `actor_type` (`bot`, `client`, `team_user`, `system`, `payment_webhook`), `actor_id uuid null`, `payload jsonb`, `correlation_id uuid`, `created_at`.
Contraintes : `UNIQUE (dossier_id, seq)`. Aucune mise à jour ni suppression : droits `UPDATE/DELETE` retirés au rôle applicatif, trigger de refus en plus.
Le statut courant de `dossiers.status` doit toujours égaler le dernier `to_status` (test d'intégration).

### `dossier_inputs`
Informations textuelles collectées (puissance fiscale, forme juridique, châssis, plaque).
`id`, `dossier_id FK`, `key`, `value_text`, `source` (`client_text`, `team`), `created_at`. `UNIQUE (dossier_id, key)`. Ces valeurs ne sont pas des pièces d'identité.

### `quotes`
Prix **figé** au devis.
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| dossier_id | uuid FK | |
| catalog_version_id | uuid FK | |
| lines | jsonb | détail : coût officiel, frais VGS, paramètre utilisé |
| official_total_xof | int | |
| vigo_fee_xof | int | |
| total_xof | int | |
| status | text | `issued`, `superseded`, `accepted`, `expired`, `cancelled` |
| issued_by_tool_call_id | uuid FK null | traçabilité : l'outil qui a calculé |
| valid_until | timestamptz null | |
| issued_at | timestamptz | |

Contraintes : `CHECK (total_xof = official_total_xof + vigo_fee_xof)` ; un seul devis `issued` par dossier (`UNIQUE (dossier_id) WHERE status = 'issued'`).

## 4. Pièces et documents

Rappel (ADR 0002) : le modèle ne voit jamais le contenu d'un fichier.

### `dossier_pieces`
Une ligne par pièce attendue, créée à l'ouverture du dossier à partir de `requirement_groups`/`requirement_items`.
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| dossier_id | uuid FK | |
| requirement_group_id | uuid FK | |
| requirement_item_id | uuid FK null | choisi quand le groupe est `one_of` (null tant que non choisi) |
| request_rank | int | ordre de demande, sert à l'attribution |
| is_required | bool | |
| status | text | `expected`, `received`, `seen_by_team`, `accepted`, `to_redo` |
| redo_reason | text null | requis si `to_redo` |
| redo_count | int | défaut 0 |
| current_document_id | uuid FK null | |
| requested_at, received_at, status_changed_at | timestamptz null | |
| status_changed_by | uuid null | |

Contraintes : `CHECK (status <> 'to_redo' OR redo_reason IS NOT NULL)` ; `UNIQUE (dossier_id, requirement_group_id, request_rank)`.
Index : `(dossier_id, status)`.
« Pièce attendue courante » = la ligne `expected` de plus petit `request_rank` déjà demandée (`requested_at` non nul).

### `documents`
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| dossier_id | uuid FK null | rempli à l'attribution |
| contact_id | uuid FK | |
| message_id | uuid FK | |
| storage_key | text | clé dans le stockage d'objets, **sans nom de fichier d'origine** |
| size_bytes | bigint | |
| mime_declared | text | |
| mime_detected | text | par octets magiques |
| sha256 | bytea | empreinte du fichier en clair |
| enc_key_id | text | version de la clé maître |
| enc_wrapped_dek | bytea | clé de données chiffrée (chiffrement par enveloppe) |
| enc_nonce | bytea | |
| status | text | `fetching`, `stored`, `quarantined`, `rejected`, `media_expired`, `failed`, `erased` |
| reject_reason | text null | |
| sharpness_score | numeric null | calculé localement, indicatif, optionnel |
| duplicate_of_document_id | uuid FK null | |
| original_filename_enc | bytea null | nom d'origine **chiffré**, jamais envoyé au modèle |
| erased_at | timestamptz null | |
| created_at | timestamptz | |

Index : `(sha256)`, `(dossier_id)`, `(status) WHERE status IN ('fetching','failed')`.
Détection de doublon : on **signale** (`duplicate_of_document_id`), on ne refuse pas.

### `piece_attributions` (historique)
`id bigint`, `document_id FK`, `dossier_piece_id FK`, `source` (`expected_order`, `declared_by_client`, `team_manual`), `needs_review bool` (vrai pour une rafale), `actor_id uuid null`, `created_at`.
L'attribution courante est la dernière ligne par `document_id`. La source reste consultable par l'équipe.

### `media_fetch_jobs`
Récupération immédiate du fichier à la réception (ADR 0003).
`id`, `inbound_event_id FK`, `message_id FK`, `media_ref text` (opaque, voir contrat), `status` (`pending`, `fetching`, `done`, `expired`, `failed`), `attempts int`, `next_attempt_at`, `deadline_at`, `last_error_code text null`, `created_at`, `done_at`.
Index : `(status, next_attempt_at)`.
Le tour de l'assistant attend l'issue de ces jobs (avec délai maximal) pour ne jamais annoncer « bien reçu » avant que le fichier soit stocké.

### `document_access_links`
`id uuid` (le jeton signé référence cet identifiant), `document_id FK`, `issued_to uuid FK staff_users`, `expires_at`, `used_at null`, `created_at`. Durée de vie courte (valeur de départ : 120 s). Le lien pointe vers un endpoint de l'application, pas vers le stockage : l'application déchiffre en mémoire et sert le fichier.

## 5. Paiements (étape 5)

### `payment_attempts`
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| dossier_id | uuid FK | |
| quote_id | uuid FK | |
| provider | text | |
| provider_ref | text | notre référence envoyée à l'agrégateur |
| provider_txn_id | text null | |
| method | text null | `mtn_momo`, `moov_flooz`, `celtiis`, `other` |
| amount_xof | int | |
| status | text | `created`, `pending`, `succeeded`, `failed`, `expired`, `cancelled` |
| payment_url | text null | |
| expires_at | timestamptz null | |
| created_at | timestamptz | |

Contraintes : `UNIQUE (provider, provider_ref)`.

### `payment_webhook_events`
Tout webhook reçu, valide ou non.
`id`, `provider`, `provider_event_id text`, `signature_valid bool`, `body_sha256 bytea`, `payload jsonb`, `status` (`received`, `processed`, `ignored`, `error`), `error_code null`, `received_at`, `processed_at null`.
Contraintes : **`UNIQUE (provider, provider_event_id)`** (idempotence). Un événement à signature invalide est enregistré et jamais traité.

### `payments` (registre des encaissements)
| Colonne | Type | Notes |
|---|---|---|
| id | uuid PK | |
| dossier_id | uuid FK | |
| payment_attempt_id | uuid FK null | null pour espèces ou virement |
| webhook_event_id | uuid FK null | |
| method | text | `mtn_momo`, `moov_flooz`, `celtiis`, `cash`, `transfer`, `other` |
| amount_xof | int | `CHECK > 0` |
| classification | text | `full`, `partial`, `duplicate`, `late`, `excess`, `manual` |
| validated_by | uuid FK null | obligatoire pour `cash`/`transfer` |
| refund_status | text | `none`, `requested`, `done` (traitement manuel au départ) |
| received_at | timestamptz | |

Contraintes : `CHECK (method NOT IN ('cash','transfer') OR validated_by IS NOT NULL)`.
Le solde d'un dossier se **calcule** (somme des paiements retenus moins le devis) ; il n'est pas stocké.

## 6. Alertes

### `staff_users`
`id`, `email`, `display_name`, `role` (`admin`, `agent`, `viewer`), `can_view_documents bool` (défaut `false`), `access_subject text` (identité fournie par Cloudflare Access), `active bool`, `created_at`. `UNIQUE (email)`.

### `alert_recipients`
`id`, `name`, `channel` (`sms`, `email`, `whatsapp`), `address`, `alert_types text[]`, `min_priority`, `active`, `created_at`.

### `alerts`
`id`, `type` (`missing_info`, `dossier_complete`, `no_courier`, `unhappy_client`, `unusual_request`, `human_requested`, `guard_failed`, `budget_threshold`, `gateway_disconnected`, `media_expired`, `payment_anomaly`, `catalog_draft`), `priority` (`low`, `normal`, `high`, `urgent`), `conversation_id FK null`, `dossier_id FK null`, `summary text` (sans donnée personnelle superflue), `status` (`open`, `acknowledged`, `resolved`), `dedupe_key text null`, `created_at`, `acknowledged_by/at`, `resolved_by/at`.
Contrainte : `UNIQUE (dedupe_key) WHERE status <> 'resolved'` (évite les doublons d'alertes ouvertes). Index : `(status, priority, created_at)`.

### `alert_deliveries`
`id`, `alert_id FK`, `recipient_id FK`, `channel`, `status` (`pending`, `sent`, `failed`), `attempts`, `provider_ref null`, `last_error null`, `created_at`, `sent_at null`.

## 7. Journal du modèle et coûts

### `llm_turns`
`id`, `conversation_id FK`, `dossier_id FK null`, `batch_id uuid`, `correlation_id uuid`, `task` (`conversation`, `summarize`, `light`), `model text`, `prompt_version text`, `attempt int` (1 ou 2 : régénération du garde-fou), `guard_status` (`passed`, `rejected`, `failed_handoff`), `guard_report jsonb` (montants et pièces cités, écarts relevés, **sans texte client**), `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_micro_usd bigint`, `duration_ms`, `error_code null`, `created_at`.
Index : `(conversation_id, created_at)`, `(created_at)`. Les prompts et réponses complètes ne sont **pas** stockés ici ; la réponse envoyée se trouve dans `messages`.

### `llm_tool_calls`
`id`, `turn_id FK`, `name`, `args jsonb` (validés, minimisés), `result jsonb` (codes et montants, jamais de contenu de pièce), `ok bool`, `error_code null`, `duration_ms`, `created_at`. Sert au garde-fou : ensemble des montants et des codes de pièces renvoyés pendant le tour.

Vue `llm_cost_daily` (jour, modèle, coût) et vue `llm_cost_month` pour le plafond configurable et l'alerte à 80 %.

## 8. Audit

### `audit_log` (append-only)
`id bigint`, `at`, `actor_type` (`staff`, `system`), `actor_id uuid null`, `action` (`document.link_issued`, `document.opened`, `dossier.viewed`, `conversation.takeover`, `config.changed`, `payment.manual_validated`, `erasure.executed`), `target_type`, `target_id uuid`, `ip inet null`, `user_agent text null`, `meta jsonb`.
Chaque ouverture de pièce écrit une ligne, **avant** d'envoyer le contenu. Même protection que `dossier_events` (pas de mise à jour ni de suppression).

## 9. Cycle de vie des données

### `erasure_requests`
`id`, `contact_id FK`, `requested_at`, `requested_via`, `status` (`pending`, `done`, `rejected`), `executed_by null`, `completed_at null`, `note null`.
Exécution : suppression des objets du stockage et passage de `documents.status` à `erased`, effacement de `messages.text`, anonymisation du contact (`channel_contact_id` remplacé par un hachage, `display_name` vidé), conservation des montants et des événements sans donnée personnelle (obligations comptables, à confirmer avec Vigo).
Une tâche planifiée applique `retention_days_*` (durées à fixer avec le client).

## 10. Index et contraintes clés (récapitulatif)

| Garantie | Mécanisme |
|---|---|
| Message entrant jamais traité deux fois | `UNIQUE (channel_account_id, dedupe_key)` sur `inbound_events` |
| Envoi jamais dupliqué | `UNIQUE (outbound_id)` sur `messages` |
| Webhook de paiement jamais rejoué | `UNIQUE (provider, provider_event_id)` |
| Une seule version de catalogue active | index unique partiel sur `catalog_versions` |
| Prix cohérent | `CHECK (total = officiel + frais)` sur `quotes` |
| « Payé » jamais posé par le client | garde de transition + trigger sur `dossier_events` |
| Journaux non modifiables | droits retirés + triggers (`dossier_events`, `audit_log`, `consent_events`) |
| Numéro Baileys jamais en production | `CHECK` sur `channel_accounts` |
| Pas de tranches de prix qui se chevauchent | contrainte d'exclusion sur `fee_parameter_bands` |
| Un seul tour d'IA à la fois par conversation | verrou consultatif par conversation |

## 11. Points à faire trancher

1. **Paiement fait et pièce refusée** : le schéma enregistre le paiement dans tous les cas et passe le dossier en `rework_needed`. Le remboursement est manuel (`refund_status`). À confirmer avec Vigo.
2. Conservation comptable des montants après anonymisation : durée à confirmer.
3. Nom d'origine des fichiers : conservé chiffré. Si Vigo n'en veut pas, la colonne disparaît.

## 12. Écarts entre ce schéma et les migrations R1 à R3 (18/11/2026)

Décidés par l'ingénieur dans son périmètre ; les migrations font foi.

- **PostgreSQL 15 minimum** : `UNIQUE NULLS NOT DISTINCT` est utilisé pour l'unicité de `(procédure, variante)` et `(procédure, variante, position)`. Neon et l'image de test sont en 16.
- Identifiants : `gen_random_uuid()` (UUID v4) par défaut en base, au lieu d'UUID v7 générés par l'application. Aucune dépendance au tri par temps n'existe pour l'instant ; à revoir si une pagination par identifiant devient nécessaire.
- `inbound_events.payload` est **nullable** et `payload_purged_at` est ajouté (ADR 0005).
- `staff_users` est créée dans R1 (et non R3) parce que `conversations` y fait référence.
- `catalog_versions` : colonne `created_at` ajoutée et déclencheur qui interdit de repasser une version publiée ou archivée en brouillon.
- `procedures.selector_question_fr` remplace `procedure_variants.selector_question_fr` (nullable, non semée : l'agent formule la question lui-même).
- `procedure_variants.handoff_only` ajouté (cas « Béninois né à l'étranger »).
- `fee_rules` : `official_fee_min_xof` et `official_fee_max_xof` ajoutés pour afficher la fourchette de la TVM tant que la table de puissance fiscale manque.
- `requirement_items.status` (`draft` ou `confirmed`) ajouté : certains intitulés (« C'est moi », FID) sont à confirmer.
- `messages` : contrainte supplémentaire, un message sortant ne peut pas avoir `sender = 'client'`.
- `audit_log` et `consent_events` : le déclencheur d'immuabilité couvre aussi `TRUNCATE`.
- Sans clé étrangère pour l'instant (tables des étapes suivantes) : `conversations.current_dossier_id`, `alerts.dossier_id`, `messages.document_id`.
- `erasure_requests` n'est pas créée : `contacts.erasure_requested_at` et `anonymized_at` suffisent tant qu'il n'y a pas de tableau de bord.
- Tables des étapes 2 à 5 (`media_fetch_jobs`, `documents`, `dossiers`…) : créées avec leur étape, comme décidé (migrations groupées par étape).
