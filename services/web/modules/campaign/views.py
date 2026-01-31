from asgiref.sync import async_to_sync
import ast
import datetime as dt
import logging
import threading

from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from wtforms import TextAreaField

from .message_campaign import MessageCampaign, TelegramMessageSender
from .utils import get_menus_without_variable_buttons
import core.constants.config as config
from core.database.database import db
import forms
from core.interface.services import BotInterfaceService
from common.models.users_models import SendMessageCampaign, User
from core.utils.mq_bot import get_mq_bot


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.INFO
    )
logger = logging.getLogger(__name__)


class CampaignView(ModelView):
    create_modal = True

    if not config.DEV_MODE:
        can_edit = False
        can_delete = False

    column_display_pk = True
    column_default_sort = ('date', True)
    column_list = ('id', 'name', 'date', 'status')
    create_modal_template = 'admin/campaign/create-modal.html'

    column_labels = dict(name='Название',
                         date='Время',
                         status='Статус',
                         send_to='Кому',
                         text='Текст',
                         button_text='Текст кнопки',
                         button_url='Ссылка кнопки')

    column_descriptions = dict(
        send_to='Список юзеров, которым отправлять рассылку. Если пусто, то отправляет по всем юзерам.',
        send_post='Если стоит галка, то отправляется пост. Если галки нет, то отправляется сообщение из бота юзерам',
        files='Список файлов')

    form_columns = ('name', 'send_to', 'text',
                    'menu', 'files')

    form_overrides = dict(text=TextAreaField,
                          files=forms.MultipleFileUploadField)

    form_widget_args = dict(
        text=dict(rows=8),
        name=dict(value=f'Рассылка {dt.datetime.now().strftime("%d.%m.%Y")}')
    )

    form_args = dict(files=dict(label='Файлы',
                                base_path=config.STATIC_FOLDER,
                                relative_path='files/'),

                     menu=dict(query_factory=lambda: get_menus_without_variable_buttons())
                    )

    def on_model_change(self, form, model, is_created):
        model.date = dt.datetime.now()

    def get_recipients_list(self, model):
        if model.send_to:
            return (user.user_id for user in model.send_to)
        return (user.user_id for user in self.session.query(User))

    def _get_markup(self, menu):
        if not menu:
            return
        bi = BotInterfaceService(db.session)
        return bi.get_keyboard(menu=menu)

    def _send_campaign(self, sender, session, app, campaign_id):
        with app.app_context():
            logging.info('Начало отправления рассылки...')

            # заново отбираем, т.к. если передавать
            # модель сразу, то возникают ошибки сессии
            campaign = (
                session.query(SendMessageCampaign)
                .get(campaign_id)
            )
            camp = MessageCampaign(sender, campaign, session=session)
            async_to_sync(camp.send)()

            logging.info('Конец отправления рассылки...')
            session.commit()

    def after_model_change(self, form, model, is_created):
        sender = TelegramMessageSender(
            name=model.name,
            text=model.text,
            preview=model.preview,
            send_post=model.send_post,
            reply_markup=self._get_markup(model.menu),
            files_list=ast.literal_eval(model.files),
            recipients=self.get_recipients_list(model),
            bot=get_mq_bot()
        )

        t = threading.Thread(
            None, self._send_campaign,
            args=[sender, self.session, self.admin.app, model.id]
        )
        t.start()

    def is_visible(self):
        return False

    def is_accessible(self):
        return current_user.is_authenticated
