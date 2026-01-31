import datetime as dt
from typing import List

from core.database.uow import UoW
from modules.users.repositories import User, UserRepository


class BaseUserService:
    def __init__(self, uow: UoW) -> None:
        self.uow = uow

    async def add_user(self, user_id: int, first_name: str,
                       username: str = None, **kwargs):
        user_id = await self.uow.user_repo.add(
            user_id=user_id,
            first_name=first_name,
            username=username,
            created_at=dt.datetime.now(),
            **kwargs
        )
        user = await self.uow.user_repo.get(user_id=user_id)
        return user

    async def get_user(self, user_id: int) -> User:
        return await self.uow.user_repo.get(user_id=user_id)

    async def get_users(self) -> List[User]:
        return await self.uow.user_repo.get_all()

    async def delete_user(self, user_id: int):
        await self.uow.user_repo.delete(user_id=user_id)



class UserService(BaseUserService):

    async def update_user(self, user_id: int, **values):
        await self.uow.user_repo.update_user(user_id, **values)

    def get_source(self, text: str):
        if not text:
            return
        if '/start' not in text:
            return

        text_list = text.split()
        raw_source = text_list[-1] if len(text_list) == 2 else None
        return raw_source
