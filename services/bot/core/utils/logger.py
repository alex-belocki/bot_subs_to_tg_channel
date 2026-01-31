import logging

import requests

import core.constants.config as config

# Создаем базовый логгер для внутреннего использования
base_logger = logging.getLogger('telegram_error_logger')
base_logger.setLevel(logging.ERROR)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
base_logger.addHandler(stream_handler)


class TelegramLoggingHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        self.send_error_to_telegram(f'<pre>{log_entry}</pre>')

    def send_error_to_telegram(self, message: str):
        url = 'https://api.telegram.org/bot{}/sendMessage'.format(config.settings.TOKEN)
        data = {'chat_id': config.TG_ADMIN_LIST[0],
                'text': message,
                'parse_mode': 'HTML'}
        try:
            resp = requests.get(url, params=data)
            resp.raise_for_status()
            raise ValueError('error')
        except Exception as e:
            base_logger.exception(f'Ошибка отправки лога в тг: {e}')


def get_extra_logger(level='ERROR'):
    logger = logging.getLogger('my_logger')
    logger.setLevel(getattr(logging, level.upper()))

    # Добавляем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

    # Добавляем наш обработчик для отправки в Telegram с кастомным форматом сообщений
    telegram_handler = TelegramLoggingHandler()
    telegram_format = logging.Formatter('%(levelname)s - %(message)s')  # Формат с HTML тегами
    telegram_handler.setFormatter(telegram_format)
    logger.addHandler(telegram_handler)

    return logger
