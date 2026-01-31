from abc import ABC, abstractmethod


class IUnitOfWork(ABC):
    @abstractmethod
    async def __enter__(self):
        pass

    @abstractmethod
    async def __exit__(self, *args):
        pass

    @abstractmethod
    async def commit(self):
        pass

    @abstractmethod
    async def rollback(self):
        pass


class BaseUnitOfWork(IUnitOfWork):
    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self.session_factory = session_factory

