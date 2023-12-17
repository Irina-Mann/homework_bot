import logging
import os
import requests
import sys
import telegram
import time

from dotenv import load_dotenv

from exceptions import ResponceError, TokenNoneError

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
    handlers=logging.StreamHandler(sys.stdout)
)


def check_tokens():
    '''Проверка наличия переменных окружения'''
    params = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for param in params:
        if param is None:
            logging.critical(f'Переменная окружения {param} недоступна')
            raise TokenNoneError(f'Отсутствует {param}')
        return True



def send_message(bot, message):
    '''Отправка сообщений в Telegram чат'''
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Бот отправил сообщение: {message}')
    except telegram.TelegramError as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')



def get_api_answer(timestamp):
    '''Отправка запроса к API Практикума'''
    payload = {'from_date': timestamp}
    try:
        responce = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.exceptions.RequestException as request_error:
        error_msg = f'Эндпоинт Практикума недоступен: {request_error}'
        logging.error(error_msg)
        raise ResponceError(error_msg)
    if responce.status_code == 400:
        logging.error(f'Неверный параметр from_date')
        raise ResponceError()
    elif responce.status_code == 401:
        logging.error(f'Запрос содержал некорректный токен')
        raise ResponceError()
    elif responce.status_code != 200:
        logging.error(f'Сбой при запросе к эндпоинту Практикума')
        raise ResponceError()
    else:
        return responce.json()
    


def check_response(response):
    '''Проверка ответа API на соответствие документации'''
    if not isinstance(response, dict):
        logging.error('Данные ответа API Практикума не являются словарем')
        raise TypeError(f'Тип ответа API Практикума: {type(response)}')
    homeworks = response.get("homeworks")
    if not isinstance(homeworks, list):
        raise TypeError('Ответ API под ключом "homeworks" не является списком')
    homework = response.get("homeworks")[0]
    return homework


def parse_status(homework):
    '''Извлечение статуса домашней работы'''
    status = homework.get('status')
    if status is None:
        logging.error('Отсутствует значение "status"')
        raise ValueError()
    elif status not in HOMEWORK_VERDICTS:
        logging.error('Недокументированный статус домашней работы')
        raise ValueError()
    homework_name = homework.get("homework_name")
    if homework_name is None:
        logging.error('Отсутствует значение "homework_name"')
        raise ValueError()
    verdict = HOMEWORK_VERDICTS.get(status)    
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    for_now_status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if homework.get('status') != for_now_status:
                send_message(bot, message)
                for_now_status = homework.get('status')
            logging.debug('Изменений в статусе домашней работы нет')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.critical(message)
        time.sleep(RETRY_PERIOD)

if __name__ == '__main__':
    main()
