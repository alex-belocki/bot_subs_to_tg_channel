import asyncio
import os

from modules.tasks.broker import broker
import logging

import datetime as dt
from decimal import Decimal
from telegram import Bot
from telegram.error import TelegramError

from core.constants.config import CHANNEL_ID, TOKEN
from core.database.uow import SqlAlchemyUoW
from common.events import PaymentSucceededEvent
from common.models.payments_models import Payment

import nats
from nats.js.api import StreamConfig
from sqlalchemy import select

logger = logging.getLogger(__name__)


@broker.task()
async def simple_task():
    logger.info('Simple task 1 is running')
    await asyncio.sleep(15)
    logger.info('Simple task 1 is done')


@broker.task(schedule=[{"cron": "*/1 * * * *", "args": [1]}])
async def heavy_task(value: int) -> int:
    result = value + 1
    logger.info(f"Heavy task result: {result}")
    return result


@broker.task(schedule=[{"cron": "*/10 * * * *"}])
async def subscriptions_expire_and_kick() -> None:
    """
    Периодическая задача:
    - ищет активные подписки с end_at < now()
    - пытается удалить пользователя из канала
    - помечает подписку expired
    """
    if not TOKEN:
        logger.warning("TOKEN is not set, skipping subscriptions_expire_and_kick")
        return
    if not CHANNEL_ID:
        logger.warning("CHANNEL_ID is not set, skipping subscriptions_expire_and_kick")
        return

    bot = Bot(token=TOKEN)
    now = dt.datetime.now(dt.timezone.utc)

    async with SqlAlchemyUoW() as uow:
        subs = await uow.subscription_repo.get_expired_active(now=now)
        if not subs:
            return

        for sub in subs:
            chat_id = sub.channel_id or CHANNEL_ID
            try:
                await bot.ban_chat_member(chat_id=chat_id, user_id=sub.user_id)
                await bot.unban_chat_member(chat_id=chat_id, user_id=sub.user_id)
            except TelegramError as exc:
                # Если пользователь уже не в канале — считаем успехом.
                msg = str(exc).lower()
                if "not a member" not in msg and "user not found" not in msg:
                    logger.exception(
                        "Failed to kick user_id=%s from chat_id=%s: %s",
                        sub.user_id,
                        chat_id,
                        exc,
                    )

            sub.status = "expired"

        await uow.commit()


async def _publish_payment_succeeded_events(events: list[PaymentSucceededEvent]) -> None:
    if not events:
        return
    nc = await nats.connect("nats://nats:4222")
    js = nc.jetstream()

    stream_config = StreamConfig(
        name="payments",
        subjects=["payment.succeeded"],
        retention="workqueue",
        max_msgs=100000,
    )
    try:
        await js.add_stream(config=stream_config)
    except nats.js.errors.APIError as exc:
        if "stream name already in use" not in str(exc):
            raise

    for event in events:
        await js.publish("payment.succeeded", event.model_dump_json().encode("utf-8"))
    await nc.close()


@broker.task(schedule=[{"cron": "*/2 * * * *"}])
async def payments_reconcile_cryptobot_pending() -> None:
    """
    Фолбэк на случай потери webhook:
    - ищет pending платежи CryptoBot
    - проверяет статус invoice через Crypto Pay API (aiosend)
    - если PAID — переводит payment в success и публикует payment.succeeded
    """
    token = (os.getenv("CRYPTOBOT_TOKEN") or "").strip()
    if not token:
        logger.info("CRYPTOBOT_TOKEN is not set, skipping payments_reconcile_cryptobot_pending")
        return

    min_age_seconds = int(os.getenv("CRYPTOBOT_RECONCILE_MIN_AGE_SECONDS") or "30")
    limit = int(os.getenv("CRYPTOBOT_RECONCILE_LIMIT") or "50")
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(seconds=min_age_seconds)

    try:
        from aiosend import CryptoPay
    except Exception as exc:
        logger.warning("aiosend is not available, skipping reconcile: %s", exc)
        return

    async with SqlAlchemyUoW() as uow:
        res = await uow.session.execute(
            select(Payment)
            .where(
                Payment.provider == "cryptobot",
                Payment.status == "pending",
                Payment.provider_invoice_id.is_not(None),
                Payment.created_at < cutoff,
            )
            .order_by(Payment.created_at.asc())
            .limit(limit)
        )
        payments = res.scalars().all()
        if not payments:
            return

        invoice_ids: list[int] = []
        by_invoice_id: dict[int, Payment] = {}
        for p in payments:
            try:
                inv_id = int(p.provider_invoice_id or "")
            except ValueError:
                continue
            invoice_ids.append(inv_id)
            by_invoice_id[inv_id] = p

        if not invoice_ids:
            return

        cp = CryptoPay(token=token)
        try:
            invoices = await cp.get_invoices(invoice_ids=invoice_ids)
        except Exception as exc:
            logger.warning("cryptobot get_invoices failed: %s", exc)
            return

        events: list[PaymentSucceededEvent] = []
        for inv in invoices:
            p = by_invoice_id.get(int(inv.invoice_id))
            if not p:
                continue
            if str(inv.status) != "paid":
                continue
            if str(inv.asset) != "TON":
                continue

            incoming_amount = Decimal(str(inv.amount)).quantize(Decimal("0.000000001"))
            expected_amount = Decimal(str(p.amount)).quantize(Decimal("0.000000001"))
            if incoming_amount != expected_amount:
                logger.warning(
                    "cryptobot amount mismatch payment_id=%s invoice_id=%s expected=%s got=%s",
                    p.id,
                    inv.invoice_id,
                    expected_amount,
                    incoming_amount,
                )
                continue

            # Идемпотентность: если уже успели обработать (например webhook), пропускаем.
            if p.status == "success":
                continue

            p.status = "success"
            p.signature_verified = True  # verified via polling
            p.paid_at = now
            p.provider_invoice_id = p.provider_invoice_id or str(inv.invoice_id)
            p.provider_payload = p.provider_payload or (inv.payload if inv.payload else None)
            p.raw_callback = {
                "reconcile": True,
                "invoice": inv.model_dump(),
            }

            events.append(
                PaymentSucceededEvent(
                    payment_id=p.id,
                    user_id=int(p.user_id),
                    provider=p.provider,
                    amount=str(p.amount),
                    currency=p.currency,
                    paid_at=now,
                )
            )

        if not events:
            return

        await uow.commit()

    # Публикация событий делается после коммита, чтобы consumer видел консистентные данные.
    await _publish_payment_succeeded_events(events)
