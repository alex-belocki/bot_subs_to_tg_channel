import ast
from markupsafe import Markup

from flask_admin.form import FileUploadField
from flask_wtf import FlaskForm
from wtforms import (BooleanField, HiddenField, PasswordField,
                     StringField, SubmitField)
from flask_admin._compat import string_types
from wtforms.widgets import html_params
from wtforms.validators import DataRequired
from wtforms.utils import unset_value


class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня', default=True)
    submit = SubmitField('Отправить')


class MultipleFileUploadInput(object):
    empty_template = "<input %(file)s multiple>"

    # display multiple images in edit view of flask-admin
    data_template = ("<div class='image-thumbnail'>"
                     "   %(images)s"
                     "</div>"
                     "<input %(file)s multiple>")

    def __call__(self, field, **kwargs):

        kwargs.setdefault("id", field.id)
        kwargs.setdefault("name", field.name)

        args = {
            "file": html_params(type="file", **kwargs),
        }

        if field.data and isinstance(field.data, string_types):

            attributes = self.get_attributes(field)

            some_list = list()
            for index, filename in enumerate(attributes):
                some_list.append(
                    f'<input name="files_{index}" readonly="readonly" type="text" value="{filename}"><input type="checkbox" name="{filename}-delete">Delete </input>'

                    )

            args["images"] = "&emsp;".join(some_list)

            template = self.data_template

        else:
            template = self.empty_template

        return Markup(template % args)

    def get_attributes(self, field):
        for item in ast.literal_eval(field.data):
            yield item


class MultipleFileUploadField(FileUploadField):

    widget = MultipleFileUploadInput()

    def process(self, formdata, data=unset_value, extra_filters=None):

        self.formdata = formdata  # get the formdata to delete images
        return super(MultipleFileUploadField, self).process(formdata, data)

    def process_formdata(self, valuelist):

        self.data = list()

        for value in valuelist:
            if self._is_uploaded_file(value):
                self.data.append(value)

    def populate_obj(self, obj, name):

        field = getattr(obj, name, None)

        if field:

            filenames = ast.literal_eval(field)

            for filename in filenames[:]:
                if filename + "-delete" in self.formdata:
                    self._delete_file(filename)
                    filenames.remove(filename)

        else:
            filenames = list()

        for data in self.data:
            if self._is_uploaded_file(data):
                filename = self.generate_name(obj, data)
                filename = self._save_file(data, filename)

                data.filename = filename

                filenames.append(filename)

        setattr(obj, name, str(filenames))


class CopyForm(FlaskForm):
    id = HiddenField('ID', validators=[DataRequired()])
    endpoint = HiddenField('Endpoint', validators=[DataRequired()])
    submit = SubmitField('Отправить')
