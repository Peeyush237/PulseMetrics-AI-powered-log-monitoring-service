"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable extensions. NB: the pgvector extension is named "vector" in
    # PostgreSQL (the control file is vector.control) — "pgvector" does not exist.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # organizations
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'member')", name="ck_users_role"),
    )

    # applications
    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("api_key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("parser_type", sa.String(50), nullable=False, server_default="json"),
        sa.Column("parser_config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("retention_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_applications_org_name"),
    )

    # log_clusters
    op.create_table(
        "log_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("centroid", sa.Text, nullable=False),  # stored as vector text, handled by pgvector
        sa.Column("representative_message", sa.Text, nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("member_count", sa.BigInteger, nullable=False, server_default="1"),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("is_acknowledged", sa.Boolean, nullable=False, server_default="false"),
    )

    # Use raw SQL for the vector column and HNSW index
    op.execute("ALTER TABLE log_clusters ALTER COLUMN centroid TYPE vector(384) USING centroid::vector")
    op.execute("CREATE INDEX idx_clusters_centroid ON log_clusters USING hnsw (centroid vector_cosine_ops)")
    op.create_index("idx_clusters_app", "log_clusters", ["application_id"])

    # logs (partitioned by timestamp RANGE)
    op.execute("""
        CREATE TABLE logs (
            id          BIGSERIAL,
            application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            timestamp   TIMESTAMPTZ NOT NULL,
            level       VARCHAR(10) NOT NULL,
            service     VARCHAR(255),
            message     TEXT NOT NULL,
            message_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', message)) STORED,
            raw         TEXT,
            metadata    JSONB NOT NULL DEFAULT '{}',
            cluster_id  UUID,
            PRIMARY KEY (id, timestamp)
        ) PARTITION BY RANGE (timestamp)
    """)
    op.execute("CREATE INDEX idx_logs_app_ts ON logs (application_id, timestamp DESC)")
    op.execute("CREATE INDEX idx_logs_metadata ON logs USING GIN (metadata)")
    op.execute("CREATE INDEX idx_logs_message ON logs USING GIN (message_tsv)")
    op.execute("CREATE INDEX idx_logs_cluster ON logs (cluster_id) WHERE cluster_id IS NOT NULL")

    # Create initial partitions for current and next month
    op.execute("""
        CREATE TABLE logs_2026_06 PARTITION OF logs
            FOR VALUES FROM ('2026-06-01') TO ('2026-07-01')
    """)
    op.execute("""
        CREATE TABLE logs_2026_07 PARTITION OF logs
            FOR VALUES FROM ('2026-07-01') TO ('2026-08-01')
    """)

    # alert_rules
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("cooldown_seconds", sa.Integer, nullable=False, server_default="900"),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "rule_type IN ('threshold', 'regex', 'rate_of_change', 'novelty', 'anomaly')",
            name="ck_alert_rules_type",
        ),
    )

    # alert_events
    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("sample_log_ids", postgresql.ARRAY(sa.BigInteger), nullable=True),
    )
    op.create_index("idx_events_rule_time", "alert_events", ["rule_id", "fired_at"])

    # notification_channels
    op.create_table(
        "notification_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("channel_type", sa.String(50), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "channel_type IN ('email', 'slack', 'webhook', 'console')",
            name="ck_notification_channels_type",
        ),
    )

    # rule_channel_bindings
    op.create_table(
        "rule_channel_bindings",
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("notification_channels.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("rule_channel_bindings")
    op.drop_table("notification_channels")
    op.drop_index("idx_events_rule_time", table_name="alert_events")
    op.drop_table("alert_events")
    op.drop_table("alert_rules")
    op.execute("DROP TABLE IF EXISTS logs CASCADE")
    op.drop_index("idx_clusters_app", table_name="log_clusters")
    op.execute("DROP INDEX IF EXISTS idx_clusters_centroid")
    op.drop_table("log_clusters")
    op.drop_table("applications")
    op.drop_table("users")
    op.drop_table("organizations")
