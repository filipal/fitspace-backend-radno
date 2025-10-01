"""create avatars table"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20230918_avatars"
down_revision = None
branch_labels = None
depends_on = None


UPDATE_TRIGGER_FUNCTION_NAME = "update_avatars_updated_at_column"
UPDATE_TRIGGER_NAME = "update_avatars_updated_at"

def upgrade() -> None:
    op.create_table(
        "avatars",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(length=50), nullable=True),
        sa.Column("height_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("body_fat_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("shoulder_circumference_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("waist_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("hips_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_avatars_user_id", "avatars", ["user_id"])
    op.create_index("ix_avatars_display_name", "avatars", ["display_name"])
    op.create_index(
        "ix_avatars_display_name_gender",
        "avatars",
        ["display_name", "gender"],
    )

    op.create_foreign_key(
        "fk_avatars_user_id_users",
        "avatars",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {UPDATE_TRIGGER_FUNCTION_NAME}()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {UPDATE_TRIGGER_NAME}
            BEFORE UPDATE ON avatars
            FOR EACH ROW
            EXECUTE FUNCTION {UPDATE_TRIGGER_FUNCTION_NAME}();
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"DROP TRIGGER IF EXISTS {UPDATE_TRIGGER_NAME} ON avatars;"
        )
    )
    op.execute(
        sa.text(
            f"DROP FUNCTION IF EXISTS {UPDATE_TRIGGER_FUNCTION_NAME}();"
        )
    )

    op.drop_constraint("fk_avatars_user_id_users", "avatars", type_="foreignkey")
    op.drop_index("ix_avatars_display_name_gender", table_name="avatars")
    op.drop_index("ix_avatars_display_name", table_name="avatars")
    op.drop_index("ix_avatars_user_id", table_name="avatars")
    op.drop_table("avatars")
