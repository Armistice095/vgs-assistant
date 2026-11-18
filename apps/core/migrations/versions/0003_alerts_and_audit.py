"""R3: alerts, audit log, immutability triggers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlfile import run_sql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql("0003_up.sql")


def downgrade() -> None:
    run_sql("0003_down.sql")
