import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    users: Mapped[list["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")  # type: ignore[name-defined]
    applications: Mapped[list["Application"]] = relationship(back_populates="organization", cascade="all, delete-orphan")  # type: ignore[name-defined]
    notification_channels: Mapped[list["NotificationChannel"]] = relationship(back_populates="organization", cascade="all, delete-orphan")  # type: ignore[name-defined]
