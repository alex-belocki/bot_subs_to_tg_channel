import datetime as dt

from telegram.error import TelegramError

from core.constants.config import CHANNEL_ID, INVITE_TTL_SECONDS, SUBSCRIPTION_DAYS
from core.database.uow import UoW


class SubscriptionService:
    def __init__(self, uow: UoW) -> None:
        self.uow = uow

    async def get_active(self, user_id: int, channel_id: int | None = None):
        channel_id = channel_id or CHANNEL_ID
        return await self.uow.subscription_repo.get_active(
            user_id=user_id, channel_id=channel_id
        )

    async def grant_30d(
        self,
        user_id: int,
        channel_id: int | None = None,
        start_at: dt.datetime | None = None,
    ) -> int:
        channel_id = channel_id or CHANNEL_ID
        start_at = start_at or dt.datetime.now(dt.timezone.utc)
        end_at = start_at + dt.timedelta(days=SUBSCRIPTION_DAYS)

        active = await self.get_active(user_id=user_id, channel_id=channel_id)
        if active:
            # Если уже активна — просто продляем до max(active.end_at, now)+SUBSCRIPTION_DAYS
            base = active.end_at if active.end_at > start_at else start_at
            new_end = base + dt.timedelta(days=SUBSCRIPTION_DAYS)
            active.end_at = new_end
            active.status = "active"
            active.start_at = active.start_at or start_at
            await self.uow.commit()
            return active.id

        subscription_id = await self.uow.subscription_repo.add(
            user_id=user_id,
            channel_id=channel_id,
            start_at=start_at,
            end_at=end_at,
            status="active",
        )
        return subscription_id

    async def extend(
        self,
        user_id: int,
        days: int,
        channel_id: int | None = None,
    ) -> int:
        channel_id = channel_id or CHANNEL_ID
        now = dt.datetime.now(dt.timezone.utc)

        sub = await self.get_active(user_id=user_id, channel_id=channel_id)
        if not sub:
            sub_id = await self.uow.subscription_repo.add(
                user_id=user_id,
                channel_id=channel_id,
                start_at=now,
                end_at=now + dt.timedelta(days=days),
                status="active",
            )
            return sub_id

        base = sub.end_at if sub.end_at > now else now
        sub.end_at = base + dt.timedelta(days=days)
        await self.uow.commit()
        return sub.id

    async def revoke(
        self,
        user_id: int,
        reason: str = "revoked_by_admin",
        channel_id: int | None = None,
    ) -> None:
        channel_id = channel_id or CHANNEL_ID
        sub = await self.get_active(user_id=user_id, channel_id=channel_id)
        if not sub:
            return
        sub.status = "revoked"
        sub.revoked_at = dt.datetime.now(dt.timezone.utc)
        sub.revoked_reason = reason
        await self.uow.commit()

    async def create_invite_link(
        self,
        bot,
        user_id: int,
        channel_id: int | None = None,
        ttl_seconds: int | None = None,
        member_limit: int = 1,
        min_interval_seconds: int = 60,
    ) -> tuple[str, dt.datetime, int]:
        """
        Возвращает (invite_link, expire_at, subscription_id).
        Делает rate-limit по последней выдаче инвайта.
        """
        channel_id = channel_id or CHANNEL_ID
        ttl_seconds = ttl_seconds or INVITE_TTL_SECONDS

        if not channel_id:
            raise ValueError("CHANNEL_ID is not set")

        sub = await self.get_active(user_id=user_id, channel_id=channel_id)
        if not sub:
            raise ValueError("no_active_subscription")

        last = await self.uow.subscription_access_repo.get_last_for_subscription(
            subscription_id=sub.id
        )
        now = dt.datetime.now(dt.timezone.utc)
        if last and (now - last.created_at).total_seconds() < min_interval_seconds:
            raise ValueError("invite_rate_limited")

        expire_at = now + dt.timedelta(seconds=ttl_seconds)
        try:
            invite = await bot.create_chat_invite_link(
                chat_id=channel_id,
                member_limit=member_limit,
                expire_date=expire_at,
            )
        except TelegramError as exc:
            raise RuntimeError(f"telegram_invite_error: {exc}") from exc

        await self.uow.subscription_access_repo.add(
            subscription_id=sub.id,
            invite_link=invite.invite_link,
            expire_at=expire_at,
            member_limit=member_limit,
        )
        return invite.invite_link, expire_at, sub.id

