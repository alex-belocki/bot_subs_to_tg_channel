import logging
import os
from pathlib import Path
import traceback
from typing import Literal, Tuple, TypedDict, Union

from sqlalchemy import select
from telegram import (
    Bot,
    Contact,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update
)

from telegram.constants import ParseMode
from telegram.ext import ConversationHandler, ContextTypes, ExtBot
from telegram.helpers import effective_message_type
from urllib.parse import urlencode, quote

from core.constants.config import DEV_MODE, STATIC_FOLDER, TOKEN
from core.database.database import db
from core.constants.enums import MEDIA_GROUP_TYPES
from core.interface.services import ButtonRepository, MenuRepository, MessageRepository
from modules.user.repositories import UserRepository
from common.models.interface_models import Button, Menu, Message
from common.models.models import Settings
from core.interface.services import BotInterfaceService


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.INFO
    )


class MsgDict(TypedDict):
    media_type: Literal["video", "photo"]
    media_id: str
    caption: str
    post_id: int


class BaseMessageManager:
    def __init__(self, update: Update = None,
                 context: ContextTypes.DEFAULT_TYPE = None,
                 bot: Bot = None, chat_id: int = None,
                 user_id: int = None,
                 session=None):
        self.update = update
        self.context = context
        self._chat_id = chat_id  # когда явно указали
        self._user_id = user_id
        self._bot = bot
        self.query = update.callback_query if self.update else None
        self.parse_mode = ParseMode.HTML
        self._session = session
        self.kb = None
        self.STATIC_IMAGES = Path(STATIC_FOLDER, 'img')
        self.STATIC_FILES = Path(STATIC_FOLDER, 'files')

    @property
    def session(self):
        return self._session

    def __enter__(self):
        # Логика, которая будет выполняться при открытии контекста
        if not self._session:
            self._session = db.session
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Логика, которая будет выполняться при закрытии контекста
        if self._session:
            self._session.close()
            self._session = None

    @property
    def message(self) -> Message | None:
        if self.query:
            return self.query.message
        return self.update.message if self.update else None

    @property
    def chat_member(self):
        if not self.update:
            return None

        if self.update.chat_member:
            return self.update.chat_member.new_chat_member
        return None

    @property
    def message_id(self) -> int | None:
        if self.context and self.context.user_data:
            return self.context.user_data.get('msg_id')
        return None

    @message_id.setter
    def message_id(self, value):
        if not (self.context is not None and self.context.user_data is not None):
            raise ValueError('Нельзя присвоить значение: не найден user_id')
        if not isinstance(value, int):
            raise ValueError(f'Должно быть число, передано: {value}')
        self.context.user_data['msg_id'] = value

    @property
    def contact(self) -> Contact | None:
        if self.update and not self.query:
            return self.update.message.contact
        return None

    @property
    def is_query(self) -> bool:
        if self.query:
            return True
        return False

    @property
    def payload(self) -> list | int | None:
        if self.is_query and self.query.data:
            payload_list = [
                int(data) for data in self.query.data.split('_') if
                data.isdigit()
            ]
            if not payload_list:
                return None
            if len(payload_list) == 1:
                return payload_list[-1]
            else: return payload_list
        return None

    @property
    def chat_id(self) -> int:
        if self._chat_id:
            return self._chat_id

        if self.is_query:
            return self.query.message.chat_id
        return self.update.message.chat_id

    @chat_id.setter
    def chat_id(self, value):
        self._chat_id = value

    @property
    def user_id(self) -> int:
        if self._user_id:
            return self._user_id
        if self.is_query:
            return self.query.from_user.id
        if self.message:
            return self.message.from_user.id
        elif self.chat_member:
            return self.chat_member.user.id

    @property
    def first_name(self) -> str:
        if self.is_query:
            return self.query.from_user.first_name
        if self.message:
            return self.message.from_user.first_name
        elif self.chat_member:
            return self.chat_member.user.first_name

    @property
    def username(self) -> str:
        if self.is_query:
            return self.query.from_user.username
        if self.message:
            return self.message.from_user.username
        elif self.chat_member:
            return self.chat_member.user.username

    @property
    def bot(self) -> Bot:
        if self._bot:
            return self._bot
        if self.context:
            return self.context.bot
        return ExtBot(token=TOKEN)

    @property
    def bot_url(self) -> str:
        return f'https://t.me/{self.bot.username}'

    @property
    def partner_link(self) -> str:
        """Ссылка для привлечения партнёров"""
        return f'{self.bot_url}?start={self.user_id}'

    @property
    def is_conv(self) -> bool:
        return self.context.user_data.get('is_conv') or False

    @is_conv.setter
    def is_conv(self, value):
        if not isinstance(value, bool):
            raise ValueError('is_conv может быть равен True или False')
        self.context.user_data['is_conv'] = value

    @property
    def end_conversation(self):
        if self.is_conv:
            self.is_conv = False
            return ConversationHandler.END

    def get_button(self, slug: str):
        query = select(Button).filter_by(slug=slug)
        result = self.session.execute(query)
        return result.scalar()

    def get_button_by_text(self, text: str):
        return (
            BotInterfaceService(self.session)
            .get_button_by_text(text)
        )

    def config(self, key: str):
        query = select(Settings).filter_by(key=key)
        result = self.session.execute(query)
        return result.scalar()

    def get_markup(self, message=None,
                   **kwargs) -> InlineKeyboardMarkup | ReplyKeyboardMarkup | None:
        if 'reply_markup' in kwargs:
            return kwargs['reply_markup']

        if not message.menu_id:
            return None

        lang = self.get_lang()
        keyboard = (
            BotInterfaceService(self.session)
            .get_keyboard(menu=message.menu, lang=lang, **kwargs)
        )

        return keyboard

    def get_text(self, message, **kwargs) -> str:
        if 'text' in kwargs:
            return kwargs['text']

        lang = self.get_lang()
        text = getattr(message, f'text_{lang}')
        return text.format(**kwargs)

    def get_caption(self, message, **kwargs) -> str:
        if 'caption' in kwargs:
            return kwargs['caption']

        lang = self.get_lang()
        text = getattr(message, f'text_{lang}')
        return text.format(**kwargs)

    def get_photo(self, message, **kwargs):
        if 'photo' in kwargs:
            return kwargs['photo']
        image_path = os.path.join(STATIC_FOLDER, message.image_path)
        return message.image_id or open(image_path, 'rb')

    def get_message_id(self, **kwargs) -> int:
        if 'msg_id' in kwargs:
            return kwargs['msg_id']
        return self.message_id

    def get_lang(self):
        user_repo = UserRepository(self.session)
        user = user_repo.get(user_id=self.user_id)
        if not user:
            return 'ru'
        return user.lang

    def get_text_and_markup(self, slug, **kwargs) \
            -> Tuple[str, Union[InlineKeyboardMarkup, ReplyKeyboardMarkup]]:
        message_repo = MessageRepository(self.session)
        message = message_repo.get(slug=slug)
        text = self.get_text(message, **kwargs)
        markup = self.get_markup(message, **kwargs)
        return text, markup

    async def send_message(self, slug=None,
                           disable_web_page_preview=False,
                           **kwargs) -> Message:

        text, reply_markup = self.get_text_and_markup(slug, **kwargs)

        msg = await self.bot.send_message(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else  self.chat_id,
            text=text,
            disable_web_page_preview=disable_web_page_preview,
            reply_markup=reply_markup,
            parse_mode=self.parse_mode
            )

        return msg

    async def send_photo(self, slug=None, **kwargs) -> Message:

        message_repo = MessageRepository(self.session)
        message = message_repo.get(slug=slug)

        msg = await self.bot.send_photo(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else  self.chat_id,
            photo=self.get_photo(message, **kwargs),
            caption=self.get_caption(message, **kwargs),
            reply_markup=self.get_markup(message, **kwargs),
            parse_mode=self.parse_mode
            )

        if not message.image_id:
            message.image_id = msg.photo[-1].file_id
            self.session.commit()

        return msg

    def get_media(self, message, **kwargs):
        if 'files_list' in kwargs:
            files_list = kwargs['files_list']
        else: files_list = message.files_list

        media_list = []
        for file in files_list:
            InputMediaObject = MEDIA_GROUP_TYPES[file.file_type]
            tg_id = getattr(file, f'{file.file_type}_id')
            media_list.append(InputMediaObject(tg_id))
        return media_list

    async def send_media_group(self, slug=None, **kwargs) -> Message:
        message_repo = MessageRepository(self.session)
        message = message_repo.get(slug=slug)

        msg_list = await self.bot.send_media_group(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else self.chat_id,
            media=self.get_media(message, **kwargs),
            caption=self.get_caption(message, **kwargs),
            parse_mode=self.parse_mode
            )
        return msg_list

    async def edit_message_text(self, slug=None,
                                disable_web_page_preview=False,
                                **kwargs) -> Message:

        text, reply_markup = self.get_text_and_markup(slug, **kwargs)

        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.get_message_id(**kwargs),
                text=text,
                reply_markup=reply_markup,
                parse_mode=self.parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
        except Exception:
            logging.info(f'Error: {str(traceback.format_exc())}')

    async def edit_message_reply_markup(self, **kwargs) -> Message:

        reply_markup = self.get_markup(**kwargs)

        try:
            await self.bot.edit_message_reply_markup(
                chat_id=self.chat_id,
                message_id=self.get_message_id(**kwargs),
                reply_markup=reply_markup
            )
        except Exception:
            logging.info(f'Ошибка: {str(traceback.format_exc())}')

    async def pin_chat_message(self, chat_id, **kwargs):
        await self.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=self.get_message_id(**kwargs)
        )

    def save_message_id(self, message_id: int):
        if self.context:
            self.context.user_data['msg_id'] = message_id

    def add_to_context(self, key, value):
        self.context.user_data[key] = value

    def get_from_context(self, key):
        return self.context.user_data.get(key)

    async def delete_message(self, message_id: int = None):
        if not message_id:
            message_id = self.message.message_id
        try:
            await self.bot.delete_message(
                chat_id=self.chat_id,
                message_id=message_id
            )
        except Exception as exc:
            logging.info(f'Ошибка: {str(exc)}')

    @property
    def is_back_button(self) -> bool:
        if self.is_query and 'back' in self.query.data:
            return True
        return False

    @property
    def is_main_button(self) -> bool:
        if self.is_query and ('main' in self.query.data) and \
                ('back' not in self.query.data):
            return True
        return False

    @property
    def is_cancel_button(self) -> bool:
        text = self.message.text.lower()
        pattern_list = ['отмен', 'cancel']
        return any([pattern in text for pattern in pattern_list])

    def share_button_params(self, text: str, url=None) -> str:
        """
        Кодирует параметры ссылки Поделиться.
        Ссылку задавать в формате: https://t.me/share/url?{params}
        """
        params = {
            'url': url or self.bot_url,
            'text': text
        }
        return urlencode(params, quote_via=quote)



class MessageManager(BaseMessageManager):
    pass
