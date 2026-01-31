import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot, Message, Update
from telegram.ext import ContextTypes

from core.constants.cases import Cases
from core.constants.config import DEV_MODE
from core.database.database import async_session_maker
from core.database.uow import UoW
from core.interface.message.repositories import MessageRepository
from core.interface.menu.kb import Keyboard
from common.models.users_models import User
from .base_manager import BaseMessageManager
from modules.users.services import UserService
from modules.subscriptions.services import SubscriptionService


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.INFO
    )


class MessageManager(BaseMessageManager):

    def __init__(self, update: Update = None,
                 context: ContextTypes.DEFAULT_TYPE = None,
                 bot: Bot = None,
                 chat_id: int = None,
                 user_id: int = None,
                 session: AsyncSession = None):
        super().__init__(update, context, bot, chat_id, user_id, session)
        self._session = session
        self.cases = Cases()
        self.user_service = None  # задаём нужные сервисы
        self.subscription_service = None
        self.kb = None

    async def __aenter__(self):
        # Логика, которая будет выполняться при открытии контекста
        self.session = async_session_maker()
        self.uow = UoW(self.session)

        # чтобы был доступен из контекстного менеджера
        self.user_service = UserService(self.uow)
        self.subscription_service = SubscriptionService(self.uow)
        self.kb = Keyboard(self.uow)
        return self

    async def send_message(self, slug=None,
                           disable_web_page_preview=False,
                           message=None,
                           **kwargs) -> Message:
        """
        Отправляет текстовое сообщение или фото с текстом
        в качестве подписи, в зависимости от того,
        добавлено ли изображение в админке
        """
        if not message:
            message = await self.uow.message_repo.get(slug=slug)

        if message.image_path:
            msg = await self.send_photo(slug=slug, message=message, **kwargs)
            self.save_message_id(msg.message_id)
            return msg
        elif message.video_note_path:
            msg = await self.send_video_note(slug=slug, message=message, **kwargs)
            self.save_message_id(msg.message_id)
            return msg
        elif message.voice_path:
            msg = await self.send_voice(slug=slug, message=message, **kwargs)
            self.save_message_id(msg.message_id)
            return msg
        elif message.video_path:
            msg = await self.send_video(slug=slug, **kwargs)
            self.save_message_id(msg.message_id)
            return msg
        elif message.animation_path:
            msg = await self.send_animation(slug=slug, **kwargs)
            self.save_message_id(msg.message_id)
            return msg

        text = await self.get_text(message, **kwargs)
        reply_markup = await self.get_markup(message, **kwargs)

        msg = await self.bot.send_message(
            chat_id=kwargs['chat_id'] if 'chat_id' in kwargs else  self.chat_id,
            text=text,
            disable_web_page_preview=disable_web_page_preview,
            reply_markup=reply_markup,
            parse_mode=self.parse_mode
            )
        self.save_message_id(msg.message_id)

        return msg

    async def get_user(self, user_id: int) -> User:
        return await self.user_service.get_user(user_id)

    async def config(self, key: str):
        dev_mode_list = ['ADMIN_USERNAME']  # сюда добавляем ключи, которые отличаются локально и на сервере
        if key in dev_mode_list and DEV_MODE:
            key = 'DEV_' + key
        return await super().config(key)

    async def download_file(self, file_id: str, dir_path: str = None):
        if not dir_path:
            dir_path = self.STATIC_FILES

        file = await self.bot.get_file(file_id)
        filename = os.path.basename(file.file_path)
        path = await file.download_to_drive(os.path.join(dir_path, filename))
        return path
