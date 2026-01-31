import datetime as dt
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id"), index=True
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)

    start_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # active | expired | revoked
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    revoked_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[Optional[str]]

    access_list: Mapped[list["SubscriptionAccess"]] = relationship(
        back_populates="subscription",
        cascade="save-update",
    )

    def __repr__(self) -> str:
        return f"<Subscription {self.id} user={self.user_id} status={self.status}>"


class SubscriptionAccess(Base):
    __tablename__ = "subscription_access"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id"), index=True
    )

    invite_link: Mapped[str]
    expire_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    member_limit: Mapped[int] = mapped_column(default=1)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    used_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    subscription: Mapped[Subscription] = relationship(back_populates="access_list")

    def __repr__(self) -> str:
        return f"<SubscriptionAccess {self.id} sub={self.subscription_id}>"

