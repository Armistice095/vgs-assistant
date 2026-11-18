"""Where client text and client identifiers are allowed to live in the database.

Every free-text column (text, varchar, json, jsonb, bytea, arrays, inet) must appear here with
one of four classes. A test compares this registry with the real schema, so adding a column
without deciding its class fails the build.

Classes:
- ``client_data``: may hold what the client wrote or an identifier of the client. Covered by
  the retention rules and erased on request (see ``vgs.privacy.erasure``).
- ``staff_data``: data about the company's own staff.
- ``config``: catalogue, templates, settings: written by the company, never by clients.
- ``technical``: codes, ids, versions. MUST NOT hold client text. This is the reason the
  append-only tables (audit log, consent events) can be immutable: they only have technical
  columns.

Columns of tables that do not exist yet (documents, payment webhooks, dossier inputs, LLM
journals) are listed in ``PLANNED`` so their class is decided before the table is created.
"""

from __future__ import annotations

from enum import StrEnum


class DataClass(StrEnum):
    CLIENT_DATA = "client_data"
    STAFF_DATA = "staff_data"
    CONFIG = "config"
    TECHNICAL = "technical"


C, S, G, T = (
    DataClass.CLIENT_DATA,
    DataClass.STAFF_DATA,
    DataClass.CONFIG,
    DataClass.TECHNICAL,
)

REGISTRY: dict[str, DataClass] = {
    # Client data
    "contacts.channel_contact_id": C,  # phone number / PSID
    "contacts.display_name": C,
    "conversations.summary": C,
    "conversations.mode_reason": C,  # free text: may quote the client
    "inbound_events.payload": C,  # raw normalised event, contains the message text
    "messages.text": C,
    "alerts.summary": C,
    # Staff data
    "alert_recipients.address": S,
    "alert_recipients.alert_types": S,
    "alert_recipients.name": S,
    "audit_log.ip": S,
    "audit_log.user_agent": S,
    "staff_users.access_subject": S,
    "staff_users.display_name": S,
    "staff_users.email": S,
    # Configuration
    "catalog_versions.note": G,
    "channel_accounts.external_account_id": G,  # the company's own number or page
    "channel_accounts.label": G,
    "fee_rules.parameter_code": G,
    "message_templates.body_fr": G,
    "message_templates.language": G,
    "message_templates.name": G,
    "message_templates.purpose": G,
    "procedure_variants.code": G,
    "procedure_variants.label_fr": G,
    "procedures.code": G,
    "procedures.description_fr": G,
    "procedures.name_fr": G,
    "procedures.selector_question_fr": G,
    "requirement_groups.condition_note_fr": G,
    "requirement_groups.label_fr": G,
    "requirement_items.code": G,
    "requirement_items.help_fr": G,
    "requirement_items.label_fr": G,
    "settings.key": G,
    "settings.value": G,
    # Technical (never client text)
    "alert_deliveries.last_error": T,  # provider error code, never message content
    "alert_deliveries.provider_ref": T,
    "alerts.dedupe_key": T,  # built from ids and codes
    "audit_log.meta": T,  # ids and codes only: the table is append-only
    "audit_log.target_type": T,
    "consent_events.text_version": T,
    "contacts.consent_text_version": T,
    "inbound_events.dedupe_key": T,  # channel message id; NEVER the contact id or a phone number
    "inbound_events.error_code": T,
    "messages.channel_message_id": T,
    "messages.error_code": T,
    "messages.template_name": T,
}

# Decided in advance for the tables of steps 2 to 5. When the table is created, its columns
# must be moved to REGISTRY (the schema test will fail until they are).
PLANNED: dict[str, DataClass] = {
    "documents.original_filename_enc": C,  # may contain a person's name; encrypted
    "documents.storage_key": T,
    "documents.reject_reason": T,
    "media_fetch_jobs.media_ref": T,
    "media_fetch_jobs.last_error_code": T,
    "dossier_inputs.value_text": C,  # chassis, plate, fiscal power, legal form
    "dossier_events.payload": T,  # ids and codes only: append-only
    "dossier_pieces.redo_reason": C,  # written by staff for the client
    "payment_webhook_events.payload": C,  # may carry the payer's phone number
    "payment_attempts.payment_url": T,
    "payments.*": T,
    "quotes.lines": T,
    "llm_turns.guard_report": T,  # amounts and codes, no client text
    "llm_tool_calls.args": T,  # minimised and validated
    "llm_tool_calls.result": T,
}


def client_data_columns() -> list[tuple[str, str]]:
    return sorted(
        (table, column)
        for key, cls in REGISTRY.items()
        for table, column in [key.split(".", 1)]
        if cls is DataClass.CLIENT_DATA
    )
