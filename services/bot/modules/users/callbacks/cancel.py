from telegram import Update
from telegram.ext import ContextTypes

from core.constants.enums import Mode
from core.message_manager import MessageManager


# from user.callbacks.callbacks import show_inspector_cabinet
# from user.callbacks.moderation import back_to_main_moderation


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as manager:
        if manager.mode == Mode.INSPECTOR:
            # return await show_inspector_cabinet(update, context)
            pass
        elif manager.mode == Mode.MODERATOR:
            # return await back_to_main_moderation(update, context)
            pass
