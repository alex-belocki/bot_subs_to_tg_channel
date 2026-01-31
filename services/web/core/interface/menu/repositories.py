from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database.base_repo import BaseRepository
from common.models.interface_models import Menu


class MenuRepository(BaseRepository):
    model = Menu

    def get(self, **filter_by):
        query = (
            select(self.model)
            .options(
                selectinload(self.model.buttons_list)
            )
            .filter_by(**filter_by)
        )
        result = self.session.execute(query)
        return result.unique().scalar_one_or_none()
