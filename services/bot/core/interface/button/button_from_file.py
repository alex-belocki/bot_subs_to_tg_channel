from abc import ABC, abstractmethod



class Button(ABC):

    @abstractmethod
    def get_pattern(self):
        pass



class ButtonFromFile(Button):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = self.get_messages()

    def get_messages(self):
        return MESSAGES_DICT

    def get_message(self, key):
        # Получение конкретного сообщения по ключу
        return self.messages.get(key)

    @property
    def pattern(self):
        # ...
        return pattern_str


# type (inline or reply)
# callback_data
# inline_url
# request_contact
# request_location

