from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.database import async_session_maker
from modules.users.repositories import UserRepository, AdminRepository
from modules.subscriptions.repositories import (
    SubscriptionAccessRepository,
    SubscriptionRepository,
)
from core.interface.message.repositories import MessageRepository
from core.interface.button.repositories import ButtonRepository
from core.interface.menu.repositories import MenuRepository
from core.interface.settings.repositories import SettingsRepository


class IUnitOfWork(ABC):
    @abstractmethod
    async def commit(self):
        pass

    @abstractmethod
    async def rollback(self):
        pass


class RepositoriesMixin:
    def init_repositories(self, session):
        self.user_repo = UserRepository(session)
        self.message_repo = MessageRepository(session)
        self.button_repo = ButtonRepository(session)
        self.menu_repo = MenuRepository(session)
        self.settings_repo = SettingsRepository(session)
        self.admin_repo = AdminRepository(session)
        self.subscription_repo = SubscriptionRepository(session)
        self.subscription_access_repo = SubscriptionAccessRepository(session)


class UoW(IUnitOfWork, RepositoriesMixin):
    def __init__(self, session: AsyncSession):
        self.session = session
        self.init_repositories(self.session)

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()


class SqlAlchemyUoW(IUnitOfWork, RepositoriesMixin):
    def __init__(self, session_factory = None):
        self.session_factory = session_factory or async_session_maker

    async def __aenter__(self):
        self.session = self.session_factory()
        self.init_repositories(self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        await self.session.close()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()
