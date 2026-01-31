import datetime as dt

from telegram import Update
from telegram.ext import ContextTypes

from core.constants.config import CHANNEL_ID
from core.message_manager import MessageManager


async def _kick_user(bot, channel_id: int, user_id: int) -> None:
    """
    Telegram не имеет отдельной операции 'kick' для всех типов чатов.
    Для чатов/групп обычно делают ban -> unban.
    """
    await bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
    await bot.unban_chat_member(chat_id=channel_id, user_id=user_id)


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        subs = await mm.uow.subscription_repo.list_active(channel_id=CHANNEL_ID, limit=50)
        if not subs:
            await update.message.reply_text("Активных подписчиков нет.")
            return

        lines: list[str] = ["Активные подписчики (до 50):"]
        for sub in subs:
            user = await mm.uow.user_repo.get(user_id=sub.user_id)
            username = f"@{user.username}" if user and user.username else ""
            end_at = sub.end_at.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"- {sub.user_id} {username} до {end_at}")

        await update.message.reply_text("\n".join(lines))


async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        if not context.args:
            await update.message.reply_text("Использование: /add <user_id>")
            return
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("user_id должен быть числом.")
            return

        sub_id = await mm.subscription_service.grant_90d(user_id=target_id, channel_id=CHANNEL_ID)
        await mm.uow.commit()

        invite_link = None
        try:
            invite_link, expire_at, _ = await mm.subscription_service.create_invite_link(
                bot=mm.bot,
                user_id=target_id,
                channel_id=CHANNEL_ID,
            )
            await mm.bot.send_message(
                chat_id=target_id,
                text=(
                    "Вам выдана подписка на канал.\n\n"
                    f"Инвайт-ссылка (действует до {expire_at.strftime('%Y-%m-%d %H:%M UTC')}):\n"
                    f"{invite_link}"
                ),
            )
        except Exception:
            # Пользователь мог не начинать чат с ботом или бот не имеет прав.
            pass

        text = f"Ок. Подписка выдана. subscription_id={sub_id}"
        if invite_link:
            text += f"\nИнвайт (можно переслать): {invite_link}"
        await update.message.reply_text(text)


async def admin_extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        if len(context.args) < 2:
            await update.message.reply_text("Использование: /extend <user_id> <days>")
            return
        try:
            target_id = int(context.args[0])
            days = int(context.args[1])
        except ValueError:
            await update.message.reply_text("user_id и days должны быть числами.")
            return

        sub_id = await mm.subscription_service.extend(
            user_id=target_id, days=days, channel_id=CHANNEL_ID
        )
        await mm.uow.commit()
        await update.message.reply_text(f"Ок. Подписка продлена. subscription_id={sub_id}")


async def admin_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        if not context.args:
            await update.message.reply_text("Использование: /remove <user_id>")
            return
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("user_id должен быть числом.")
            return

        await mm.subscription_service.revoke(
            user_id=target_id, channel_id=CHANNEL_ID, reason="revoked_by_admin"
        )
        await mm.uow.commit()

        if CHANNEL_ID:
            try:
                await _kick_user(mm.bot, CHANNEL_ID, target_id)
            except Exception:
                pass

        await update.message.reply_text("Ок. Подписка отозвана, пользователь удалён из канала (если был).")


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with MessageManager(update, context) as mm:
        stats = await mm.uow.subscription_repo.count_by_status(channel_id=CHANNEL_ID)
        if not stats:
            await update.message.reply_text("Статистики пока нет.")
            return

        lines = ["Статистика подписок:"]
        for status, cnt in sorted(stats.items()):
            lines.append(f"- {status}: {cnt}")
        await update.message.reply_text("\n".join(lines))

