import os
import requests
from aiogram import Bot
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

API_TOKEN = os.getenv('TOKEN_BOT')
bot = Bot(token=API_TOKEN)  # Використовуємо default для налаштувань

# Create your views here.
def mute_user_telegram(chat_id, user_id, mute_end_time):
    # Перевести timedelta в datetime
    if isinstance(mute_end_time, timedelta):
        mute_end_time = datetime.now() + mute_end_time

    url = f"https://api.telegram.org/bot{API_TOKEN}/restrictChatMember"

    # Параметри для обмеження доступу
    data = {
        'chat_id': chat_id,
        'user_id': user_id,
        'permissions': {
            'can_send_messages': False,  # Відключити відправку повідомлень
            'can_send_media_messages': False,
            'can_send_other_messages': False,
            'can_add_web_page_previews': False,
        },
        'until_date': int(mute_end_time.timestamp())  # Час до якого буде активний мут
    }

    # Відправляємо запит на Telegram API
    response = requests.post(url, json=data)


def ban_user_telegram(chat_id, user_id):
    url = f"https://api.telegram.org/bot{API_TOKEN}/banChatMember"

    # Відправляємо запит на бани користувача
    data = {
        'chat_id': chat_id,
        'user_id': user_id
    }

    # Відправка запиту до Telegram API
    response = requests.post(url, data=data)




def unban_user_telegram(chat_id, user_id):
    url = f"https://api.telegram.org/bot{API_TOKEN}/unbanChatMember"

    # Відправляємо запит на розбан користувача
    data = {
        'chat_id': chat_id,
        'user_id': user_id
    }

    # Відправка запиту до Telegram API
    response = requests.post(url, data=data)





def unmute_user_telegram(chat_id, user_id):
    url = f"https://api.telegram.org/bot{API_TOKEN}/restrictChatMember"

    # Відновлення доступу до чату (розмут)
    data = {
        'chat_id': chat_id,
        'user_id': user_id,
        'permissions': {
            'can_send_messages': True,  # Включити можливість відправки повідомлень
            'can_send_media_messages': True,
            'can_send_other_messages': True,
            'can_add_web_page_previews': True,
        }
    }

    # Відправка запиту до Telegram API
    response = requests.post(url, json=data)

