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
    BOT_TOKEN: str
    API_ID: str
    API_HASH: str

# קבלת הגדרות מ-ENV
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
API_ID = os.getenv('API_ID', '')
API_HASH = os.getenv('API_HASH', '')
ADMIN_CHAT = os.getenv('ADMIN_CHAT', '')
ORDER_CHAT = os.getenv('ORDER_CHAT', '')

# קבלת רשימות משתמשים מ-ENV
try:
    ADMINS = list(map(int, os.getenv("ADMINS", "").split(","))) if os.getenv("ADMINS") else []
    OPERATORS = list(map(int, os.getenv("OPERATORS", "").split(","))) if os.getenv("OPERATORS") else []
    STOCKMEN = list(map(int, os.getenv("STOCKMEN", "").split(","))) if os.getenv("STOCKMEN") else []
    COURIERS = list(map(int, os.getenv("COURIERS", "").split(","))) if os.getenv("COURIERS") else []
except:
    ADMINS = []
    OPERATORS = []
    STOCKMEN = []
    COURIERS = []

# הגדרות בסיסיות - ללא מסד נתונים
admin_chat = ADMIN_CHAT
order_chat = ORDER_CHAT
admins_list = ADMINS
operators_list = OPERATORS
stockmen_list = STOCKMEN
couriers_list = COURIERS

# יצירת object links
links = Links(admin_chat, order_chat, BOT_TOKEN, API_ID, API_HASH)

print(f"Admins: {admins_list}")
print(f"Operators: {operators_list}")
print(f"Stockmen: {stockmen_list}")
print(f"Couriers: {couriers_list}")
