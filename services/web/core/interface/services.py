from telegram import (
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)

from core.interface.button.repositories import ButtonRepository
from core.interface.menu.repositories import MenuRepository
from core.interface.message.repositories import MessageRepository
from core.interface.settings.repositories import SettingsRepository


class BotInterfaceService:
    def __init__(self, session=None) -> None:
        self.button_repo = ButtonRepository(session)
        self.menu_repo = MenuRepository(session)
        self.message_repo = MessageRepository(session)
        self.settings_repo = SettingsRepository(session)

    def is_inline(self, menu):
        '''Проверяет или клавиатура инлайн '''
        if not menu.buttons_list:
            return False
        if menu.buttons_list[0].type_ == 'inline':
            return True
        return False

    def _get_text(self, button, **kwargs):
        lang = kwargs.get('lang', 'ru')
        return getattr(button, f'text_{lang}').format(**kwargs)

    def _get_ikb(self, button, **kwargs) -> InlineKeyboardButton:
        '''Возвращает инлайн кнопку '''
        lang = kwargs.get('lang', 'ru')
        if button.inline_url:
            ikb = InlineKeyboardButton(
                getattr(button, f'text_{lang}'),
                url=button.inline_url.format(**kwargs)
            )
        elif button.callback_data:
            ikb = InlineKeyboardButton(
                self._get_text(button, **kwargs),
                callback_data=button.callback_data.format(**kwargs)
            )
        return ikb

    def _get_reply_button(self, button, **kwargs):
        lang = kwargs.get('lang', 'ru')
        if button.request_contact or button.request_location:
            text = getattr(button, f'text_{lang}').format(**kwargs)
            return KeyboardButton(text,
                                  request_contact=button.request_contact,
                                  request_location=button.request_location)

        return getattr(button, f'text_{lang}').format(**kwargs)

    def _get_buttons_row_from_id(self, menu, id_list, **kwargs):
        '''Получает одну строку клавиатуры из id '''
        buttons_row = list()
        for id in id_list:
            button = [button for button in
                      menu.buttons_list if
                      button.id == id]

            if not button:
                continue

            assert isinstance(button, list)

            if self.is_inline(menu):
                ikb = self._get_ikb(button[0], **kwargs)
                buttons_row.append(ikb)
            else:
                buttons_row.append(
                    self._get_reply_button(button[0], **kwargs)
                )

        return buttons_row

    def _get_keyboard_from_markup(self, menu, **kwargs):
        keyboard = list()
        rows_list = menu.markup.format(**kwargs).split('\n')
        for row in rows_list:
            if row == '':
                continue

            delimiter = '|'

            id_list = [int(id) for id in row.split(delimiter)]
            buttons_row = self._get_buttons_row_from_id(menu, id_list, **kwargs)
            keyboard.append(buttons_row)

        return keyboard

    def _get_menu(self, slug: str = None, menu_id: int = None):
        if slug:
            return self.menu_repo.get(slug=slug)
        return self.menu_repo.get(id=menu_id)

    def get_keyboard(self, slug: str = None, menu_id: int = None, menu=None, **kwargs):
        menu = self._get_menu(slug=slug, menu_id=menu_id) if not menu else menu
        if menu is None:
            raise Exception(f"Menu with slug '{slug}' not found")

        if 'reply_markup' in kwargs:
            assert isinstance(kwargs['reply_markup'], InlineKeyboardMarkup), \
                'Меню нужно вызывать menu.markup(), а не передавать функцию menu.markup'
            return kwargs['reply_markup']

        keyboard = self._get_keyboard_from_markup(menu, **kwargs)

        if self.is_inline(menu):
            return InlineKeyboardMarkup(keyboard)

        return ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True,
            is_persistent=menu.is_persistent
        )

    def get_message(self, slug: str):
        return self.message_repo.get(slug=slug)

    def get_button(self, slug: str):
        return self.button_repo.get(slug=slug)

    def get_button_by_text(self, text: str):
        return self.button_repo.get(text_ru=text)

    def get_settings(self, key: str):
        settings = self.settings_repo.get(key=key)
        return settings.value

    def is_float(self, element) -> bool:
        try:
            float(element)
            return True
        except ValueError:
            return False

    @classmethod
    def __call__(cls, session):
        return cls(session)
