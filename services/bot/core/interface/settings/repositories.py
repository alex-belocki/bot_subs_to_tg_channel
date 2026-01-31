from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database.base_repo import BaseRepository
from common.models.models import Settings


class SettingsRepository(BaseRepository):
    model = Settings
