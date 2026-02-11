import asyncio

from werkzeug.security import generate_password_hash

from core.database.database import async_session_maker, engine
from core.interface.button.repositories import ButtonRepository
from core.interface.menu.repositories import MenuRepository
from core.interface.message.repositories import MessageRepository
from core.interface.settings.repositories import SettingsRepository
from common.models.models import *
from common.models.base import Base
from common.models.interface_models import Button, Menu, Message
from common.models.payments_models import Payment
from common.models.subscriptions_models import Subscription, SubscriptionAccess
from common.models.users_models import User
from modules.users.repositories import AdminRepository


async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        button_repo = ButtonRepository(session)
        menu_repo = MenuRepository(session)

        async def ensure_button(**data) -> Button:
            slug = data["slug"]
            btn = await button_repo.get(slug=slug)
            if btn:
                return btn
            btn_id = await button_repo.add(**data)
            return await button_repo.get(id=btn_id)

        btn_close = await ensure_button(
            slug="btn-close",
            text_ru="Закрыть",
            text_en="Close",
            callback_data="close",
        )
        btn_back = await ensure_button(
            slug="btn-back",
            text_ru="◀️ Назад",
            text_en="◀️ Back",
            callback_data="back_to_main",
        )

        await ensure_button(
            slug="btn-cancel",
            text_ru="Отмена",
            text_en="Cancel",
            type_="reply",
        )

        btn_buy = await ensure_button(
            slug="btn-buy-subscription",
            text_ru="Оформить подписку (30 дней)",
            text_en="Buy subscription (30 days)",
            callback_data="buy_subscription",
        )
        btn_pay_robokassa = await ensure_button(
            slug="btn-pay-robokassa",
            text_ru="💳 Robokassa",
            text_en="💳 Robokassa",
            callback_data="pay_robokassa",
        )
        btn_pay_ton = await ensure_button(
            slug="btn-pay-ton",
            text_ru="💎 TON / 5000 ₸ (CryptoBot)",
            text_en="💎 TON / 5000 ₸ (CryptoBot)",
            callback_data="pay_ton",
        )
        btn_my = await ensure_button(
            slug="btn-my-subscription",
            text_ru="Моя подписка",
            text_en="My subscription",
            callback_data="my_subscription",
        )
        btn_support = await ensure_button(
            slug="btn-support",
            text_ru="Поддержка",
            text_en="Support",
            callback_data="support",
        )
        btn_get_invite = await ensure_button(
            slug="btn-get-invite",
            text_ru="Получить инвайт-ссылку",
            text_en="Get invite link",
            callback_data="get_invite",
        )
        btn_privacy = await ensure_button(
            slug="btn-privacy",
            text_ru="🔒 Политика конфиденциальности",
            text_en="🔒 Privacy Policy",
            callback_data="cmd_privacy",
        )
        btn_offer = await ensure_button(
            slug="btn-offer",
            text_ru="📄 Оферта",
            text_en="📄 Offer",
            callback_data="cmd_offer",
        )

        async def ensure_menu(slug: str, rows: list[list[Button]]) -> Menu:
            menu = await menu_repo.get(slug=slug)
            # markup строится из ID кнопок, разделитель строк: \n, внутри строки: |
            markup_rows = ["|".join(str(btn.id) for btn in row) for row in rows]
            markup = "\n".join(markup_rows)
            buttons = [btn for row in rows for btn in row]

            if not menu:
                menu = Menu(slug=slug, markup=markup)
                menu.buttons_list = buttons
                session.add(menu)
                await session.flush()
                return menu

            menu.markup = markup
            menu.buttons_list = buttons
            await session.flush()
            return menu

        await ensure_menu(
            "menu-start",
            [[btn_buy], [btn_my], [btn_support], [btn_privacy, btn_offer]],
        )
        await ensure_menu("menu-back", [[btn_back]])
        await ensure_menu("menu-support", [[btn_back]])
        # TODO: вернуть btn_pay_ton когда CryptoBot будет готов
        # await ensure_menu("menu-pay-method", [[btn_pay_robokassa], [btn_pay_ton], [btn_back]])
        await ensure_menu("menu-pay-method", [[btn_pay_robokassa], [btn_back]])
        await ensure_menu("menu-my-sub-active", [[btn_get_invite], [btn_back]])
        await ensure_menu("menu-my-sub-inactive", [[btn_back]])
        await ensure_menu("menu-invite", [[btn_close]])

        settings_repo = SettingsRepository(session)
        if not await settings_repo.get(key="TARIFF_AMOUNT_KZT"):
            await settings_repo.add(key="TARIFF_AMOUNT_KZT", value_="5000")
            print("Setting TARIFF_AMOUNT_KZT created")
        if not await settings_repo.get(key="CRYPTOBOT_DESCRIPTION"):
            await settings_repo.add(key="CRYPTOBOT_DESCRIPTION", value_="Подписка на 30 дней")
            print("Setting CRYPTOBOT_DESCRIPTION created")

        message_repo = MessageRepository(session)
        menu_start = await menu_repo.get(slug="menu-start")
        message = await message_repo.get(slug="msg-start")
        if not message:
            msg_id = await message_repo.add(
                slug="msg-start",
                text_ru=(
                    "Привет!\n\n"
                    "Это бот для доступа в закрытый канал по подписке на 30 дней.\n\n"
                    "Выберите действие ниже."
                ),
                text_en="Hello! Choose an action below.",
                menu_id=menu_start.id if menu_start else None,
            )
            message = await message_repo.get(id=msg_id)
        else:
            message.menu_id = menu_start.id if menu_start else None

        if not await message_repo.get(slug="msg-buy-subscription-stub"):
            await message_repo.add(
                slug="msg-buy-subscription-stub",
                text_ru=(
                    "Оплата будет добавлена позже.\n\n"
                    "Пока что подписку можно выдать вручную через администратора."
                ),
                text_en="Payments will be added later.",
            )

        msg_choose_payment = await message_repo.get(slug="msg-choose-payment")
        if not msg_choose_payment:
            await message_repo.add(
                slug="msg-choose-payment",
                text_ru=(
                    "Подписка на 30 дней.\n"
                    "Стоимость: {price} ₸\n\n"
                    "Выберите способ оплаты:"
                ),
                text_en="30-day subscription.\nCost: {price} ₸\n\nChoose a payment method:",
            )
        else:
            msg_choose_payment.text_ru = (
                "Подписка на 30 дней.\n"
                "Стоимость: {price} ₸\n\n"
                "Выберите способ оплаты:"
            )
            msg_choose_payment.text_en = (
                "30-day subscription.\nCost: {price} ₸\n\nChoose a payment method:"
            )

        if not await message_repo.get(slug="msg-support"):
            await message_repo.add(
                slug="msg-support",
                text_ru="Поддержка: напишите администратору или в чат поддержки.",
                text_en="Support: contact the admin.",
            )

        if not await message_repo.get(slug="msg-my-subscription"):
            await message_repo.add(
                slug="msg-my-subscription",
                text_ru="Статус подписки: {status}\nДата окончания: {end_at}",
                text_en="Subscription status: {status}\nEnd date: {end_at}",
            )

        if not await message_repo.get(slug="msg-invite"):
            await message_repo.add(
                slug="msg-invite",
                text_ru=(
                    "Инвайт-ссылка (действует до {expire_at}):\n"
                    "{invite_link}"
                ),
                text_en="Invite link (valid until {expire_at}):\n{invite_link}",
            )

        if not await message_repo.get(slug="msg-no-subscription"):
            await message_repo.add(
                slug="msg-no-subscription",
                text_ru="У вас нет активной подписки.",
                text_en="You don't have an active subscription.",
            )

        if not await message_repo.get(slug="msg-invite-rate-limited"):
            await message_repo.add(
                slug="msg-invite-rate-limited",
                text_ru="Инвайт можно запрашивать не чаще 1 раза в минуту.",
                text_en="Invite link can be requested once per minute.",
            )

        if not await message_repo.get(slug="msg-privacy"):
            await message_repo.add(
                slug="msg-privacy",
                text_ru=(
                    "<b>Политика конфиденциальности</b>\n\n"
                    "Здесь разместите полный текст вашей политики конфиденциальности.\n"
                    "Можно использовать HTML теги, например <b>жирный</b> или "
                    "<a href=\"...\">ссылки</a>."
                ),
                text_en="<b>Privacy Policy</b>\n\nPlace your privacy policy text here.",
            )

        if not await message_repo.get(slug="msg-offer"):
            await message_repo.add(
                slug="msg-offer",
                text_ru=(
                    "<b>Публичная оферта</b>\n\n"
                    "Здесь разместите текст оферты.\n"
                    "Текст может быть длинным, Telegram поддерживает до 4096 символов."
                ),
                text_en="<b>Public Offer</b>\n\nPlace your offer text here.",
            )

        # добавляем админа
        password = 'admin'
        password = generate_password_hash(password, method='pbkdf2:sha256')

        admin_repo = AdminRepository(session)
        admin = await admin_repo.get(username='admin')
        if not admin:
            await admin_repo.add(username='admin',
                                password=password)

        await session.commit()


asyncio.run(create_db())
