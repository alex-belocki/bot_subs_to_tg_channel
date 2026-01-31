import re
from typing import List

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)

from core.constants.config import DEV_MODE_KB
from core.interface.button.repositories import ButtonRepository, Button
from core.interface.menu.repositories import MenuRepository, Menu
from core.interface.services import BotInterfaceService
from common.models.models import Tariff


class BaseKeyboard:
    """
    Класс Keyboards предназначен для создания и разметки интерфейса бота
    """
    # инициализация разметки

    def __init__(self, session=None):
        self.session = session
        self.button_repo = ButtonRepository(session)
        self.menu_repo = MenuRepository(session)
        self.bi_service = BotInterfaceService(self.session)

    @staticmethod
    def build_menu(buttons,
                   n_cols,
                   header_buttons: List = None,
                   footer_buttons: List = None):
        menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
        if header_buttons:
            menu.insert(0, header_buttons)

        if footer_buttons:
            if len(footer_buttons) == 1:
                menu.append(footer_buttons)
            else: menu.extend(footer_buttons)
        return menu

    async def get_button(self, slug: str) -> Button:
        return await self.button_repo.get(slug=slug)

    async def get_menu(self, slug: str) -> Menu:
        return await self.menu_repo.get(slug=slug)

    def ikb(self, text, callback_data=None, url=None):
        button_text = text if not DEV_MODE_KB else f'{text} ({callback_data})'
        return InlineKeyboardButton(
            button_text,
            callback_data=callback_data,
            url=url)

    @classmethod
    def __call__(cls, session):
        return cls(session)


class Keyboard(BaseKeyboard):

    def get_tariffs_ikb(self, tariffs_list: List[Tariff]):
        ikb_list = [self.ikb(tariff.button_text, f'tariff_{tariff.id}') for tariff in tariffs_list]
        menu = self.build_menu(ikb_list, 1)
        return InlineKeyboardMarkup(menu)


class BaseMenu(BaseKeyboard):

    def __init__(self, session=None, page_num: int = 1,
                 count_per_page: int = 5, **kwargs) -> None:
        super().__init__(session)
        self.page_num = page_num
        self.count_per_page = count_per_page
        self.repo = None
        self._all_items_count = None
        self.columns = 1
        self.button_text_attr = 'name'  # откуда брать текст кнопки
        self.nav_back_button = '<<<'
        self.nav_forward_button = '>>>'
        self.prefix = self.get_prefix()
        self.nav_prefix = f'nav_{self.prefix}'
        self._data = None
        self.is_pagination = False

    def pattern(self, *args) -> str:
        if not args:
            return f'^({self.prefix}_\d(1, 6))$'
        payload = '_'.join([item for item in args])
        return f'^({self.prefix}_{payload}_\d(1, 6))$'

    def nav_pattern(self) -> str:
        return f'^({self.nav_prefix}_\d(1, 2))$'

    def get_prefix(self) -> str:
        prefix = re.sub(
            r'(?<!^)(?=[A-Z])', '_',
            self.__class__.__name__).lower().replace('_menu', '')
        return prefix

    @property
    async def is_last_page(self) -> bool:
        return (
            self.page_num * self.count_per_page >=
            await self.all_items_count
        )

    async def all_items_count(self, **kwargs) -> int:
        if self._all_items_count:
            return self._all_items_count

        # kwargs должны совпадать с полями в базе.
        # TODO: сделать общие kwargs для all_items_count и get_data,
        # т.к. они должны быть одинаковые
        all_items_count = await self.repo.get_all_items_count(**kwargs)
        self._all_items_count = all_items_count
        return all_items_count

    async def all_pages_count(self, **kwargs) -> int:
        """Сколько всего страниц"""
        all_items_count = await self.all_items_count(**kwargs)
        if all_items_count % self.count_per_page == 0:
            return int(all_items_count / self.count_per_page)
        return all_items_count // self.count_per_page + 1

    async def get_data(self, **kwargs) -> list:
        if self._data:
            return self._data

        data = await self.repo.get_by_page(
            page_num=self.page_num,
            count_per_page=self.count_per_page,
            **kwargs
        )
        self._data = data
        return data

    def _get_text(self, item, **kwargs) -> str:
        text = getattr(item, self.button_text_attr)
        return text

    def _get_callback_data(self, item_id=1, **kwargs) -> str:
        return f'{self.prefix}_{item_id}'

    async def get_button_list(self, **kwargs) -> List[InlineKeyboardButton]:
        ikb_list = []
        data = await self.get_data(**kwargs)
        for item in data:
            ikb = self.ikb(
                self._get_text(item, **kwargs),
                self._get_callback_data(item.id, **kwargs)
            )
            ikb_list.append(ikb)
        return ikb_list

    async def _get_header_buttons(self) -> List[InlineKeyboardButton]:
        return None

    async def _get_footer_buttons(self) -> List[InlineKeyboardButton]:
        return None

    async def _get_nav_buttons_paginations(self, **kwargs) -> List[InlineKeyboardButton]:
        """Навигационные кнопки в формате пагинации (страницы)"""
        buttons_list = []
        for page_num in range(1, await self.all_pages_count(**kwargs) + 1):
            name = (
                f'·{page_num}·' if page_num == self.page_num
                else str(page_num)
            )
            ikb = self.ikb(name, f'nav_{page_num}')
            buttons_list.append(ikb)
        return buttons_list

    async def get_nav_buttons(self, **kwargs) -> List[InlineKeyboardButton]:
        if self.is_pagination:
            return await self._get_nav_buttons_paginations(**kwargs)
        return await self._get_nav_buttons_flipping(**kwargs)

    async def _get_nav_buttons_flipping(self, **kwargs) -> List[InlineKeyboardButton]:
        """Навигационные кнопки Вперёд-Назад"""
        pages_count = await self.all_pages_count(**kwargs)
        if self.page_num == 1:
            forward_ikb = self.ikb(self.nav_forward_button, f'{self.nav_prefix}_{self.page_num+1}')
            return [forward_ikb]
        elif 1 < self.page_num < pages_count:
            back_ikb = self.ikb(self.nav_back_button, f'{self.nav_prefix}_{self.page_num-1}')
            forward_ikb = self.ikb(self.nav_forward_button, f'{self.nav_prefix}_{self.page_num+1}')
            return [back_ikb, forward_ikb]
        elif self.page_num == pages_count:
            back_ikb = self.ikb(self.nav_back_button, f'{self.nav_prefix}_{self.page_num-1}')
            return [back_ikb]

    @property
    async def is_nav_buttons(self) -> bool:
        """Определяет или нужны кнопки навигации"""
        return self.count_per_page < await self.all_items_count()

    async def get_ikb(self, **kwargs) -> InlineKeyboardMarkup:
        button_list = await self.get_button_list(**kwargs)
        menu = self.build_menu(
            button_list, self.columns,
            header_buttons=await self._get_header_buttons(),
            footer_buttons=await self._get_footer_buttons()
        )
        if await self.is_nav_buttons:
            menu.insert(-1, await self.get_nav_buttons())
        return InlineKeyboardMarkup(menu)

