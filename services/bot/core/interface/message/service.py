from core.interface.message.repositories import MessageRepository



class MessageSerivice:
    def __init__(self, message_repo: MessageRepository) -> None:
        self.message_repo = message_repo
