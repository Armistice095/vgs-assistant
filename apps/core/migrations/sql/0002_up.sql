-- R2: versioned catalogue and settings.

CREATE TABLE catalog_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version integer NOT NULL UNIQUE CHECK (version > 0),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  note text,
  created_by uuid REFERENCES staff_users(id),
  published_at timestamptz,
  published_by uuid REFERENCES staff_users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX catalog_one_published ON catalog_versions (status)
  WHERE status = 'published';

CREATE FUNCTION catalog_version_status_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status IN ('published', 'archived') AND NEW.status = 'draft' THEN
    RAISE EXCEPTION USING MESSAGE = 'a published catalogue version cannot go back to draft';
  END IF;
  RETURN NEW;
END
$$;
CREATE TRIGGER catalog_versions_guard BEFORE UPDATE ON catalog_versions
  FOR EACH ROW EXECUTE FUNCTION catalog_version_status_guard();

CREATE TABLE procedures (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  catalog_version_id uuid NOT NULL REFERENCES catalog_versions(id),
  code text NOT NULL,
  name_fr text NOT NULL,
  description_fr text,
  selector_question_fr text,
  delay_min_days integer CHECK (delay_min_days >= 0),
  delay_max_days integer CHECK (delay_max_days >= 0),
  needs_valid_phone boolean NOT NULL DEFAULT false,
  handoff_only boolean NOT NULL DEFAULT false,
  payment_order text CHECK (payment_order IN ('documents_first', 'payment_first')),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'confirmed')),
  sort_order integer NOT NULL DEFAULT 0,
  UNIQUE (catalog_version_id, code),
  CONSTRAINT delay_order CHECK (
    delay_min_days IS NULL OR delay_max_days IS NULL OR delay_min_days <= delay_max_days)
);

CREATE TABLE procedure_variants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  procedure_id uuid NOT NULL REFERENCES procedures(id),
  code text NOT NULL,
  label_fr text NOT NULL,
  handoff_only boolean NOT NULL DEFAULT false,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'confirmed')),
  sort_order integer NOT NULL DEFAULT 0,
  UNIQUE (procedure_id, code)
);

CREATE TABLE fee_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  procedure_id uuid NOT NULL REFERENCES procedures(id),
  variant_id uuid REFERENCES procedure_variants(id),
  pricing_mode text NOT NULL CHECK (pricing_mode IN ('fixed', 'by_parameter')),
  parameter_code text,
  official_fee_xof integer CHECK (official_fee_xof >= 0),
  official_fee_min_xof integer CHECK (official_fee_min_xof >= 0),
  official_fee_max_xof integer CHECK (official_fee_max_xof >= 0),
  vigo_fee_xof integer NOT NULL CHECK (vigo_fee_xof >= 0),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'confirmed')),
  CONSTRAINT fixed_needs_official CHECK (pricing_mode <> 'fixed' OR official_fee_xof IS NOT NULL),
  CONSTRAINT parameter_needs_code CHECK (
    pricing_mode <> 'by_parameter' OR parameter_code IS NOT NULL),
  CONSTRAINT official_range_order CHECK (
    official_fee_min_xof IS NULL OR official_fee_max_xof IS NULL
    OR official_fee_min_xof <= official_fee_max_xof),
  UNIQUE NULLS NOT DISTINCT (procedure_id, variant_id)
);

CREATE TABLE fee_parameter_bands (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fee_rule_id uuid NOT NULL REFERENCES fee_rules(id),
  min_value integer NOT NULL,
  max_value integer NOT NULL,
  official_fee_xof integer NOT NULL CHECK (official_fee_xof >= 0),
  CONSTRAINT band_order CHECK (min_value <= max_value),
  CONSTRAINT bands_do_not_overlap EXCLUDE USING gist (
    fee_rule_id WITH =, int4range(min_value, max_value, '[]') WITH &&)
);

CREATE TABLE requirement_groups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  procedure_id uuid NOT NULL REFERENCES procedures(id),
  variant_id uuid REFERENCES procedure_variants(id),
  position integer NOT NULL CHECK (position > 0),
  label_fr text NOT NULL,
  rule text NOT NULL CHECK (rule IN ('all_of', 'one_of')),
  min_count integer NOT NULL DEFAULT 1 CHECK (min_count > 0),
  condition_note_fr text,
  UNIQUE NULLS NOT DISTINCT (procedure_id, variant_id, position)
);

CREATE TABLE requirement_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id uuid NOT NULL REFERENCES requirement_groups(id),
  code text NOT NULL,
  label_fr text NOT NULL,
  capture_mode text NOT NULL DEFAULT 'file' CHECK (capture_mode IN ('file', 'text')),
  doc_kind text NOT NULL DEFAULT 'other'
    CHECK (doc_kind IN ('identity', 'civil_status', 'attestation', 'vehicle', 'photo', 'other')),
  is_sensitive boolean NOT NULL DEFAULT false,
  is_fallback boolean NOT NULL DEFAULT false,
  status text NOT NULL DEFAULT 'confirmed' CHECK (status IN ('draft', 'confirmed')),
  help_fr text,
  position integer NOT NULL CHECK (position > 0),
  UNIQUE (group_id, code)
);

CREATE TABLE settings (
  key text PRIMARY KEY,
  value jsonb NOT NULL,
  updated_by uuid REFERENCES staff_users(id),
  updated_at timestamptz NOT NULL DEFAULT now()
);
