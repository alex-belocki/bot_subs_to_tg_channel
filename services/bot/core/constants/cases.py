class BaseCase:
    GENITIVE = ''
    ACCUSATIVE = ''
    NOMINATIVE = ''

    @classmethod
    def handle_case(cls, num: int, word_only=False) -> str:
        """Вычисляем падеж в зависимости от цифры"""
        if num % 10 in [0, 5, 6, 7, 8, 9] or num in range(11, 15):
            return f'{num} {cls.GENITIVE}' if not word_only else cls.GENITIVE
        elif num % 10 in [2, 3, 4]:
            return f'{num} {cls.ACCUSATIVE}' if not word_only else cls.ACCUSATIVE
        elif num % 10 == 1:
            return f'{num} {cls.NOMINATIVE}' if not word_only else cls.NOMINATIVE


class CurrencyTitleCase:
    """
    NOMINATIVE -- именительный (кто? что?)
    GENITIVE -- родительный (кого? чего?)
    DATIVE -- дательный (кому? чему?)
    ACCUSATIVE -- винительный (кого? что?)
    INSTRUMENTAL -- творительный (кем? чем?)
    PREPOSITIONAL -- предложный (о ком? о чём?)
    """
    ACCUSATIVE = 'валюту'  # винительный


class RequestCase(BaseCase):
    GENITIVE = 'запросов'
    ACCUSATIVE = 'запроса'
    NOMINATIVE = 'запрос'


class Cases:
    CURRENCY_TITLE = CurrencyTitleCase
    REQUEST = RequestCase
