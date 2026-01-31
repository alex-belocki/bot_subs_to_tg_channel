from sqlalchemy import insert, select, update

from core.database.base_repo import BaseRepository
from common.models.admin_models import AdminModel
from common.models.users_models import User


class UserRepository(BaseRepository):
    model = User

    async def add(self, **data):
        query = insert(self.model).values(**data).returning(self.model.user_id)
        result = await self.session.execute(query)
        return result.scalar()

    async def get(self, **filter_by):
        query = select(self.model).filter_by(**filter_by)
        result = await self.session.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_all(self, **filter_by):
        query = (
            select(self.model)
            .filter_by(**filter_by)
            .order_by(self.model.user_id)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_user(self, user_id: int, **values):
        query = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(**values)
        )
        result = await self.session.execute(query)
        if result.rowcount == 0:
            raise ValueError(f'Не удалось обновить {id}, values: {values}')


class AdminRepository(BaseRepository):
    model = AdminModel
