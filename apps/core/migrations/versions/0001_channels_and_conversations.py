"""R1: channels, contacts, conversations, messages, inbound events, templates, consent."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlfile import run_sql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql("0001_up.sql")


def downgrade() -> None:
    run_sql("0001_down.sql")
