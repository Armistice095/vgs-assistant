-- R3: alerts, audit log, immutability triggers.

CREATE TABLE alert_recipients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  channel text NOT NULL CHECK (channel IN ('sms', 'email', 'whatsapp')),
  address text NOT NULL,
  alert_types text[] NOT NULL DEFAULT '{}',
  min_priority text NOT NULL DEFAULT 'low'
    CHECK (min_priority IN ('low', 'normal', 'high', 'urgent')),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type text NOT NULL CHECK (type IN (
    'missing_info', 'dossier_complete', 'no_courier', 'unhappy_client', 'unusual_request',
    'human_requested', 'guard_failed', 'budget_threshold', 'gateway_disconnected',
    'media_expired', 'payment_anomaly', 'catalog_draft')),
  priority text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
  conversation_id uuid REFERENCES conversations(id),
  dossier_id uuid,
  summary text NOT NULL,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
  dedupe_key text,
  created_at timestamptz NOT NULL DEFAULT now(),
  acknowledged_by uuid REFERENCES staff_users(id),
  acknowledged_at timestamptz,
  resolved_by uuid REFERENCES staff_users(id),
  resolved_at timestamptz
);
CREATE UNIQUE INDEX alerts_open_dedupe_uq ON alerts (dedupe_key)
  WHERE dedupe_key IS NOT NULL AND status <> 'resolved';
CREATE INDEX alerts_queue_idx ON alerts (status, priority, created_at);

CREATE TABLE alert_deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_id uuid NOT NULL REFERENCES alerts(id),
  recipient_id uuid NOT NULL REFERENCES alert_recipients(id),
  channel text NOT NULL CHECK (channel IN ('sms', 'email', 'whatsapp')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
  attempts integer NOT NULL DEFAULT 0,
  provider_ref text,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz
);
CREATE INDEX alert_deliveries_pending_idx ON alert_deliveries (status) WHERE status = 'pending';

CREATE TABLE audit_log (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  at timestamptz NOT NULL DEFAULT now(),
  actor_type text NOT NULL CHECK (actor_type IN ('staff', 'system')),
  actor_id uuid,
  action text NOT NULL CHECK (action IN (
    'document.link_issued', 'document.opened', 'dossier.viewed', 'conversation.takeover',
    'config.changed', 'payment.manual_validated', 'erasure.executed')),
  target_type text NOT NULL,
  target_id uuid NOT NULL,
  ip inet,
  user_agent text,
  meta jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX audit_log_target_idx ON audit_log (target_type, target_id, at);

CREATE TRIGGER audit_log_immutable BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION deny_modification();
CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION deny_modification();
CREATE TRIGGER consent_events_immutable BEFORE UPDATE OR DELETE ON consent_events
  FOR EACH ROW EXECUTE FUNCTION deny_modification();
CREATE TRIGGER consent_events_no_truncate BEFORE TRUNCATE ON consent_events
  FOR EACH STATEMENT EXECUTE FUNCTION deny_modification();
