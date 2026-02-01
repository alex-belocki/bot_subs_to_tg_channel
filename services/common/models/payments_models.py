import datetime as dt
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id"), index=True, nullable=False
    )

    # robokassa | cryptobot (пока используем robokassa)
    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    # Для RUB достаточно 2 знаков после запятой, но для TON нужны дробные значения.
    # Поэтому храним с повышенной точностью (на уровне БД).
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 9), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    # pending | success | failed | canceled
    status: Mapped[str] = mapped_column(String(16), index=True, nullable=False)

    # Идентификаторы/метаданные у провайдера (для CryptoBot/CryptoPay API и идемпотентности).
    provider_payment_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    provider_invoice_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    provider_payload: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, index=True
    )

    signature_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Для аудита/отладки: входящие параметры callback'а (ResultURL)
    raw_callback: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    paid_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Идемпотентность на стороне bot-consumer (обработка payment.succeeded)
    processed_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    def __repr__(self) -> str:
        inv = f" invoice={self.provider_invoice_id}" if self.provider_invoice_id else ""
        return (
            f"<Payment {self.id} provider={self.provider} user={self.user_id} "
            f"status={self.status} amount={self.amount} {self.currency}{inv}>"
        )

