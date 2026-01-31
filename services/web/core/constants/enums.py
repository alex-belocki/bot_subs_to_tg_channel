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
