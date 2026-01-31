import datetime as dt

from telegram import Update
from telegram.ext import ContextTypes

from core.interface.services import BotInterfaceService
from core.constants.config import CHANNEL_ID
from core.message_manager import MessageManager


async def _menu(mm: MessageManager, slug: str):
    bi = BotInterfaceService(mm.uow)
    lang = await mm.get_lang()
    menu = await mm.uow.menu_repo.get(slug=slug)
    return await bi.get_keyboard(menu=menu, lang=lang)


async def buy_subscription_stub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        await mm.edit_message_text(
            "msg-buy-subscription-stub",
            msg_id=mm.message.message_id,
            reply_markup=await _menu(mm, "menu-start"),
        )


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        await mm.edit_message_text(
            "msg-support",
            msg_id=mm.message.message_id,
            reply_markup=await _menu(mm, "menu-support"),
        )


async def my_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        sub = await mm.subscription_service.get_active(
            user_id=mm.user_id, channel_id=CHANNEL_ID
        )
        if sub:
            end_at = sub.end_at.astimezone(dt.timezone.utc)
            await mm.edit_message_text(
                "msg-my-subscription",
                msg_id=mm.message.message_id,
                status="Активна",
                end_at=end_at.strftime("%Y-%m-%d %H:%M UTC"),
                reply_markup=await _menu(mm, "menu-my-sub-active"),
            )
            return

        await mm.edit_message_text(
            "msg-my-subscription",
            msg_id=mm.message.message_id,
            status="Не активна",
            end_at="—",
            reply_markup=await _menu(mm, "menu-my-sub-inactive"),
        )


async def get_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        try:
            invite_link, expire_at, _ = await mm.subscription_service.create_invite_link(
                bot=mm.bot,
                user_id=mm.user_id,
                channel_id=CHANNEL_ID,
            )
        except ValueError as exc:
            if str(exc) == "no_active_subscription":
                await mm.answer("msg-no-subscription", show_alert=True)
                return
            if str(exc) == "invite_rate_limited":
                await mm.answer("msg-invite-rate-limited", show_alert=True)
                return
            raise

        await mm.edit_message_text(
            "msg-invite",
            msg_id=mm.message.message_id,
            invite_link=invite_link,
            expire_at=expire_at.strftime("%Y-%m-%d %H:%M UTC"),
            reply_markup=await _menu(mm, "menu-invite"),
        )

