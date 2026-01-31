from flask import flash, redirect, request, url_for
from flask_admin import AdminIndexView, expose
from flask_admin.babel import gettext
from flask_admin.contrib.fileadmin import FileAdmin
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import FileUploadField, ImageUploadField
from flask_admin.menu import MenuLink
from flask_admin.menu import MenuView as AdminMenuView
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from wtforms import BooleanField, TextAreaField
from wtforms.validators import ValidationError
from werkzeug.utils import secure_filename

import core.constants.config as config
from core.database.database import db
import forms
from common.models.admin_models import AdminModel
from common.models.interface_models import Button, Menu, Message

from core.interface.services import ButtonRepository, MenuRepository, MessageRepository



class MyHomeView(AdminIndexView):

    @expose('/')
    def index(self):
        if current_user.is_authenticated:
            return self.render('admin/index.html')
        else:
            return redirect(url_for('admin.login'))

    @expose('/login')
    def login(self):
        if current_user.is_authenticated:
            return redirect(url_for('admin.index'))

        title = 'Авторизация'
        login_form = forms.LoginForm()
        return self.render('login.html', page_title=title, form=login_form)

    @expose('/process-login', methods=['POST'])
    def process_login(self):
        form = forms.LoginForm()
        if form.validate_on_submit():
            user = db.session.query(AdminModel).filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                flash('Вы вошли на сайт')
                return redirect(url_for('admin.index'))

        flash('Неправильное имя пользователя или пароль')
        return redirect(url_for('admin.login'))

    @expose('/logout')
    def logout(self):
        logout_user()
        flash('Вы успешно разлогинились')
        return redirect(url_for('admin.login'))

    def _get_slug(self, slug: str):
        """Вычисляет slug при копировании"""
        head = '-'.join(slug.split('-')[:-1])  # часть до "copy"
        tail = slug.split('-')[-1]
        if tail == 'copy':
            return f'{slug}1'
        elif tail.startswith('copy'):
            num = int(tail.replace('copy', ''))
            return f'{head}-copy{num+1}'
        return f'{slug}-copy'

    @expose('/copy-row', methods=['POST'])
    def copy_row(self):
        message_repo = MessageRepository(db.session)
        menu_repo = MenuRepository(db.session)
        button_repo = ButtonRepository(db.session)
        form = forms.CopyForm()
        if form.validate_on_submit():
            endpoint = request.form.get('endpoint')
            model_id = int(request.form.get('id'))

            if endpoint == 'message':
                model = Message
                old_model = message_repo.get_model(model, model_id)
                try:
                    new_model_id = message_repo.add_model(
                        model=model,
                        slug=self._get_slug(old_model.slug),
                        text_ru=old_model.text_ru,
                        text_en=old_model.text_en,
                        image_path=old_model.image_path,
                        image_id=old_model.image_id,
                        animation_path=old_model.animation_path,
                        animation_id=old_model.animation_id,
                        video_path=old_model.video_path,
                        video_id=old_model.video_id,
                        menu_id=old_model.menu_id)
                except IntegrityError:
                    flash(gettext('Ошибка. Нажимайте значок копировать в строке с наибольшей цифрой'), 'error')
                    return redirect(url_for(f'{endpoint}.index_view'))

            elif endpoint == 'menu':
                model = Menu
                old_model = menu_repo.get_model(model, model_id)

                try:
                    menu_id = menu_repo.add_model(
                        model=model,
                        slug=self._get_slug(old_model.slug),
                        markup=old_model.markup,
                        is_persistent=old_model.is_persistent
                    )
                except IntegrityError:
                    flash(gettext('Ошибка. Нажимайте значок копировать в строке с наибольшей цифрой'), 'error')
                    return redirect(url_for(f'{endpoint}.index_view'))


                menu = menu_repo.get(id=menu_id)
                menu.buttons_list = old_model.buttons_list

            elif endpoint == 'button':
                model = Button
                old_model = button_repo.get_model(model, model_id)

                try:
                    button_repo.add_model(
                        model=model,
                        slug=self._get_slug(old_model.slug),
                        text_ru=old_model.text_ru,
                        text_en=old_model.text_en,
                        type_=old_model.type_,
                        callback_data=old_model.callback_data,
                        inline_url=old_model.inline_url,
                        request_contact=old_model.request_contact,
                        request_location=old_model.request_location,
                        message_id=old_model.message_id
                    )
                except IntegrityError:
                    flash(gettext('Ошибка. Нажимайте значок копировать в строке с наибольшей цифрой'), 'error')
                    return redirect(url_for(f'{endpoint}.index_view'))

            db.session.commit()
            flash(gettext('Запись успешно скопирована'), 'success')
            return redirect(url_for(f'{endpoint}.index_view'))

    def is_visible(self):
        return False


