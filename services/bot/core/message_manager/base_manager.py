import logging
import os
from pathlib import Path
import traceback
from typing import cast, List, Literal, Tuple, TypedDict, Union

from sqlalchemy.ext.asyncio import AsyncSession
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
from core.database.database import async_session_maker
from core.database.uow import UoW
from core.constants.enums import MEDIA_GROUP_TYPES, Mode
from core.interface.menu.repositories import MenuRepository
from core.interface.message.repositories import MessageRepository
from core.interface.services import BotInterfaceService
from modules.users.repositories import UserRepository


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
                 session: AsyncSession = None):
        self.update = update
        self.context = context
        self._chat_id = chat_id  # когда явно указали
        self._user_id = user_id
        self._bot = bot
        self.query = update.callback_query if self.update else None
        self.parse_mode = ParseMode.HTML
        self.uow = None
        self.kb = None
        self.STATIC_IMAGES = Path(STATIC_FOLDER, 'img')
        self.STATIC_FILES = Path(STATIC_FOLDER, 'files')

    async def __aenter__(self):
            self.session = async_session_maker()
            self.uow = UoW(self.session)
            return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                await self.uow.commit()  # Фиксируем изменения, если ошибок нет
            else:
                await self.uow.rollback()  # Откатываем при ошибке
            await self.session.close()

            if self.context and DEV_MODE:
                print(self.user_id, self.context.user_data, '\n')

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
    def message_id_list(self) -> List[int]:
        if self.context and self.context.user_data:
            return self.context.user_data.get('msg_id_list')
        return []

    def append_message_id(self, value):
        if not (self.context is not None and self.context.user_data is not None):
            raise ValueError('Нельзя присвоить значение: не найден user_id')
        if not isinstance(value, int):
            raise ValueError(f'Должно быть число, передано: {value}')

        if self.context.user_data.get('msg_id_list'):
            self.context.user_data['msg_id_list'].append(value)
        else:
            self.context.user_data['msg_id_list'] = [value]

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

    async def get_message(self, slug: str):
        return await BotInterfaceService(self.session).get_message(slug)

    async def get_button(self, slug: str):
        return await BotInterfaceService(self.session).get_button(slug)

    async def get_button_by_text(self, text: str):
        return (
            await BotInterfaceService(self.session)
            .get_button_by_text(text)
        )

    async def config(self, key: str):
        dev_mode_list = []
        if key in dev_mode_list and DEV_MODE:
            key = 'DEV_' + key  # когда разные данные на сервере и локально, например, CHANNEL_ID
        return (
            await BotInterfaceService(self.session)
            .get_settings(key)
        )

    async def get_markup(self, message=None,
                   **kwargs) -> InlineKeyboardMarkup | ReplyKeyboardMarkup | None:
        if 'reply_markup' in kwargs:
            return kwargs['reply_markup']

        if not message.menu_id:
            return None

        lang = await self.get_lang()
        keyboard = (
            await BotInterfaceService(self.session)
            .get_keyboard(menu=message.menu, lang=lang, **kwargs)
        )

        return keyboard

    async def get_text(self, message, **kwargs) -> str:
        if 'text' in kwargs:
            return kwargs['text']

        lang = await self.get_lang()
        text = getattr(message, f'text_{lang}')
        return text.format(**kwargs)

    async def get_caption(self, message, **kwargs) -> str:
        if 'caption' in kwargs:
            return kwargs['caption']

        lang = await self.get_lang()
        text = getattr(message, f'text_{lang}')
        return text.format(**kwargs)

    def get_animation(self, message, **kwargs):
        if 'animation' in kwargs:
            return kwargs['animation']
        animation_path = os.path.join(STATIC_FOLDER, message.animation_path)
        if DEV_MODE:
            return open(animation_path, 'rb')
        return message.animation_id or open(animation_path, 'rb')

    def get_video_note(self, message, **kwargs):
        if 'video_note' in kwargs:
            return kwargs['video_note']
        video_note_path = os.path.join(STATIC_FOLDER, message.video_note_path)
        if DEV_MODE:
            return open(video_note_path, 'rb')
        return message.video_note_id or open(video_note_path, 'rb')

    def get_video(self, message, **kwargs):
        if 'video' in kwargs:
            return kwargs['video']
        video_path = os.path.join(STATIC_FOLDER, message.video_path)
        if DEV_MODE:
            return open(video_path, 'rb')
        return message.video_id or open(video_path, 'rb')

    def get_voice(self, message, **kwargs):
        if 'voice' in kwargs:
            return kwargs['voice']
        voice_path = os.path.join(STATIC_FOLDER, message.voice_path)
        if DEV_MODE:
            return open(voice_path, 'rb')
        return message.voice_id or open(voice_path, 'rb')

    def get_photo(self, message, **kwargs):
        if 'photo' in kwargs:
            return kwargs['photo']
        image_path = os.path.join(STATIC_FOLDER, message.image_path)
        if DEV_MODE:
            return open(image_path, 'rb')
        return message.image_id or open(image_path, 'rb')

    def get_document(self, message, **kwargs):
        if 'document' in kwargs:
            return kwargs['document']
        document_path = os.path.join(STATIC_FOLDER, message.document_path)
        if DEV_MODE:
            return open(document_path, 'rb')
        return message.document_id or open(document_path, 'rb')

    def get_message_id(self, **kwargs) -> int:
        if 'msg_id' in kwargs:
            return kwargs['msg_id']
        return self.message_id

    async def get_lang(self):
        if self.context and 'lang' in self.context.user_data:
            return self.context.user_data['lang']

        user = await self.uow.user_repo.get(user_id=self.user_id)
        if not user:
            return 'ru'

        if self.context:
            self.context.user_data['lang'] = user.lang
        return user.lang

    async def get_text_and_markup(self, slug, **kwargs) \
            -> Tuple[str, Union[InlineKeyboardMarkup, ReplyKeyboardMarkup]]:
        message = await self.uow.message_repo.get(slug=slug)
        text = await self.get_text(message, **kwargs)
        markup = await self.get_markup(message, **kwargs)
        return text, markup

    async def send_message(self, slug=None,
                           disable_web_page_preview=False,
                           **kwargs) -> Message:

        text, reply_markup = await self.get_text_and_markup(slug, **kwargs)

        msg = await self.bot.send_message(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else  self.chat_id,
            text=text,
            disable_web_page_preview=disable_web_page_preview,
            reply_markup=reply_markup,
            parse_mode=self.parse_mode
            )

        return msg

    async def send_photo(self, slug=None, message=None, **kwargs) -> Message:
        if not message:
            message = await self.uow.message_repo.get(slug=slug)

        msg = await self.bot.send_photo(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else  self.chat_id,
            photo=self.get_photo(message, **kwargs),
            caption=await self.get_caption(message, **kwargs),
            reply_markup=await self.get_markup(message, **kwargs),
            parse_mode=self.parse_mode
            )

        if not message.image_id:
            message.image_id = msg.photo[-1].file_id
            await self.session.commit()

        return msg

    async def send_animation(self, slug=None, message=None, **kwargs) -> Message:
        if not message:
            message = await self.uow.message_repo.get(slug=slug)

        msg = await self.bot.send_animation(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else  self.chat_id,
            animation=self.get_animation(message, **kwargs),
            caption=await self.get_caption(message, **kwargs),
            reply_markup=await self.get_markup(message, **kwargs),
            parse_mode=self.parse_mode
            )

        if not message.animation_id:
            message.animation_id = msg.animation.file_id
            await self.session.commit()

        return msg

    async def send_video(self, slug=None, message=None, **kwargs) -> Message:
        if not message:
            message = await self.uow.message_repo.get(slug=slug)

        msg = await self.bot.send_video(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else  self.chat_id,
            video=self.get_video(message, **kwargs),
            caption=await self.get_caption(message, **kwargs),
            reply_markup=await self.get_markup(message, **kwargs),
            parse_mode=self.parse_mode
            )

        if not message.video_id:
            message.video_id = msg.video.file_id
            await self.session.commit()

        return msg

    async def send_video_note(self, slug=None, message=None, **kwargs) -> Message:
        if not message:
            message = await self.uow.message_repo.get(slug=slug)

        msg = await self.bot.send_video_note(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else self.chat_id,
            video_note=self.get_video_note(message, **kwargs),
            reply_markup=await self.get_markup(message, **kwargs)
            )

        if not message.video_note_id:
            message.video_note_id = msg.video_note.file_id
            await self.session.commit()

        return msg

    async def send_voice(self, slug=None, message=None, **kwargs) -> Message:
        if not message:
            message = await self.uow.message_repo.get(slug=slug)

        msg = await self.bot.send_voice(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else self.chat_id,
            voice=self.get_voice(message, **kwargs),
            caption=await self.get_caption(message, **kwargs),
            reply_markup=await self.get_markup(message, **kwargs),
            parse_mode=self.parse_mode
            )

        if not message.voice_id:
            message.voice_id = msg.voice.file_id
            await self.session.commit()

        return msg

    async def send_document(self, slug=None, message=None, **kwargs) -> Message:
        if not message:
            message = await self.uow.message_repo.get(slug=slug)

        msg = await self.bot.send_document(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else self.chat_id,
            document=self.get_document(message, **kwargs),
            caption=await self.get_caption(message, **kwargs),
            reply_markup=await self.get_markup(message, **kwargs),
            parse_mode=self.parse_mode
            )
        return msg

    async def get_media(self, message, **kwargs):
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
        message = await self.uow.message_repo.get(slug=slug)

        msg_list = await self.bot.send_media_group(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else self.chat_id,
            media=await self.get_media(message, **kwargs),
            caption=await self.get_caption(message, **kwargs),
            parse_mode=self.parse_mode
            )
        return msg_list

    async def edit_message_text(self, slug=None,
                                disable_web_page_preview=False,
                                **kwargs) -> Message:

        text, reply_markup = await self.get_text_and_markup(slug, **kwargs)

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

    async def edit_message_caption(self, slug=None, **kwargs) -> Message:

        text, reply_markup = await self.get_text_and_markup(slug, **kwargs)

        try:
            await self.bot.edit_message_caption(
                chat_id=self.chat_id,
                message_id=self.get_message_id(**kwargs),
                caption=text,
                reply_markup=reply_markup,
                parse_mode=self.parse_mode,
            )
        except Exception:
            logging.info(f'Error: {str(traceback.format_exc())}')

    async def edit_message_reply_markup(self, **kwargs) -> Message:

        reply_markup = await self.get_markup(**kwargs)

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

    async def answer(self, slug: str, show_alert=False, **kwargs) -> bool:
        text, _ = await self.get_text_and_markup(slug, **kwargs)
        await self.query.answer(text, show_alert=show_alert)

    def save_message_id(self, message_id: int):
        if self.context:
            self.context.user_data['msg_id'] = message_id

    def add_to_context(self, key, value):
        if self.context:
            self.context.user_data[key] = value

    def get_from_context(self, key):
        if self.context:
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

    async def delete_previous_message(self):
        if self.message_id:
            await self.delete_message(self.message_id)

        if self.message_id_list:
            for message_id in self.message_id_list:
                await self.delete_message(message_id)

            self.context.user_data['msg_id_list'] = []

    def clear_context(self, except_keys: list[str] | str = None):
        """Очищает временные переменные из контекста"""
        exc_keys = ['msg_id', 'screen_names_list', 'lang']
        if except_keys:
            if isinstance(except_keys, str):
                exc_keys.append(except_keys)
            else:
                exc_keys.extend(except_keys)

        for key in list(self.context.user_data):
            if key in exc_keys:
                continue
            del self.context.user_data[key]

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

    async def delete_reply_keyboard(self):
        """
        Удаляет репли меню (полезно, когда надо
        заменить репли меню на инлайн)
        """
        msg = await self.message.reply_text(
            '.', reply_markup=ReplyKeyboardRemove()
        )
        await self.delete_message(msg.message_id)

    async def delete_inline_keyboard(self):
        """Удяляет инлайн кнопки в сообщении"""
        await self.edit_message_reply_markup(
            msg_id=self.message.message_id,
            reply_markup=InlineKeyboardMarkup([[]])
        )

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

    async def media_group_handler(self, context: ContextTypes.DEFAULT_TYPE):
        """
        В клиентском коде переопределяем этот метод, используем
        media = await super().media_group_handler(context)
        """
        context.job.data = cast(List[MsgDict], context.job.data)
        media = []
        for msg_dict in context.job.data:
            InputMediaObj = MEDIA_GROUP_TYPES[msg_dict["media_type"]]
            media.append(
                InputMediaObj(media=msg_dict["media_id"],
                              caption=msg_dict["caption"])
            )
        return media

    def handle_media(self, message: Message):
        """
        Обрабатывает случай, когда прислали
        сообщение в формате media_group
        """
        media_type = effective_message_type(message)
        media_id = (
            message.photo[-1].file_id if message.photo else
            message.effective_attachment.file_id
        )
        msg_dict = {"media_type": media_type,
                    "media_id": media_id,
                    "caption": message.caption_html,
                    "post_id": message.message_id}

        jobs = self.context.job_queue.get_jobs_by_name(
            str(message.media_group_id))
        if jobs:
            # job уже создали и запланировали
            # через 2 сек, просто добавляем данные
            jobs[0].data.append(msg_dict)
        else:
            # создаём job, которая отработает через 2 сек.
            # До этого времени добавляем к её данным
            # информацию о сообщениях
            self.context.job_queue.run_once(
                callback=self.media_group_handler,
                when=2, data=[msg_dict],
                name=str(message.media_group_id)
            )
        return

    @property
    def mode(self):
        mode = self.context.user_data.get('mode')
        if not mode:
            raise ValueError('Не найдена переменная mode в контексте')
        return mode

    @mode.setter
    def mode(self, value: Mode):
        if not isinstance(value, Mode):
            raise ValueError('Переменная mode должна быть объектом класса Mode')
        self.context.user_data['mode'] = value



class MessageManager(BaseMessageManager):
    pass
