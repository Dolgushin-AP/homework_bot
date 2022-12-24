class TelegramError(Exception):
    """Ошибка телеграма."""
    pass


class BadResponse(Exception):
    """Неподходящий ответ."""
    pass


class EmptyResponse(Exception):
    """Пустой ответ API."""
    pass


class NotForSendInTelegram(Exception):
    """Не для отправки в телеграм."""
    pass

class JSONDecodeError(Exception):
    """Ошибка с Json"""
    pass