class MessageView(ModelView):
    can_delete = True
    can_create = True
    list_template = 'admin/list-with-copy.html'

    form_overrides = dict(text_ru=TextAreaField,
                          text_en=TextAreaField,
                          image_path=ImageUploadField,
                          animation_path=FileUploadField,
                          video_path=FileUploadField,
                          voice_path=FileUploadField,
                          video_note_path=FileUploadField)

    @property
    def extra_js(self):
        with self.admin.app.app_context():
            return [url_for('static', filename='js/message.js')]

    form_args = dict(
        image_path=dict(label='Изображение',
                        base_path=config.STATIC_FOLDER,
                        relative_path='files/messages/'),

        animation_path=dict(label='Анимация',
                            base_path=config.STATIC_FOLDER,
                            relative_path='files/messages/'),

        video_path=dict(label='Видео',
                        base_path=config.STATIC_FOLDER,
                        relative_path='files/messages/'),

        video_note_path=dict(label='Видео заметка',
                             base_path=config.STATIC_FOLDER,
                             relative_path='files/messages/'),

        voice_path=dict(label='Голосовое сообщение',
                        base_path=config.STATIC_FOLDER,
                        relative_path='files/messages/'),

    )

    form_widget_args = dict(text_ru=dict(rows=8),
                            text_en=dict(rows=8),
                            markup=dict(rows=4))
    form_columns = ('slug', 'text_ru', 'image_path', 'video_path', 'video_note_path', 'voice_path', 'menu')
    column_list = ('slug', 'text_ru', 'menu')
    column_exclude_list = ('image_id', 'image_path')
    column_searchable_list = ('slug', 'text_ru')
    column_default_sort = ('id', True)

    column_labels = dict(text_ru='Текст',
                         text_en='Текст (en)',
                         menu='Меню')

    # def on_form_prefill(self, form, id, **kwargs):
    #     form.slug.render_kw = {'readonly': True}

    def on_model_change(self, form, model, is_created):
        model.slug = model.slug.lower().replace(' ', '-')
        if not model.slug.startswith('msg'):
            model.slug = f'msg-{model.slug}'

        if model.image_id:
            model.image_id = None
        elif model.animation_id:
            model.animation_id = None
        elif model.video_id:
            model.video_id = None

    def render(self, template, **kwargs):
        # указываем наш шаблон
        if template == self.list_template:
            form = forms.CopyForm()
            kwargs['form'] = form
        return super().render(template, **kwargs)

    def is_accessible(self):
        return current_user.is_authenticated

    def is_visible(self):
        return True


class MenuView(ModelView):
    column_default_sort = ('id', True)
    list_template = 'admin/list-with-copy.html'

    form_columns = ('slug', 'buttons_list', 'markup')
    column_list = ('slug', 'buttons_list', 'is_persistent')
    column_editable_list = ('is_persistent',)
    form_overrides = dict(markup=TextAreaField)

    form_widget_args = dict(markup=dict(rows=4))

    column_labels = dict(buttons_list='Кнопки',
                         markup='Разметка')

    def on_form_prefill(self, form, id, **kwargs):
        form.slug.render_kw = {'readonly': True}

    def on_model_change(self, form, model, is_created):
        model.slug = model.slug.lower().replace(' ', '-')
        if not model.slug.startswith('menu'):
            model.slug = f'menu-{model.slug}'

    def render(self, template, **kwargs):
        # указываем наш шаблон
        if template == self.list_template:
            form = forms.CopyForm()
            kwargs['form'] = form
        return super().render(template, **kwargs)

    def is_accessible(self):
        return current_user.is_authenticated

    def is_visible(self):
        return True


class ButtonView(ModelView):
    can_delete = True
    can_create = True
    column_default_sort = ('id', True)
    # column_exclude_list = ('callback_data',)
    # form_excluded_columns = ('callback_data',)
    list_template = 'admin/list-with-copy.html'

    column_searchable_list = ('slug',)

    form_extra_fields = {'is_single': BooleanField(default=False)}
    form_columns = ('slug', 'text_ru', 'type_', 'callback_data', 'inline_url',
                    'request_contact', 'request_location', 'is_single')

    column_exclude_list = ('text_en',)

    column_labels = dict(message='Сообщение',
                         text_ru='Текст (ru)',
                         text_en='Текст (en)',
                         type_='Тип',
                         callback_data='Колбек данные',
                         inline_url='Инлайн ссылка')

    form_choices = dict(type_=[
        ('inline', 'inline'),
        ('reply', 'reply')
        ])

    # def on_form_prefill(self, form, id, **kwargs):
    #     form.slug.render_kw = {'readonly': True}

    def on_model_change(self, form, model, is_created):
        model.slug = model.slug.lower().replace(' ', '-')
        if not model.slug.startswith('btn'):
            model.slug = f'btn-{model.slug}'

        if not model.callback_data and model.type_ == 'inline' and not model.inline_url:
            model.callback_data = model.slug.replace('btn-', '')\
                .replace('-', '_')

    def after_model_change(self, form, model, is_created):
        if form.is_single.data:
            slug = model.slug.replace('btn', 'menu')
            menu = Menu(slug=slug, markup=str(model.id))
            self.session.add(menu)
            self.session.flush()

            menu.buttons_list.append(model)
            self.session.commit()

    def render(self, template, **kwargs):
        # указываем наш шаблон
        if template == self.list_template:
            form = forms.CopyForm()
            kwargs['form'] = form
        return super().render(template, **kwargs)

    def is_accessible(self):
        return current_user.is_authenticated

    def is_visible(self):
        return True


