import pytz
from flask_admin.model import typefmt
from datetime import datetime

# Определите ваш часовой пояс
local_tz = pytz.timezone('Europe/Moscow')

def datetime_formatter(view, value):
    if value is None:
        return ''
    # Преобразование времени в локальный часовой пояс
    local_dt = value.astimezone(local_tz)
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')

# Добавьте кастомный форматтер в typefmt
MY_DEFAULT_FORMATTERS = dict(typefmt.BASE_FORMATTERS)
MY_DEFAULT_FORMATTERS.update({
    datetime: datetime_formatter
})
