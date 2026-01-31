
class Message:
    def __init__(self, text, image_path=None, image_id=None, menu=None):
        self.text = text
        self.image_path = image_path
        self.image_id = image_id
        self.menu = menu


MESSAGES_DICT = {
    'greeting': Message(
        text='Приветствую! Как я могу вам помочь?',
        image_path='path/to/image.jpg',
        image_id=12345,
    ),
    'farewell': Message(
        text='До свидания! Удачного дня!',
    ),
    'thank_you': Message(
        text='Спасибо за ваше сообщение!',
        menu=['Option 1', 'Option 2', 'Option 3'],
    ),
    'error': Message(
        text='Произошла ошибка. Пожалуйста, попробуйте еще раз.',
    ),
}
