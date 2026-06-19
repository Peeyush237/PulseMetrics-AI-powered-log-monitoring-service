import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        CheckConstraint(
            "rule_type IN ('threshold', 'regex', 'rate_of_change', 'novelty', 'anomaly')",
            name="ck_alert_rules_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    last_fired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    application: Mapped["Application"] = relationship(back_populates="alert_rules")  # type: ignore[name-defined]
    alert_events: Mapped[list["AlertEvent"]] = relationship(back_populates="rule", cascade="all, delete-orphan")  # type: ignore[name-defined]
    channel_bindings: Mapped[list["RuleChannelBinding"]] = relationship(back_populates="rule", cascade="all, delete-orphan")  # type: ignore[name-defined]


class NotificationChannel(Base):
    __tablename__ = "notification_channels"
    __table_args__ = (
        CheckConstraint(
            "channel_type IN ('email', 'slack', 'webhook', 'console')",
            name="ck_notification_channels_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship(back_populates="notification_channels")  # type: ignore[name-defined]
    rule_bindings: Mapped[list["RuleChannelBinding"]] = relationship(back_populates="channel", cascade="all, delete-orphan")  # type: ignore[name-defined]


class RuleChannelBinding(Base):
    __tablename__ = "rule_channel_bindings"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        primary_key=True,
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        primary_key=True,
    )

    rule: Mapped["AlertRule"] = relationship(back_populates="channel_bindings")
    channel: Mapped["NotificationChannel"] = relationship(back_populates="rule_bindings")
