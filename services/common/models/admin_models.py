from flask_login import UserMixin
from sqlalchemy.orm import Mapped
from werkzeug.security import check_password_hash

from .base import Base
import common.models.common as cm


class AdminModel(Base, UserMixin):
    __tablename__ = 'admin_model'

    id: Mapped[cm.intpk]
    username: Mapped[str]
    password: Mapped[str]

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def __repr__(self):
        return f'<Admin {self.id} - {self.username}>'
