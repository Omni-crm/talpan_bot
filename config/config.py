import os
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning
filterwarnings(action="ignore", category=PTBUserWarning)
load_dotenv(override=True,)

@dataclass
class Links:
    ADMIN_CHAT: str
    ORDER_CHAT: str

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMINS = list(map(int, os.getenv("ADMINS").split(",")))
OPERATORS = list(map(int, os.getenv("OPERATORS").split(",")))
STOCKMEN = list(map(int, os.getenv("STOCKMEN").split(",")))
COURIERS = list(map(int, os.getenv("COURIERS").split(",")))

admin_chat = os.getenv('ADMIN_CHAT')
order_chat = os.getenv('ORDER_CHAT')
links = Links(admin_chat, order_chat,)


print(f"Админы: {ADMINS}")
print(f"Операторы: {OPERATORS}")
print(f"Кладовщики: {STOCKMEN}")
print(f"Курьеры: {COURIERS}")
