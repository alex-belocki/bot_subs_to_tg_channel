import os

from telegram.ext import ExtBot


def get_mq_bot() -> ExtBot:
    token = os.getenv('TOKEN')
    mybot = ExtBot(token)
    return mybot
