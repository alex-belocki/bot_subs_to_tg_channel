from abc import ABC, abstractmethod
from typing import List, Optional

from sqlalchemy import delete, func, insert, select


class IRepository(ABC):
    @abstractmethod
    async def get(self, **filter_by) -> Optional[object]:
        pass

    @abstractmethod
    async def get_all(self, **filter_by) -> List[object]:
        pass

    @abstractmethod
    async def add(self, **data) -> None:
        pass

    @abstractmethod
    async def delete(self, **kwargs) -> None:
        pass

    @abstractmethod
    async def get_by_page(self, page_num=1, count_per_page=5, **filter_by) -> List[object]:
        pass

    @abstractmethod
    async def get_all_items_count(self, **filter_by) -> int:
        pass


class BaseRepository(IRepository):
    model = None

    def __init__(self, session) -> None:
        self.session = session

    async def get(self, **filter_by):
        query = select(self.model).filter_by(**filter_by)
        result = await self.session.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_all(self, **filter_by):
        query = select(self.model).filter_by(**filter_by).order_by(self.model.id)
        result = await self.session.execute(query)
        return result.unique().scalars().all()

    async def add(self, **data):
        query = insert(self.model).values(**data).returning(self.model.id)
        result = await self.session.execute(query)
        return result.scalar()

    async def add_all(self, items: list):
        self.session.add_all(items)

    async def get_by_page(self, page_num=1, count_per_page=5, **filter_by):
        """Для возможности отбирать постранично"""
        offset = (page_num - 1) * count_per_page
        query = (
            select(self.model)
            .filter_by(**filter_by)
            .offset(offset)
            .limit(count_per_page)
            .order_by(self.model.id)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all_items_count(self, **filter_by):
        query = select(func.count(self.model.id)).filter_by(**filter_by)
        result = await self.session.execute(query)
        return result.scalar()

    async def delete(self, **kwargs):
        query = delete(self.model).filter_by(**kwargs)
        await self.session.execute(query)
