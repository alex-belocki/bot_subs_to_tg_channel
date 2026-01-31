from core.database.base_repo import BaseRepository
from common.models.users_models import User


class UserRepository(BaseRepository):
    model = User
