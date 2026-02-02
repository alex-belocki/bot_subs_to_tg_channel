import logging
import os
from typing import cast

from flask import Flask, redirect, url_for
from flask_admin import Admin
from flask_login import current_user, LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix

from core.database.database import db
from common.models.admin_models import AdminModel
from common.models.interface_models import Button, Menu, Message
from common.models.models import Settings
from common.models.users_models import SendMessageCampaign, User
from common.models.subscriptions_models import Subscription, SubscriptionAccess
from modules.payments import payments_bp


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level = logging.INFO
    )


def create_app() -> Flask:
    app = Flask(__name__)

    # Running behind reverse proxies (Traefik -> nginx) in production.
    # Trust a single hop for forwarded headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.config.from_pyfile('core/constants/config.py')
    db.init_app(app)
    app.register_blueprint(payments_bp)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'admin.login'

    from core.interface.views import (
        ButtonView,
        LoginMenuLink,
        LogoutMenuLink,
        MenuView,
        MessageView,
        MyHomeView,
        MyFileAdmin,
        MyMenuView,
        SettingsView
    )
    from modules.campaign.views import CampaignView
    from modules.user.views import AdminView, UserView
    from modules.subscriptions.views import SubscriptionView, SubscriptionAccessView

    class MyAdmin(Admin):
        """
        https://flask-admin.readthedocs.io/en/latest/_modules/flask_admin/base/
        """
        def _add_view_to_menu(self, view):
            self.add_menu_item(MyMenuView(view.name, view), view.category)

    admin = MyAdmin(
        template_mode='bootstrap3',
        name='Админка',
        index_view=MyHomeView(url='/admin/')
        )

    admin.init_app(app)
    admin.add_view(UserView(User, db.session, name='Пользователи'))
    admin.add_view(SubscriptionView(Subscription, db.session, name='Подписки', category='Подписки'))
    admin.add_view(SubscriptionAccessView(SubscriptionAccess, db.session, name='Доступы', category='Подписки'))
    admin.add_view(MessageView(Message, db.session, name='Сообщения'))
    admin.add_view(MenuView(Menu, db.session, name='Меню'))
    admin.add_view(ButtonView(Button, db.session, name='Кнопки'))
    admin.add_view(CampaignView(SendMessageCampaign, db.session, name='Рассылка'))
    admin.add_view(SettingsView(Settings, db.session, name='Настройки'))
    admin.add_view(AdminView(AdminModel, db.session, name='Админ'))

    admin.add_link(LoginMenuLink(name='Логин', category='', url='/admin/login'))
    admin.add_link(LogoutMenuLink(name='Выход', category='', url='/admin/logout'))

    # Путь, по которому будут находиться файлы
    path = os.path.join(os.path.dirname(__file__), 'static')
    admin.add_view(MyFileAdmin(path, '/static/', name='Static Files'))


    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('admin.index'))
        return redirect(url_for('admin.login'))

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.query(AdminModel).get(user_id)

    return cast(Flask, admin.app)


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
