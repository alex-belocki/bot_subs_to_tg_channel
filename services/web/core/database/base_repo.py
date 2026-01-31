from abc import ABC, abstractmethod
from typing import List, Optional

from sqlalchemy import delete, func, insert, select


class IRepository(ABC):
    @abstractmethod
    def get(self, **filter_by) -> Optional[object]:
        pass

    @abstractmethod
    def get_all(self, **filter_by) -> List[object]:
        pass

    @abstractmethod
    def add(self, **data) -> None:
        pass

    @abstractmethod
    def delete(self, **kwargs) -> None:
        pass

    @abstractmethod
    def get_by_page(self, page_num=1, count_per_page=5, **filter_by) -> List[object]:
        pass

    @abstractmethod
    def get_all_items_count(self, **filter_by) -> int:
        pass


class BaseRepository(IRepository):
    model = None

    def __init__(self, session) -> None:
        self.session = session

    def get(self, **filter_by):
        query = select(self.model).filter_by(**filter_by)
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def get_all(self, **filter_by):
        query = select(self.model).filter_by(**filter_by).order_by(self.model.id)
        result = self.session.execute(query)
        return result.scalars().all()

    def add(self, **data):
        query = insert(self.model).values(**data).returning(self.model.id)
        result = self.session.execute(query)
        return result.scalar()

    def get_by_page(self, page_num=1, count_per_page=5, **filter_by):
        """Для возможности отбирать постранично"""
        offset = (page_num - 1) * count_per_page
        query = (
            select(self.model)
            .filter_by(**filter_by)
            .offset(offset)
            .limit(count_per_page)
            .order_by(self.model.id)
        )
        result = self.session.execute(query)
        return result.scalars().all()

    def get_all_items_count(self):
        query = select(func.count(self.model.id))
        result = self.session.execute(query)
        return result.scalar()

    def delete(self, **kwargs):
        query = delete(self.model).filter_by(**kwargs)
        self.session.execute(query)

    def get_model(self, model, model_id):
        query = select(model).filter_by(id=model_id)
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def add_model(self, model, **data):
        query = insert(model).values(**data).returning(self.model.id)
        result = self.session.execute(query)
        return result.scalar()

    @classmethod
    def __call__(cls, session):
        return cls(session)
