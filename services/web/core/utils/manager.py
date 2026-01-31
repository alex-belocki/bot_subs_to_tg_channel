from core.database.database import db
from common.models.users_models import User
from .base_manager import BaseMessageManager


class MessageManager(BaseMessageManager):
    def get_user(self, user_id):
        return self.session.query(User).filter_by(user_id=user_id).first()