class SettingsView(ModelView):
    can_delete = False
    column_editable_list = ('value_',)
    column_default_sort = ('id')
    column_labels = dict(key='Переменная',
                         value_='Значение')

    def on_form_prefill(self, form, id, **kwargs):
        form.key.render_kw = {'readonly': True}

    def is_accessible(self):
        return current_user.is_authenticated


class LoginMenuLink(MenuLink):

    def is_accessible(self):
        return not current_user.is_authenticated


class LogoutMenuLink(MenuLink):
    def is_accessible(self):
        return current_user.is_authenticated


class MyMenuView(AdminMenuView):
    """
    https://github.com/flask-admin/flask-admin/blob/master/flask_admin/menu.py
    """
    def __init__(self, name, view=None, cache=True) -> None:
        super().__init__(name, view=view, cache=cache)
        self.name = name
        self._view = view
        self._cache = cache

    @property
    def color(self):
        return '#f30733'

    @property
    def items_count(self):
        if self.endpoint == 'user':
            return self.users_count
        # elif self.endpoint == 'conv':
        #     return self.chat_messages_count
        return 0

    @property
    def name_menu(self):
        if self.items_count:
            return f'{self.name} <span class="badge" style="background-color: {self.color};">{self.items_count}</span>'
        return self.name

    @property
    def endpoint(self):
        return self._view.endpoint

    @property
    def session(self):
        return self._view.session

    @property
    def users_count(self):
        # return (
        #     self.session.query(User)
        #     .filter(User.status == UserStatus.REGISTERED.name)
        #     .count()
        # )
        return 0


class MyFileAdmin(FileAdmin):

    def get_upload_form(self):

        class UploadForm(self.form_base_class):

            upload = forms.MultipleFileUploadField()

            def __init__(self, *args, **kwargs):
                super(UploadForm, self).__init__(*args, **kwargs)
                self.admin = kwargs['admin']

            def validate_upload(self, field):
                if not self.upload.data:
                    raise ValidationError(gettext('File required.'))

                for data in self.upload.data:
                    filename = data.filename
                    if not self.admin.is_file_allowed(filename):
                        raise ValidationError(gettext('Invalid file type.'))

        return UploadForm

    def _save_form_files(self, directory, path, form):
        for data in form.upload.data:
            filename = self._separator.join([directory, secure_filename(data.filename)])
            if self.storage.path_exists(filename):
                secure_name = self._separator.join([path, secure_filename(data.filename)])
                raise Exception(gettext('File "%(name)s" already exists.',
                                        name=secure_name))
            else:
                self.save_file(filename, data)
                self.on_file_upload(directory, path, filename)

    @expose('/upload/', methods=('GET', 'POST'))
    @expose('/upload/<path:path>', methods=('GET', 'POST'))
    def upload(self, path=None):
        """
            Upload view method

            :param path:
                Optional directory path. If not provided, will use the base directory
        """
        # Get path and verify if it is valid
        base_path, directory, path = self._normalize_path(path)

        if not self.can_upload:
            flash(gettext('File uploading is disabled.'), 'error')
            return redirect(self._get_dir_url('.index_view', path))

        if not self.is_accessible_path(path):
            flash(gettext('Permission denied.'), 'error')
            return redirect(self._get_dir_url('.index_view'))

        form = self.upload_form()
        if self.validate_form(form):
            try:
                self._save_form_files(directory, path, form)
                if isinstance(form.upload.data, list):
                    files = ', '.join([data.filename for data in form.upload.data])
                    flash(gettext(f'Successfully saved files: {files}'), 'success')
                else:
                    flash(gettext('Successfully saved file: %(name)s',
                                name=form.upload.data.filename), 'success')
                return redirect(self._get_dir_url('.index_view', path))
            except Exception as ex:
                flash(gettext('Failed to save file: %(error)s', error=ex), 'error')

        if self.upload_modal and request.args.get('modal'):
            template = self.upload_modal_template
        else:
            template = self.upload_template

        return self.render(template, form=form,
                           header_text=gettext('Upload File'),
                           modal=request.args.get('modal'))

    def is_accessible(self):
        return current_user.is_authenticated

    def is_visible(self):
        return False
