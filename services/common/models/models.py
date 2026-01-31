from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
import common.models.common as cm


class Settings(Base):
    __tablename__ = 'settings'

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str]
    value_: Mapped[str]

    def is_float(self, element) -> bool:
        try:
            float(element)
            return True
        except ValueError:
            return False

    @property
    def value(self):
        if self.value_.lower() == 'true':
            return True
        elif self.value_.lower() == 'false':
            return False
        elif self.value_.isdigit():
            return int(self.value_)
        elif self.is_float(self.value_):
            return float(self.value_)
        return self.value_
