import datetime as dt
import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.message_manager import MessageManager


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.INFO
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        text = mm.message.text if mm.message else None
        source = mm.user_service.get_source(text)

        user = await mm.get_user(mm.user_id)
        if not user:
            user = await mm.user_service.add_user(
                user_id=mm.user_id,
                first_name=mm.first_name,
                username=mm.username,
                source=source
            )
            await mm.session.commit()

        await mm.send_message('msg-start')
        return mm.end_conversation


async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post:
        channel_id = update.channel_post.chat.id
        await update.channel_post.reply_text(f'ID канала: {channel_id}')
        logging.info(f'ID канала: {channel_id}')

    elif update.message:
        user_id = update.message.from_user.id
        await update.message.reply_text(f'Ваш user_id: {str(user_id)}')
        logging.info(f'User_id клиента: {str(user_id)}')

        chat_id = update.message.chat.id
        await update.message.reply_text(f'Chat_id: {chat_id}')
        logging.info(f'Chat_id: {chat_id}')


async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Удаляет сообщение по нажатии на кнопку Закрыть
    """
    async with MessageManager(update, context) as mm:
        for message_id in mm.message_id_list:
            await mm.delete_message(message_id)
        await mm.delete_message(mm.message.message_id)
