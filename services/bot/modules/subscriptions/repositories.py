import datetime as dt
from typing import Optional

from sqlalchemy import desc, func, select

from core.database.base_repo import BaseRepository
from common.models.subscriptions_models import Subscription, SubscriptionAccess


class SubscriptionRepository(BaseRepository):
    model = Subscription

    async def get_active(self, user_id: int, channel_id: int) -> Optional[Subscription]:
        query = (
            select(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.channel_id == channel_id,
                self.model.status == "active",
            )
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_active(self, channel_id: int, limit: int = 50) -> list[Subscription]:
        query = (
            select(self.model)
            .where(
                self.model.channel_id == channel_id,
                self.model.status == "active",
            )
            .order_by(self.model.end_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_expired_active(self, now: dt.datetime) -> list[Subscription]:
        query = (
            select(self.model)
            .where(
                self.model.status == "active",
                self.model.end_at < now,
            )
            .order_by(self.model.end_at.asc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_by_status(self, channel_id: int) -> dict[str, int]:
        query = (
            select(self.model.status, func.count(self.model.id))
            .where(self.model.channel_id == channel_id)
            .group_by(self.model.status)
        )
        result = await self.session.execute(query)
        return {status: cnt for status, cnt in result.all()}


class SubscriptionAccessRepository(BaseRepository):
    model = SubscriptionAccess

    async def get_last_for_subscription(
        self, subscription_id: int
    ) -> Optional[SubscriptionAccess]:
        query = (
            select(self.model)
            .where(self.model.subscription_id == subscription_id)
            .order_by(desc(self.model.created_at))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

