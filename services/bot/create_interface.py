import asyncio
from typing import Iterable, Optional

from core.database.database import async_session_maker
from core.interface.button.repositories import ButtonRepository
from core.interface.menu.repositories import MenuRepository
from core.interface.message.repositories import MessageRepository
from common.models.interface_models import Button, Menu, Message


async def upsert_button(
    repo: ButtonRepository,
    slug: str,
    *,
    text_ru: str,
    text_en: Optional[str] = None,
    type_: str = "inline",
    callback_data: Optional[str] = None,
    inline_url: Optional[str] = None,
    request_contact: bool = False,
    request_location: bool = False,
) -> Button:
    button = await repo.get(slug=slug)
    if button:
        button.text_ru = text_ru
        button.text_en = text_en
        button.type_ = type_
        button.callback_data = callback_data
        button.inline_url = inline_url
        button.request_contact = request_contact
        button.request_location = request_location
        return button

    button_id = await repo.add(
        slug=slug,
        text_ru=text_ru,
        text_en=text_en,
        type_=type_,
        callback_data=callback_data,
        inline_url=inline_url,
        request_contact=request_contact,
        request_location=request_location,
    )
    button = await repo.get(id=button_id)
    assert button is not None
    return button


async def upsert_menu(
    repo: MenuRepository,
    slug: str,
    *,
    markup: str,
    is_persistent: bool = False,
    buttons: Iterable[Button],
) -> Menu:
    menu = await repo.get(slug=slug)
    if menu:
        menu.markup = markup
        menu.is_persistent = is_persistent
        # Обновляем набор кнопок меню
        menu.buttons_list = list(buttons)
        return menu

    menu_id = await repo.add(
        slug=slug,
        markup=markup,
        is_persistent=is_persistent,
    )
    menu = await repo.get(id=menu_id)
    assert menu is not None
    menu.buttons_list = list(buttons)
    return menu


async def upsert_message(
    repo: MessageRepository,
    slug: str,
    *,
    text_ru: str,
    text_en: Optional[str] = None,
    menu: Optional[Menu] = None,
) -> Message:
    message = await repo.get(slug=slug)
    menu_id = menu.id if menu else None

    if message:
        message.text_ru = text_ru
        message.text_en = text_en
        message.menu_id = menu_id
        return message

    message_id = await repo.add(
        slug=slug,
        text_ru=text_ru,
        text_en=text_en,
        menu_id=menu_id,
    )
    message = await repo.get(id=message_id)
    assert message is not None
    return message


async def create_or_update_interface():
    """
    Скрипт создаёт или обновляет сообщения, кнопки и меню
    для сценария регистрации инвестора (MenaCore).

    Повторный запуск безопасен: сущности обновляются по slug.
    """
    async with async_session_maker() as session:
        button_repo = ButtonRepository(session)
        menu_repo = MenuRepository(session)
        message_repo = MessageRepository(session)


        # Здесь добавляем создание или обновление кнопок, меню и сообщений

        await session.commit()


if __name__ == "__main__":
    asyncio.run(create_or_update_interface())


