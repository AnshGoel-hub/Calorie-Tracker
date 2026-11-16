"""Normalized schema.

Revision ID: 0001
Revises:

Safe on both a fresh database and one created by the old app: `users`, `usage` and `user_data` may
already exist and are left untouched. Run scripts/import_legacy.py afterwards to move old JSON blobs
into the new tables.
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

CASCADE = {"ondelete": "CASCADE"}


def _missing(name: str) -> bool:
    return name not in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _missing("users"):
        op.create_table("users",
                        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                        sa.Column("email", sa.String(255), nullable=False, unique=True),
                        sa.Column("pw_hash", sa.String(100), nullable=False),
                        sa.Column("created", sa.BigInteger, nullable=False))
    if _missing("usage"):
        op.create_table("usage",
                        sa.Column("user_id", sa.Integer, primary_key=True),
                        sa.Column("day", sa.Date, primary_key=True),
                        sa.Column("n", sa.Integer, nullable=False, server_default="0"))
    if _missing("user_data"):
        op.create_table("user_data",
                        sa.Column("user_id", sa.Integer, primary_key=True),
                        sa.Column("kind", sa.String(20), primary_key=True),
                        sa.Column("body", sa.Text, nullable=False),
                        sa.Column("updated", sa.BigInteger, nullable=False, server_default="0"))

    uid = lambda: sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", **CASCADE), nullable=False)  # noqa: E731
    op.create_table("profiles",
                    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", **CASCADE), primary_key=True),
                    sa.Column("age", sa.Float), sa.Column("sex", sa.String(10)), sa.Column("height_cm", sa.Float),
                    sa.Column("weight_kg", sa.Float), sa.Column("activity", sa.String(20)),
                    sa.Column("goal", sa.String(20)),
                    sa.Column("target_kcal", sa.Float, nullable=False, server_default="2000"),
                    sa.Column("weekly_workout_goal", sa.Integer, nullable=False, server_default="3"),
                    sa.Column("setup_done", sa.Boolean, nullable=False, server_default=sa.false()),
                    sa.Column("body_weight_kg", sa.Float, nullable=False, server_default="0"),
                    sa.Column("tracker_updated", sa.BigInteger, nullable=False, server_default="0"),
                    sa.Column("workouts_updated", sa.BigInteger, nullable=False, server_default="0"))

    op.create_table("foods",
                    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", **CASCADE), nullable=False),
                    sa.Column("name", sa.String(200), nullable=False), sa.Column("name_norm", sa.String(200), nullable=False),
                    sa.Column("kcal", sa.Float, nullable=False), sa.Column("protein", sa.Float, nullable=False, server_default="0"),
                    sa.Column("carbs", sa.Float, nullable=False, server_default="0"),
                    sa.Column("fat", sa.Float, nullable=False, server_default="0"),
                    sa.Column("source", sa.String(10), nullable=False, server_default="user"),
                    sa.Column("kind", sa.String(20)),
                    sa.UniqueConstraint("owner_id", "name_norm", name="uq_food_owner_name"))
    op.create_index("ix_foods_owner_id", "foods", ["owner_id"])
    op.create_table("food_units",
                    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("food_id", sa.Integer, sa.ForeignKey("foods.id", **CASCADE), nullable=False),
                    sa.Column("position", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("name", sa.String(40), nullable=False), sa.Column("grams", sa.Float, nullable=False))
    op.create_index("ix_food_units_food_id", "food_units", ["food_id"])

    op.create_table("food_entries",
                    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), uid(),
                    sa.Column("date", sa.Date, nullable=False),
                    sa.Column("meal", sa.String(20), nullable=False, server_default="Snacks"),
                    sa.Column("position", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("name", sa.String(200), nullable=False),
                    sa.Column("label", sa.String(200), nullable=False, server_default=""),
                    sa.Column("grams", sa.Float, nullable=False, server_default="0"),
                    sa.Column("kcal", sa.Float, nullable=False, server_default="0"),
                    sa.Column("protein", sa.Float, nullable=False, server_default="0"),
                    sa.Column("carbs", sa.Float, nullable=False, server_default="0"),
                    sa.Column("fat", sa.Float, nullable=False, server_default="0"),
                    sa.Column("version", sa.Integer, nullable=False, server_default="1"),
                    sa.Column("updated_at", sa.BigInteger, nullable=False, server_default="0"),
                    sa.Column("deleted_at", sa.BigInteger))
    op.create_index("ix_entries_user_date", "food_entries", ["user_id", "date"])
    op.create_index("ix_entries_user_updated", "food_entries", ["user_id", "updated_at"])

    op.create_table("day_logs",
                    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", **CASCADE), primary_key=True),
                    sa.Column("date", sa.Date, primary_key=True),
                    sa.Column("target_kcal", sa.Float, nullable=False, server_default="2000"),
                    sa.Column("water", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("weight_kg", sa.Float), sa.Column("marker_type", sa.String(10)),
                    sa.Column("marker_note", sa.String(60)),
                    sa.Column("version", sa.Integer, nullable=False, server_default="1"),
                    sa.Column("updated_at", sa.BigInteger, nullable=False, server_default="0"))
    op.create_index("ix_daylogs_user_updated", "day_logs", ["user_id", "updated_at"])

    op.create_table("custom_exercises",
                    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", **CASCADE), primary_key=True),
                    sa.Column("slug", sa.String(40), primary_key=True),
                    sa.Column("name", sa.String(120), nullable=False), sa.Column("type", sa.String(4), nullable=False),
                    sa.Column("met", sa.Float, nullable=False, server_default="6"),
                    sa.Column("primary_muscles", sa.String(60), nullable=False, server_default=""),
                    sa.Column("secondary_muscles", sa.String(120), nullable=False, server_default=""))

    op.create_table("workouts",
                    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), uid(),
                    sa.Column("client_id", sa.String(40), nullable=False), sa.Column("date", sa.Date, nullable=False),
                    sa.Column("name", sa.String(120), nullable=False, server_default=""),
                    sa.Column("duration_min", sa.Float, nullable=False, server_default="0"),
                    sa.Column("kcal", sa.Float, nullable=False, server_default="0"),
                    sa.Column("body_weight_kg", sa.Float, nullable=False, server_default="0"),
                    sa.Column("version", sa.Integer, nullable=False, server_default="1"),
                    sa.Column("updated_at", sa.BigInteger, nullable=False, server_default="0"),
                    sa.Column("deleted_at", sa.BigInteger),
                    sa.UniqueConstraint("user_id", "client_id", name="uq_workout_client"))
    op.create_index("ix_workouts_user_date", "workouts", ["user_id", "date"])
    op.create_table("workout_exercises",
                    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("workout_id", sa.Integer, sa.ForeignKey("workouts.id", **CASCADE), nullable=False),
                    sa.Column("position", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("exercise_slug", sa.String(40), nullable=False))
    op.create_index("ix_workout_exercises_workout_id", "workout_exercises", ["workout_id"])
    op.create_table("workout_sets",
                    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("workout_exercise_id", sa.Integer,
                              sa.ForeignKey("workout_exercises.id", **CASCADE), nullable=False),
                    sa.Column("position", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("kind", sa.String(1), nullable=False, server_default="n"),
                    sa.Column("weight", sa.Float), sa.Column("reps", sa.Float),
                    sa.Column("duration", sa.Float), sa.Column("distance_km", sa.Float))
    op.create_index("ix_workout_sets_workout_exercise_id", "workout_sets", ["workout_exercise_id"])

    op.create_table("estimate_cache",
                    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("key", sa.String(64), nullable=False, unique=True),
                    sa.Column("name_norm", sa.String(200), nullable=False), sa.Column("kind", sa.String(20), nullable=False),
                    sa.Column("payload", sa.Text, nullable=False),
                    sa.Column("hits", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("created_at", sa.BigInteger, nullable=False, server_default="0"))


def downgrade() -> None:
    for t in ("estimate_cache", "workout_sets", "workout_exercises", "workouts", "custom_exercises", "day_logs",
              "food_entries", "food_units", "foods", "profiles"):
        op.drop_table(t)
    # users / usage / user_data are shared with the old app and are intentionally kept
