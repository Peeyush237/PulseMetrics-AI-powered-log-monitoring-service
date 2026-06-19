import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_applications_org_name"),
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
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    parser_type: Mapped[str] = mapped_column(String(50), nullable=False, default="json")
    parser_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship(back_populates="applications")  # type: ignore[name-defined]
    logs: Mapped[list["Log"]] = relationship(back_populates="application", cascade="all, delete-orphan")  # type: ignore[name-defined]
    clusters: Mapped[list["LogCluster"]] = relationship(back_populates="application", cascade="all, delete-orphan")  # type: ignore[name-defined]
    alert_rules: Mapped[list["AlertRule"]] = relationship(back_populates="application", cascade="all, delete-orphan")  # type: ignore[name-defined]
