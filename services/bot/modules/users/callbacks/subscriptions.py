import datetime as dt
import os

from telegram import Update
from telegram.ext import ContextTypes
import httpx

from core.interface.services import BotInterfaceService
from core.constants.config import CHANNEL_ID
from core.message_manager import MessageManager


async def _menu(mm: MessageManager, slug: str):
    bi = BotInterfaceService(mm.uow)
    lang = await mm.get_lang()
    menu = await mm.uow.menu_repo.get(slug=slug)
    return await bi.get_keyboard(menu=menu, lang=lang)


async def _require_internal_api(mm: MessageManager) -> tuple[str, str]:
    web_base_url = (os.getenv("WEB_BASE_URL") or "http://web:5000").rstrip("/")
    internal_token = os.getenv("INTERNAL_API_TOKEN") or ""
    if not internal_token:
        raise RuntimeError("INTERNAL_API_TOKEN is not set")
    return web_base_url, internal_token


async def buy_subscription_stub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        price = await mm.config("TARIFF_AMOUNT_KZT")
        if price is None:
            price = "5000"
        else:
            price = str(price)
        await mm.edit_message_text(
            "msg-choose-payment",
            msg_id=mm.message.message_id,
            reply_markup=await _menu(mm, "menu-pay-method"),
            price=price,
        )
        return


async def pay_robokassa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        try:
            web_base_url, internal_token = await _require_internal_api(mm)
        except RuntimeError:
            await mm.bot.edit_message_text(
                chat_id=mm.chat_id,
                message_id=mm.message.message_id,
                text="Оплата пока не настроена (INTERNAL_API_TOKEN не задан).",
                reply_markup=await _menu(mm, "menu-start"),
            )
            return

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{web_base_url}/payments/robokassa/create",
                    json={"user_id": mm.user_id},
                    headers={"X-Internal-Token": internal_token},
                )
                data = resp.json()
        except Exception as exc:
            await mm.bot.edit_message_text(
                chat_id=mm.chat_id,
                message_id=mm.message.message_id,
                text=f"Не удалось создать платёж. Попробуйте позже.\n\nОшибка: {exc}",
                reply_markup=await _menu(mm, "menu-start"),
            )
            return

        if resp.status_code != 200:
            err = data.get("error") if isinstance(data, dict) else str(data)
            await mm.bot.edit_message_text(
                chat_id=mm.chat_id,
                message_id=mm.message.message_id,
                text=f"Не удалось создать платёж. Код {resp.status_code}.\n{err}",
                reply_markup=await _menu(mm, "menu-start"),
            )
            return

        payment_url = data.get("payment_url")
        inv_id = data.get("inv_id")
        if not payment_url:
            await mm.bot.edit_message_text(
                chat_id=mm.chat_id,
                message_id=mm.message.message_id,
                text="Не удалось получить ссылку оплаты. Попробуйте позже.",
                reply_markup=await _menu(mm, "menu-start"),
            )
            return

        description = await mm.config("CRYPTOBOT_DESCRIPTION") or "Подписка на 90 дней"
        price = await mm.config("TARIFF_AMOUNT_KZT")
        price_str = str(price) if price is not None else "5000"
        await mm.bot.edit_message_text(
            chat_id=mm.chat_id,
            message_id=mm.message.message_id,
            text=(
                f"Ссылка для оплаты {description} ({price_str} ₸):\n\n"
                f"{payment_url}\n\n"
                f"Номер счёта: {inv_id}\n\n"
                "После оплаты бот пришлёт инвайт-ссылку автоматически."
            ),
            disable_web_page_preview=True,
            reply_markup=await _menu(mm, "menu-start"),
        )


async def pay_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        try:
            web_base_url, internal_token = await _require_internal_api(mm)
        except RuntimeError:
            await mm.bot.edit_message_text(
                chat_id=mm.chat_id,
                message_id=mm.message.message_id,
                text="Оплата пока не настроена (INTERNAL_API_TOKEN не задан).",
                reply_markup=await _menu(mm, "menu-start"),
            )
            return

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{web_base_url}/payments/cryptobot/create",
                    json={"user_id": mm.user_id},
                    headers={"X-Internal-Token": internal_token},
                )
                data = resp.json()
        except Exception as exc:
            await mm.bot.edit_message_text(
                chat_id=mm.chat_id,
                message_id=mm.message.message_id,
                text=f"Не удалось создать счёт на оплату. Попробуйте позже.\n\nОшибка: {exc}",
                reply_markup=await _menu(mm, "menu-start"),
            )
            return

        if resp.status_code != 200:
            err = data.get("error") if isinstance(data, dict) else str(data)
            await mm.bot.edit_message_text(
                chat_id=mm.chat_id,
                message_id=mm.message.message_id,
                text=f"Не удалось создать счёт на оплату. Код {resp.status_code}.\n{err}",
                reply_markup=await _menu(mm, "menu-start"),
            )
            return

        pay_url = data.get("pay_url")
        invoice_id = data.get("invoice_id")
        if not pay_url:
            await mm.bot.edit_message_text(
                chat_id=mm.chat_id,
                message_id=mm.message.message_id,
                text="Не удалось получить ссылку оплаты. Попробуйте позже.",
                reply_markup=await _menu(mm, "menu-start"),
            )
            return

        description = await mm.config("CRYPTOBOT_DESCRIPTION") or "Подписка на 90 дней"
        price = await mm.config("TARIFF_AMOUNT_KZT")
        price_str = str(price) if price is not None else "5000"
        await mm.bot.edit_message_text(
            chat_id=mm.chat_id,
            message_id=mm.message.message_id,
            text=(
                f"Оплата {price_str} ₸ в TON (CryptoBot).\n\n"
                f"Ссылка для оплаты {description}:\n\n"
                f"{pay_url}\n\n"
                f"Номер счёта: {invoice_id}\n\n"
                "После оплаты бот пришлёт инвайт-ссылку автоматически."
            ),
            disable_web_page_preview=True,
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

