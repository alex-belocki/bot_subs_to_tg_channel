import logging
from pathlib import Path
import traceback
from typing import Generator, List

from telegram import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo
)
from telegram.constants import ParseMode
from telegram.ext import ExtBot

from core.constants.config import STATIC_FOLDER


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.INFO
    )


class TelegramMessageSender:
    def __init__(self, name: str, recipients: Generator[int, None, None] | int,
                 text: str = None, preview: bool = False,
                 send_post: bool = False,
                 channel_id: int = None,
                 reply_markup=None, files_list: List = None,
                 bot: ExtBot = None) -> None:
        self.name = name
        self.recipients = recipients
        self.text = text
        self.preview = preview
        self.send_post = send_post
        self.channel_id = channel_id
        self.reply_markup = reply_markup
        self.files_list = files_list
        self.bot = bot

    def get_markup(self):
        return self.reply_markup

    def _get_file_type(self, file_path: str):
        extension_to_type = {
            'jpg': 'photo',
            'jpeg': 'photo',
            'png': 'photo',
            'gif': 'animation',
            'mp4': 'video_note',
            'mkv': 'video',
            'avi': 'video',
            'mp3': 'voice',
            'wav': 'voice',
            'ogg': 'voice',
            'oga': 'voice',
            'pdf': 'document',
            'doc': 'document',
            'txt': 'document',
            'docx': 'document',
            'ppt': 'document',
            'pptx': 'document',
            'xls': 'document',
            'xlsx': 'document',
            'zip': 'document',
            'rar': 'document',
            'tar': 'document',
            '7z': 'document'
        }
        extension = file_path.split('.')[-1].lower()
        return extension_to_type.get(extension, 'unknown')

    @property
    def message_type(self):
        if not self.files_list:
            return 'message'
        elif len(self.files_list) > 1:
            return 'media_group'
        return self._get_file_type(self.files_list[0])

    def _get_media_obj(self, media_type: str = None):
        if media_type == 'audio':
            return InputMediaAudio
        elif media_type == 'video':
            return InputMediaVideo
        elif media_type == 'document':
            return InputMediaDocument
        elif media_type == 'photo':
            return InputMediaPhoto

    async def get_kwargs(self, chat_id: int = None):
        kwargs = dict(chat_id=chat_id)
        if self.message_type == 'message':
            kwargs.update({'text': self.get_text(),
                           'reply_markup': self.get_markup(),
                           'parse_mode': ParseMode.HTML})

        elif self.message_type in ['document', 'photo', 'video', 'voice']:
            kwargs.update(
                {'caption': self.get_caption(),
                 'reply_markup': self.get_markup(),
                 'parse_mode': ParseMode.HTML,
                 self.message_type: self.get_file_data()}
            )

        elif self.message_type == 'video_note':
            kwargs.update({'video_note': self.get_file_data(),
                           'reply_markup': self.get_markup()})

        elif self.message_type == 'media_group':
            kwargs.update({'media': self.get_media_group()})

        return kwargs

    def get_file_data(self):
        file = self.files_list[0]
        return open(Path(STATIC_FOLDER, file), 'rb')

    @property
    def is_media_group(self):
        return self.message_type == 'media_group'

    @property
    def is_file(self):
        return self.message_type in ['document', 'photo',
                                     'video', 'voice']

    def get_text(self):
        return self.text

    def get_caption(self):
        return (
            self.text if
            self.is_file or self.is_media_group
            else None
        )

    def get_media_group(self):
        media_list = []
        for index, file in enumerate(self.files_list, start=1):
            file_type = self._get_file_type(file)
            MediaObj = self._get_media_obj(file_type)

            file_path = Path(STATIC_FOLDER, file)

            if index == len(self.files_list):
                media_list.append(
                    MediaObj(open(file_path, 'rb'),
                             caption=self.get_caption(),
                             parse_mode=ParseMode.HTML)
                )
            else:
                media_list.append(MediaObj(open(file_path, 'rb')))
        return media_list

    async def send_one(self, chat_id=None):
        try:
            method = getattr(self.bot, f'send_{self.message_type}')
            kwargs = await self.get_kwargs(chat_id)
            msg = await method(**kwargs)
            return msg
        except Exception:
            logging.info(str(traceback.format_exc()))

    async def send(self):
        if isinstance(self.recipients, int):
            await self.send_one(chat_id=self.recipients)
            return

        for chat_id in self.recipients:
            await self.send_one(chat_id=chat_id)


class MessageCampaign:
    def __init__(self, sender, campaign_model, session=None):
        self.sender = sender
        self.session = session
        self.campaign_model = campaign_model

    async def send(self):
        await self.sender.send()
        self.campaign_model.status = 'Завершена'
