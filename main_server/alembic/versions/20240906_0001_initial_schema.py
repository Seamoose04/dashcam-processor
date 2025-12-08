"""initial schema for tasks and ingestion"""

from alembic import op
import sqlalchemy as sa


revision = "20240906_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("video_id", sa.String(), primary_key=True),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("trip_date", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
    )

    op.create_table(
        "tasks",
        sa.Column("task_id", sa.String(), primary_key=True),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("device_class", sa.String(), nullable=False),
        sa.Column("video_id", sa.String(), sa.ForeignKey("videos.video_id"), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("inputs", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("state in ('pending','complete')", name="ck_tasks_state"),
    )
    op.create_index("idx_tasks_state_device_created", "tasks", ["state", "device_class", "created_at"])

    op.create_table(
        "ingestion_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("video_id", sa.String(), sa.ForeignKey("videos.video_id"), nullable=False),
        sa.Column("device", sa.String(), nullable=True),
        sa.Column("path", sa.String(), nullable=True),
        sa.Column("received_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("ingestion_events")
    op.drop_index("idx_tasks_state_device_created", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("videos")
