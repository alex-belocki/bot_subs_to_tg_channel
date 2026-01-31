from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import AsyncSession
from core.database.database import async_session_maker
from core.database.uow import UoW
from modules.users.repositories import UserRepository
from modules.users.services import UserService


class AppContainer(containers.DeclarativeContainer):
    # Фабрика для сессии базы данных
    session = providers.Factory(async_session_maker)

    # Unit of Work с инжектируемой сессией
    uow = providers.Factory(UoW, session=session)

    # Репозитории с инжектируемым UoW
    user_repo = providers.Factory(UserRepository, uow=uow)

    # Сервисы с инжектируемым UoW
    user_service = providers.Factory(UserService, uow=uow)

    # Добавьте другие зависимости по мере необходимости