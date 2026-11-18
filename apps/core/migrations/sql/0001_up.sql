-- R1: channels, contacts, conversations, messages, inbound events, templates, consent.
-- Written without the percent sign: this file is executed as a raw multi-statement string.

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END
$$;

CREATE FUNCTION deny_modification() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION USING MESSAGE = 'append-only table: ' || TG_TABLE_NAME;
END
$$;

CREATE TABLE staff_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  display_name text NOT NULL,
  role text NOT NULL CHECK (role IN ('admin', 'agent', 'viewer')),
  can_view_documents boolean NOT NULL DEFAULT false,
  access_subject text,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE channel_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel text NOT NULL
    CHECK (channel IN ('whatsapp_baileys', 'whatsapp_cloud', 'messenger', 'console')),
  external_account_id text NOT NULL,
  label text NOT NULL,
  is_production boolean NOT NULL DEFAULT false,
  reply_window_hours integer NOT NULL DEFAULT 24 CHECK (reply_window_hours > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (channel, external_account_id),
  CONSTRAINT baileys_never_production
    CHECK (channel <> 'whatsapp_baileys' OR is_production = false)
);

CREATE TABLE contacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_account_id uuid NOT NULL REFERENCES channel_accounts(id),
  channel_contact_id text NOT NULL,
  display_name text,
  consent_status text NOT NULL DEFAULT 'unknown'
    CHECK (consent_status IN ('unknown', 'granted', 'refused', 'withdrawn')),
  consent_text_version text,
  consent_at timestamptz,
  erasure_requested_at timestamptz,
  anonymized_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (channel_account_id, channel_contact_id)
);

CREATE TABLE conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contact_id uuid NOT NULL UNIQUE REFERENCES contacts(id),
  mode text NOT NULL DEFAULT 'bot' CHECK (mode IN ('bot', 'human')),
  mode_changed_at timestamptz,
  mode_changed_by uuid REFERENCES staff_users(id),
  mode_reason text,
  current_dossier_id uuid,
  last_inbound_at timestamptz,
  last_outbound_at timestamptz,
  batch_not_before timestamptz,
  summary text,
  summary_upto_message_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX conversations_mode_idx ON conversations (mode);
CREATE INDEX conversations_last_inbound_idx ON conversations (last_inbound_at);
CREATE INDEX conversations_batch_idx ON conversations (batch_not_before)
  WHERE batch_not_before IS NOT NULL;
CREATE TRIGGER conversations_updated_at BEFORE UPDATE ON conversations
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE inbound_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_account_id uuid NOT NULL REFERENCES channel_accounts(id),
  dedupe_key text NOT NULL,
  event_type text NOT NULL CHECK (event_type IN ('message', 'delivery_status', 'connection')),
  payload jsonb,
  payload_purged_at timestamptz,
  status text NOT NULL DEFAULT 'received'
    CHECK (status IN ('received', 'queued', 'processing', 'done', 'failed', 'dead')),
  attempts integer NOT NULL DEFAULT 0,
  error_code text,
  correlation_id uuid NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  UNIQUE (channel_account_id, dedupe_key)
);
CREATE INDEX inbound_events_status_idx ON inbound_events (status, received_at);

CREATE TABLE messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id),
  direction text NOT NULL CHECK (direction IN ('in', 'out')),
  sender text NOT NULL CHECK (sender IN ('client', 'bot', 'human_agent', 'system')),
  channel_message_id text,
  inbound_event_id uuid REFERENCES inbound_events(id),
  outbound_id uuid,
  kind text NOT NULL CHECK (kind IN (
    'text', 'image', 'document', 'audio', 'video', 'sticker', 'location',
    'contact', 'reaction', 'template', 'unsupported')),
  text text,
  document_id uuid,
  reply_to_message_id uuid REFERENCES messages(id),
  template_name text,
  delivery_status text
    CHECK (delivery_status IN ('pending', 'sent', 'delivered', 'read', 'failed')),
  error_code text,
  attempts integer NOT NULL DEFAULT 0,
  batch_id uuid,
  channel_sent_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT inbound_is_from_client CHECK (direction = 'out' OR sender = 'client'),
  CONSTRAINT outbound_is_not_from_client CHECK (direction = 'in' OR sender <> 'client')
);
CREATE UNIQUE INDEX messages_channel_message_uq ON messages (conversation_id, channel_message_id)
  WHERE channel_message_id IS NOT NULL;
CREATE UNIQUE INDEX messages_outbound_uq ON messages (outbound_id)
  WHERE outbound_id IS NOT NULL;
CREATE INDEX messages_conversation_idx ON messages (conversation_id, created_at);
CREATE INDEX messages_delivery_idx ON messages (delivery_status)
  WHERE delivery_status IN ('pending', 'failed');

CREATE TABLE message_templates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  language text NOT NULL DEFAULT 'fr',
  body_fr text NOT NULL,
  params_count integer NOT NULL DEFAULT 0 CHECK (params_count >= 0),
  purpose text NOT NULL,
  meta_status text NOT NULL DEFAULT 'local'
    CHECK (meta_status IN ('local', 'submitted', 'approved', 'rejected')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (name, language)
);

CREATE TABLE consent_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contact_id uuid NOT NULL REFERENCES contacts(id),
  status text NOT NULL CHECK (status IN ('granted', 'refused', 'withdrawn')),
  text_version text NOT NULL,
  message_id uuid REFERENCES messages(id),
  created_at timestamptz NOT NULL DEFAULT now()
);
