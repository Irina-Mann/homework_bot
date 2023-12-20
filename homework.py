import logging
import os
import requests
import sys
import telegram
import time

from dotenv import load_dotenv

from exceptions import ResponseError, TokenNoneError

from http import HTTPStatus

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


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


def check_tokens():
    """Проверка наличия переменных окружения."""
    params = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if not all(params):
        logging.critical('Переменная окружения недоступна')
        raise TokenNoneError()


def send_message(bot, message):
    """Отправка сообщений в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Бот отправил сообщение')
    except telegram.TelegramError as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(current_timestamp):
    """Отправка запроса к API Практикума."""
    payload = {'from_date': current_timestamp}
    try:
        responce = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.exceptions.RequestException:
        raise ResponseError('Эндпоинт Практикума недоступен')
    if responce.status_code != HTTPStatus.OK:
        raise ResponseError('Сбой при запросе к эндпоинту Практикума')
    return responce.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(f'Тип ответа API Практикума: {type(response)}')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Ответ API под ключом "homeworks" не является списком')
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if (status := homework.get('status')) is None:
        raise ValueError('Отсутствует значение status')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError('Недокументированный статус домашней работы')
    if (homework_name := homework.get('homework_name')) is None:
        raise ValueError('Отсутствует значение homework_name')
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    last_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            message = parse_status(homework)
            if message != last_message:
                send_message(bot, message)
                last_message = message
            else:
                logging.debug('Изменений в статусе домашней работы нет')
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.critical(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
