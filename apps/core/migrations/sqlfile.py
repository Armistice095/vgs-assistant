"""Helper to run the SQL files that hold the DDL of each revision."""

from pathlib import Path

from alembic import op

_SQL_DIR = Path(__file__).parent / "sql"


def run_sql(name: str) -> None:
    # exec_driver_sql sends the file as is (several statements, no bind parameters).
    op.get_bind().exec_driver_sql((_SQL_DIR / name).read_text(encoding="utf-8"))
