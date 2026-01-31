from enum import Enum

from telegram import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo
)

MEDIA_GROUP_TYPES = {"audio": InputMediaAudio,
                     "document": InputMediaDocument,
                     "photo": InputMediaPhoto,
                     "video": InputMediaVideo}


class Mode(Enum):
    """
    Чтобы при нажатии Отмена
    было понятно куда перенаправлять
    """
    INSPECTOR = 1
    MODERATOR = 2


class ScreenName(str, Enum):
    MAIN = 'main'
