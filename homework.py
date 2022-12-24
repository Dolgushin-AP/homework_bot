import json
import logging
import os
import sys
import time
from dotenv import load_dotenv
from http import HTTPStatus

import requests
import telegram

from exceptions import (BadResponse, EmptyResponse, NotForSendInTelegram,
                        TelegramError, JSONDecodeError)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler = logging.StreamHandler()


def check_tokens():
    """Проверка доступности переменных окружения.
    При отсутствии хотя бы одной переменной бот будет остановлен.
    """
    message_info = 'Проверка наличия всех токенов'
    logger.info(message_info)
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        message_info = f'Попытка отправки сообщения: {message}'
        logger.info(message_info)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        message_debug = f'Отправка сообщения: {message}'
        logger.debug(message_debug)
    except telegram.error.TelegramError as error:
        message_error = f'Ошибка отправки сообщения в Telegram: {message}'
        logger.error(message_error)
        raise TelegramError(
            f'Не удачная отправка сообщение {error}')
    else:
        message_debug = f'Сообщение успешно отправлено: {message}'
        logger.debug(message_debug)


def get_api_answer(timestamp):
    """Запрос списка домашних работ в эндпоинте API-сервиса."""
    request_timestamp = timestamp or int(time.time())
    request_parameters = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': request_timestamp},
    }
    message = ('Отправка запроса к API: {url}, {headers}, {params}.'
               ).format(**request_parameters)
    logger.info(message)
    try:
        homework_statuses = requests.get(**request_parameters)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise BadResponse(
                f'API не отвечает OK.'
                f'код ошибки: {homework_statuses.status_code}.'
                f'причина: {homework_statuses.reason}.'
                f'текст: {homework_statuses.text}.'
            )
        return homework_statuses.json()
    except json.JSONDecodeError as json_error:
        message_error = f'Ошибка json: {json_error}'
        raise JSONDecodeError(message_error) from json_error
    except requests.exceptions.RequestException as error_request:
        message_error = f'Ошибка в запросе API: {error_request}'
        raise BadResponse(message_error)


def check_response(response):
    """Проверка ответа API на корректность.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    """
    message_info = 'Начало проверки'
    logger.info(message_info)
    if not isinstance(response, dict):
        raise TypeError('Ошибка в типе приведенных данных')
    if 'homeworks' not in response or 'current_date' not in response:
        raise EmptyResponse('Пустой ответ API')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('При ключе homeworks данные приходят не в виде списка')
    return homeworks


def parse_status(homework):
    """Извлечение из информации о конкретной домашней работе её статус.
    В случае успеха, функция возвращает подготовленную
    для отправки в Telegram строку.
    """
    message_info = 'Проведение проверки и извлечение статуса работы'
    logger.info(message_info)
    if 'homework_name' not in homework:
        raise KeyError('В API отсутствует ключ homework_name')
    homework_name = homework.get('homework_name')
    if homework_name is None:
        message_error = f'Отсутствует имя работы: {homework_name}'
        logger.critical(message_error)
        raise KeyError(message_error)
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы - {homework_status}')
    return ('Изменился статус проверки работы "{homework_name}". {verdict}'
            ).format(homework_name=homework_name,
                     verdict=HOMEWORK_VERDICTS[homework_status]
                     )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message_error = 'Отсутствует токен'
        logger.critical(message_error)
        sys.exit('Бот остановлен!')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    message_info = 'Старт работы бота'
    logger.info(message_info)
    first_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get(
                'current_date', timestamp
            )
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = 'Нет новых статусов'
            if message != first_message:
                send_message(bot, message)
                first_message = message
            else:
                message_debug = 'Статус работ не изменён'
                logger.debug(message_debug)
        except NotForSendInTelegram as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            if message != first_message:
                send_message(bot, message)
                first_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
