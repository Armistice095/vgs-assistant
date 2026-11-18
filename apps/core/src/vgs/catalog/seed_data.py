"""Starting catalogue, exactly as supplied by the client (Vigo Services).

These are STARTING VALUES. Nothing here is validated by Vigo yet: every procedure,
variant and fee rule is seeded as ``draft`` and the catalogue version itself is a
draft. The assistant never quotes a draft entry outside development/tests.

Nothing is invented. Where the source is ambiguous the entry is flagged in
``docs/questions-vigo.md`` instead of being guessed:
- the fiscal-power table for the TVM is NOT provided (no bands are seeded);
- the names of the « C'est moi » card and of the FID certificate are unconfirmed;
- the delay "3 to 7 business days" is stored as a global indicative setting because
  the source says "for most documents" without saying which ones.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    code: str
    label_fr: str
    doc_kind: str = "other"
    sensitive: bool = False
    fallback: bool = False
    status: str = "confirmed"
    capture_mode: str = "file"
    help_fr: str | None = None


@dataclass(frozen=True)
class Group:
    label_fr: str
    rule: str  # "all_of" or "one_of"
    items: tuple[Item, ...]
    min_count: int = 1
    condition_note_fr: str | None = None


@dataclass(frozen=True)
class Fee:
    vigo_xof: int
    official_xof: int | None = None
    mode: str = "fixed"
    parameter_code: str | None = None
    official_min_xof: int | None = None
    official_max_xof: int | None = None

    @property
    def total_xof(self) -> int | None:
        if self.official_xof is None:
            return None
        return self.official_xof + self.vigo_xof


@dataclass(frozen=True)
class VariantSeed:
    code: str
    label_fr: str
    groups: tuple[Group, ...] = ()
    fee: Fee | None = None
    handoff_only: bool = False


@dataclass(frozen=True)
class ProcedureSeed:
    code: str
    name_fr: str
    groups: tuple[Group, ...] = ()
    fee: Fee | None = None
    variants: tuple[VariantSeed, ...] = ()
    needs_valid_phone: bool = False
    description_fr: str | None = None
    handoff_only: bool = False


BIRTH = Item("birth_certificate_secure", "Acte de naissance sécurisé", "civil_status", True)
CIP = Item("cip", "CIP", "identity", True)
BIOMETRIC = Item("biometric_id", "Carte d'identité biométrique", "identity", True)
ENROLMENT = Item(
    "enrolment_receipt",
    "Récépissé d'enrôlement",
    "identity",
    True,
    help_fr="s'il est disponible",
)
CESTMOI = Item(
    "cestmoi_card", "Carte « C'est moi »", "identity", True, fallback=True, status="draft"
)
FID = Item("fid_certificate", "Certificat FID", "identity", True, fallback=True, status="draft")
NATIONALITY = Item("nationality_certificate", "Certificat de nationalité", "attestation")
RESIDENCE = Item("residence_certificate", "Certificat de résidence", "attestation")
OLD_PASSPORT = Item("old_passport", "Ancien passeport", "identity", True)
RESIDENCE_PROOF = Item(
    "residence_proof_local_authority",
    "Preuve de résidence auprès du délégué ou chef de quartier",
    "attestation",
)
WITNESS_CIP = Item("witness_cip", "CIP du témoin", "identity", True)
CHASSIS = Item("chassis_number", "Numéro de châssis", "vehicle", capture_mode="text")
PLATE = Item("plate_reference", "Référence de la plaque", "vehicle", capture_mode="text")
ID_PHOTO = Item("id_photo", "Photo d'identité", "photo", True)
CRIMINAL_RECORD_3M = Item(
    "criminal_record_under_3_months", "Casier judiciaire de moins de 3 mois", "attestation", True
)
HONOUR_DECLARATION = Item("honour_declaration", "Déclaration sur l'honneur", "attestation")
STATUTES = Item("statutes", "Statuts")
STATUTES_NOTARIAL = Item("statutes_notarial", "Statuts notariés")
PAYMENT_SLIP = Item("payment_slip", "Bordereau de versement")
CONTRIBUTIONS_TABLE = Item("contributions_table", "Tableau des apports")
PARTNER_CIP = Item("partner_cip", "CIP de chaque associé", "identity", True)

_IDENTITY_ONE_OF = Group("Pièce d'identité", "one_of", (CIP, BIOMETRIC))
_RCCM_SOLE_TRADER_GROUPS = (
    _IDENTITY_ONE_OF,
    Group("Casier judiciaire ou déclaration", "one_of", (CRIMINAL_RECORD_3M, HONOUR_DECLARATION)),
    Group("Photo d'identité", "all_of", (ID_PHOTO,)),
)

PROCEDURES: tuple[ProcedureSeed, ...] = (
    ProcedureSeed(
        code="birth_certificate_secure",
        name_fr="Acte de naissance sécurisé",
        groups=(Group("Pièce d'identité", "one_of", (ENROLMENT, CIP, BIOMETRIC, CESTMOI, FID)),),
        fee=Fee(official_xof=1000, vigo_xof=1500),
        needs_valid_phone=True,
    ),
    ProcedureSeed(
        code="cip",
        name_fr="CIP",
        groups=(Group("Pièce justificative", "one_of", (ENROLMENT, BIOMETRIC, BIRTH)),),
        fee=Fee(official_xof=1000, vigo_xof=1500),
        needs_valid_phone=True,
    ),
    ProcedureSeed(
        code="criminal_record",
        name_fr="Casier judiciaire",
        groups=(
            _IDENTITY_ONE_OF,
            Group("Acte de naissance sécurisé", "all_of", (BIRTH,)),
        ),
        fee=Fee(official_xof=1900, vigo_xof=2000),
        needs_valid_phone=True,
    ),
    ProcedureSeed(
        code="residence_certificate",
        name_fr="Certificat de résidence",
        variants=(
            VariantSeed(
                code="local_authority_proof",
                label_fr="Preuve de résidence auprès du délégué ou chef de quartier",
                groups=(
                    Group(
                        "Pièces à fournir",
                        "all_of",
                        (RESIDENCE_PROOF, CIP, WITNESS_CIP),
                    ),
                ),
            ),
            VariantSeed(
                code="vigo_attestation",
                label_fr="Attestation fournie par Vigo Services (valable 1 an)",
            ),
        ),
        fee=Fee(official_xof=2000, vigo_xof=2500),
    ),
    ProcedureSeed(
        code="nationality_certificate",
        name_fr="Certificat de nationalité",
        groups=(Group("Pièces à fournir", "all_of", (BIRTH, CIP, RESIDENCE)),),
        fee=Fee(official_xof=3500, vigo_xof=3000),
        variants=(
            VariantSeed(
                code="born_abroad",
                label_fr="Béninois né à l'étranger",
                handoff_only=True,
            ),
        ),
    ),
    ProcedureSeed(
        code="passport_new",
        name_fr="Passeport, nouvelle demande",
        groups=(Group("Pièces à fournir", "all_of", (BIRTH, CIP, NATIONALITY)),),
        fee=Fee(official_xof=30000, vigo_xof=10000),
    ),
    ProcedureSeed(
        code="passport_renewal",
        name_fr="Passeport, renouvellement",
        groups=(Group("Pièces à fournir", "all_of", (OLD_PASSPORT, BIRTH, CIP, NATIONALITY)),),
        fee=Fee(official_xof=30000, vigo_xof=8000),
    ),
    ProcedureSeed(
        code="vehicle_tvm",
        name_fr="TVM",
        groups=(Group("Informations du véhicule", "all_of", (CHASSIS, PLATE)),),
        fee=Fee(
            vigo_xof=3000,
            mode="by_parameter",
            parameter_code="fiscal_power",
            official_min_xof=20000,
            official_max_xof=60000,
        ),
        description_fr="Le coût officiel dépend de la puissance fiscale du véhicule.",
    ),
    ProcedureSeed(
        code="technical_inspection",
        name_fr="Visite technique",
        groups=(Group("Informations du véhicule", "all_of", (CHASSIS, PLATE)),),
        fee=Fee(official_xof=3000, vigo_xof=5000),
    ),
    ProcedureSeed(
        code="rccm",
        name_fr="RCCM",
        description_fr="Démarche en ligne sur monentreprise.bj.",
        variants=(
            VariantSeed(
                code="sole_trader",
                label_fr="Entreprise individuelle",
                groups=_RCCM_SOLE_TRADER_GROUPS,
                fee=Fee(official_xof=10000, vigo_xof=15000),
            ),
            VariantSeed(
                code="sarl_suarl",
                label_fr="SARL ou SUARL",
                groups=(
                    *_RCCM_SOLE_TRADER_GROUPS,
                    Group("Statuts", "all_of", (STATUTES,)),
                    Group("Versement ou apports", "one_of", (PAYMENT_SLIP, CONTRIBUTIONS_TABLE)),
                    Group("CIP des associés", "all_of", (PARTNER_CIP,)),
                ),
                fee=Fee(official_xof=22000, vigo_xof=30000),
            ),
            VariantSeed(
                code="sa_sas_gie_sci_scp",
                label_fr="SA, SAS, GIE, SCI ou SCP",
                groups=(
                    *_RCCM_SOLE_TRADER_GROUPS,
                    Group("Statuts notariés", "all_of", (STATUTES_NOTARIAL,)),
                    Group(
                        "Versement ou apports",
                        "one_of",
                        (PAYMENT_SLIP, CONTRIBUTIONS_TABLE),
                        condition_note_fr="Dépôt d'au moins 1/4 du capital.",
                    ),
                    Group("CIP des associés", "all_of", (PARTNER_CIP,)),
                ),
                fee=Fee(official_xof=37000, vigo_xof=60000),
            ),
        ),
    ),
)

# Global settings. ``None`` means "to be provided by Vigo" (stored as JSON null).
SETTINGS: dict[str, object] = {
    "payment_order": "documents_first",
    "batch_window_ms": 3000,
    "llm_budget_alert_pct": 80,
    "default_delay_days": {"min": 3, "max": 7, "indicative": True, "confirmed": False},
    "delivery_price_floor_xof": {"from": 1000, "grid": None},
    "retention_days_documents": None,
    "retention_days_messages": None,
    "llm_monthly_budget_usd": None,
    "quote_validity_hours": None,
}


@dataclass(frozen=True)
class TemplateSeed:
    name: str
    body_fr: str
    purpose: str
    params_count: int = 0
    language: str = "fr"
    meta_status: str = "local"


# One development-only template, used to exercise the out-of-window path.
# It is NOT a Meta-approved template and carries a provisional text.
TEMPLATES: tuple[TemplateSeed, ...] = (
    TemplateSeed(
        name="dev_out_of_window_test",
        body_fr="[TEST] Un conseiller de Vigo Services vous répondra prochainement.",
        purpose="development test of the out-of-window path",
    ),
)
