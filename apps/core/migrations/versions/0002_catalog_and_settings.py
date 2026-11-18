"""R2: versioned catalogue and settings."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlfile import run_sql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql("0002_up.sql")


def downgrade() -> None:
    run_sql("0002_down.sql")
