"""workspace (multi-file / multi-sheet + derived recipe)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-29 00:00:00.000000

Additive only — extends the Phase 1/2 schema without breaking existing rows:
  * datasets.source_file  — original upload filename (shared across xlsx sheets)
  * datasets.recipe_code  — code recipe for a derived dataset (used by the
                            derived slice later)
  * workspace_datasets    — association binding MULTIPLE datasets to one
                            conversation, each under a sandbox table_name.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("source_file", sa.Text(), nullable=True))
    op.add_column("datasets", sa.Column("recipe_code", sa.Text(), nullable=True))

    op.create_table(
        "workspace_datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "table_name", name="uq_workspace_conv_table"
        ),
    )


def downgrade() -> None:
    op.drop_table("workspace_datasets")
    op.drop_column("datasets", "recipe_code")
    op.drop_column("datasets", "source_file")
