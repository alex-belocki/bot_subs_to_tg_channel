import datetime as dt
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    func,
    Integer,
    Table
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


user_campaign = Table(
    "user_campaign",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.user_id")),
    Column("campaign_id", Integer, ForeignKey("send_message_campaign.id"))
)


class User(Base):
    __tablename__ = 'users'

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str]
    last_name: Mapped[Optional[str]]
    username: Mapped[Optional[str]]
    phone: Mapped[Optional[str]]
    lang: Mapped[str] = mapped_column(default='ru')
    timezone: Mapped[str] = mapped_column(default='Europe/Moscow')
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now()
    )
    source: Mapped[Optional[str]]

    campaign_list: Mapped[List['SendMessageCampaign']] = relationship(
        back_populates='send_to',
        secondary=user_campaign
    )

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'

    @property
    def chat_url(self) -> str:
        """
        Ссылка на чат с юзером, или на его
        профиль, если не задан username
        """
        if self.username:
            return f'https://t.me/{self.username}'
        return f'tg://user?id={self.user_id}'

    @property
    def html_link(self) -> str:
        """Html-сниппет для вставки в html-код"""
        return f'<a href="tg://user?id={self.user_id}">{self.first_name}</a>'

    def __repr__(self) -> str:
        return f'<{self.user_id} - {self.first_name}>'


class SendMessageCampaign(Base):
    __tablename__ = 'send_message_campaign'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    text: Mapped[Optional[str]]
    preview: Mapped[bool] = mapped_column(default=False)
    send_post: Mapped[bool] = mapped_column(default=False)
    menu_id: Mapped[Optional[int]] = mapped_column(ForeignKey('kb_menu.id'))
    date: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now()
    )
    status: Mapped[str] = mapped_column(default='Выполняется')
    files: Mapped[Optional[str]]

    send_to: Mapped[User] = relationship(
        back_populates='campaign_list',
        secondary=user_campaign
    )

    menu: Mapped['Menu'] = relationship(cascade='save-update')

    def __repr__(self):
        return f'<{self.name}>'
