from typing import List

from telegram.ext import (
    CallbackQueryHandler as _CallbackQueryHandler,
    ChatJoinRequestHandler as _ChatJoinRequestHandler,
    ChatMemberHandler as _ChatMemberHandler,
    CommandHandler as _CommandHandler,
    ConversationHandler as _ConversationHandler,
    MessageHandler as _MessageHandler
)

from core.interface.button.repositories import Button, ButtonRepository
import core.interface.menu.kb as kb


class CommandHandler(_CommandHandler):
    def __init__(self, *args, group=0, order=5, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.group = group
        self.order = order
        self.block = False


class CallbackQueryHandler(_CallbackQueryHandler):
    def __init__(self, *args, group=0, order=5, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.group = group
        self.order = order
        self.block = False


class MessageHandler(_MessageHandler):
    def __init__(self, *args, group=0, order=5, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.group = group
        self.order = order
        self.block = False


class ChatMemberHandler(_ChatMemberHandler):
    def __init__(self, *args, group=0, order=5, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.group = group
        self.order = order


class ChatJoinRequestHandler(_ChatJoinRequestHandler):
    def __init__(self, *args, group=0, order=5, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.group = group
        self.order = order


class ConversationHandler(_ConversationHandler):
    def __init__(self, *args, group=0, order=5, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.group = group
        self.order = order
        self.block = False


class BaseHandler:
    def __init__(self, session) -> None:
        self.session = session

    async def button(self, slug):
        return await ButtonRepository(self.session).get(slug=slug)

    async def pattern(self, slug, **kwargs):
        button = await self.button(slug=slug)
        return button.pattern(**kwargs)

    async def buttons_list(self, slug_list) -> List[Button]:
        return await ButtonRepository(self.session).get_buttons(slug_list)

    async def buttons_pattern(self, slug_list: List[str]):
        """Формирует паттерн из нескольких reply-кнопок"""
        buttons_list = await self.buttons_list(slug_list)
        text_list = [
            f'{button.text_ru}|{button.text_en}' if button.text_en is not None else button.text_ru
            for button in buttons_list
        ]
        return f"^({'|'.join(text_list)})$"


class BaseMainHandler(BaseHandler):
    def __init__(self, session) -> None:
        super().__init__(session)
        self._module_handlers_list = []

    def add_module_handler(self, handler: BaseHandler):
        self._module_handlers_list.append(handler)

    async def setup_handlers(self):
        close_conv_buttons = await self.close_conv_buttons()

        for Handler in self._module_handlers_list:
            async for handler in Handler(self.session, close_conv_buttons).handle():
                yield handler

    async def close_conv_buttons(self):
        pass

    async def handlers(self):
        pass

    def menu_pattern(self, Menu: kb.BaseMenu, *args):
        """Паттерн на кнопки меню"""
        menu = Menu(self.session)
        return menu.pattern(*args)

    def nav_menu_pattern(self, Menu: kb.BaseMenu):
        """Паттерн на навигационные кнопки"""
        menu = Menu(self.session)
        return menu.nav_pattern()

    async def handle(self):
        async for handler in self.handlers():
            yield handler

        async for handler in self.setup_handlers():
            yield handler
