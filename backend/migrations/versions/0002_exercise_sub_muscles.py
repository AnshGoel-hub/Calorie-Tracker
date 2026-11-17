"""Optional sub-muscle ids on custom exercises.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("custom_exercises") as b:
        b.add_column(sa.Column("sub_muscles", sa.String(120), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("custom_exercises") as b:
        b.drop_column("sub_muscles")
