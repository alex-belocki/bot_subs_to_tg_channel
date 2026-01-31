from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from werkzeug.security import generate_password_hash


class UserView(ModelView):
    column_display_pk = True

    column_list = ('user_id', 'first_name', 'username', 'created_at')
    column_searchable_list = ('user_id', 'first_name', 'username')

    column_labels = dict(first_name='Имя',
                         username='Логин',
                         created_at='Дата подписки')

    def is_accessible(self):
        return current_user.is_authenticated


class AdminView(ModelView):
    can_delete = False
    can_create = False
    can_edit = True
    column_exclude_list = ('password')

    def on_model_change(self, form, model, is_created):
        if not model.password.startswith('sha'):
            model.password = generate_password_hash(
                model.password, method='sha256'
            )

    def is_accessible(self):
        return current_user.is_authenticated

