"""Recipes table and an ingredient snapshot on food entries.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("food_entries") as b:
        b.add_column(sa.Column("ingredients", sa.Text, nullable=True))
    op.create_table("recipes",
                    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("name", sa.String(200), nullable=False),
                    sa.Column("name_norm", sa.String(200), nullable=False),
                    sa.Column("portions", sa.Float, nullable=False, server_default="1"),
                    sa.Column("kcal", sa.Float, nullable=False, server_default="0"),
                    sa.Column("protein", sa.Float, nullable=False, server_default="0"),
                    sa.Column("carbs", sa.Float, nullable=False, server_default="0"),
                    sa.Column("fat", sa.Float, nullable=False, server_default="0"),
                    sa.Column("ingredients", sa.Text, nullable=False),
                    sa.Column("version", sa.Integer, nullable=False, server_default="1"),
                    sa.Column("updated_at", sa.BigInteger, nullable=False, server_default="0"),
                    sa.UniqueConstraint("owner_id", "name_norm", name="uq_recipe_owner_name"))
    op.create_index("ix_recipes_owner_id", "recipes", ["owner_id"])


def downgrade() -> None:
    op.drop_table("recipes")
    with op.batch_alter_table("food_entries") as b:
        b.drop_column("ingredients")