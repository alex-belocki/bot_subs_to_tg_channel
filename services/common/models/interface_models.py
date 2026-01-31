from typing import List, Optional

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Table
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


menu_button = Table(
    "menu_button",
    Base.metadata,
    Column("menu_id", Integer, ForeignKey("kb_menu.id"), index=True),
    Column("button_id", Integer, ForeignKey("buttons.id"), index=True)
)


class Message(Base):
    __tablename__ = 'messages'

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    text_ru: Mapped[Optional[str]]
    text_en: Mapped[Optional[str]]
    image_path: Mapped[Optional[str]]
    image_id: Mapped[Optional[str]]  # telegram_id
    animation_path: Mapped[Optional[str]]
    animation_id: Mapped[Optional[str]]
    video_path: Mapped[Optional[str]]
    video_id: Mapped[Optional[str]]
    video_note_path: Mapped[Optional[str]]
    video_note_id: Mapped[Optional[str]]
    voice_path: Mapped[Optional[str]]
    voice_id: Mapped[Optional[str]]
    menu_id: Mapped[Optional[int]] = mapped_column(ForeignKey('kb_menu.id'))

    menu: Mapped['Menu'] = relationship(cascade='save-update')

    def __repr__(self):
        return f'<{self.slug}>'


class Menu(Base):
    __tablename__ = 'kb_menu'

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    markup: Mapped[Optional[str]]
    is_persistent: Mapped[bool] = mapped_column(default=False)

    buttons_list: Mapped[List['Button']] = relationship(
        back_populates='menu_list',
        secondary='menu_button', lazy='joined',
        cascade='save-update'
    )

    def __repr__(self) -> str:
        return self.slug + ' ' + ', '.join(
            [repr(button) for button in self.buttons_list]
        )


class Button(Base):
    __tablename__ = 'buttons'

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    text_ru: Mapped[str]
    text_en: Mapped[Optional[str]]
    type_: Mapped[str] = mapped_column(String(6), default='inline')
    callback_data: Mapped[Optional[str]]
    inline_url: Mapped[Optional[str]]
    request_contact: Mapped[bool] = mapped_column(default=False)
    request_location: Mapped[bool] = mapped_column(default=False)
    message_id: Mapped[Optional[int]] = mapped_column(ForeignKey('messages.id'))

    menu_list: Mapped[List[Menu]] = relationship(back_populates='buttons_list',
                                                 secondary=menu_button)

    @property
    def _ekran_symbols(self):
        return ['(', ')']

    def _prepare_pattern_text(self, text: str):
        for symb in self._ekran_symbols:
            if symb in text:
                text = text.replace(symb, f'\{symb}')
        return text

    def pattern(self, **kwargs):
        if self.callback_data:
            try:
                self.callback_data = self.callback_data.format(**kwargs)
            except KeyError:
                pass

            payload_cnt = self.callback_data.count('{')
            payload_ptrn = '_'.join(['\d{1,20}' for i in range(payload_cnt)])
            num = self.callback_data.find('{')
            data_head = (
                self.callback_data[:num] if
                payload_cnt > 0 else self.callback_data
            )
            return f'^({data_head}{payload_ptrn})$'

        elif self.inline_url:
            return None

        if self.text_en:
            pattern = f'^({self._prepare_pattern_text(self.text_ru)}|'\
                      f'{self._prepare_pattern_text(self.text_en)})$'
        else:
            pattern = f'^({self._prepare_pattern_text(self.text_ru)})$'

        return pattern

    def __repr__(self):
        return f'[{self.id} - {self.text_ru} ({self.type_})]'
