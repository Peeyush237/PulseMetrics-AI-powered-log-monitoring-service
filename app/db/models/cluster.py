import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class LogCluster(Base):
    __tablename__ = "log_clusters"
    __table_args__ = (
        Index("idx_clusters_app", "application_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    centroid: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    representative_message: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    member_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    application: Mapped["Application"] = relationship(back_populates="clusters")  # type: ignore[name-defined]
