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

# אתחול הגדרות במסד נתונים
try:
    from db.db import initialize_default_settings, get_bot_setting, set_bot_setting, set_bot_setting_list
    
    # אתחול הגדרות ברירת מחדל
    initialize_default_settings()
    
    # העברת הגדרות מ-ENV למסד נתונים
    if BOT_TOKEN and not get_bot_setting('bot_token'):
        set_bot_setting('bot_token', BOT_TOKEN, description='טוקן הבוט')
    if API_ID and not get_bot_setting('api_id'):
        set_bot_setting('api_id', API_ID, description='API ID')
    if API_HASH and not get_bot_setting('api_hash'):
        set_bot_setting('api_hash', API_HASH, description='API Hash')
    if ADMIN_CHAT and not get_bot_setting('admin_chat'):
        set_bot_setting('admin_chat', ADMIN_CHAT, description='קבוצת מנהלים')
    if ORDER_CHAT and not get_bot_setting('order_chat'):
        set_bot_setting('order_chat', ORDER_CHAT, description='קבוצת שליחים')
    
    # העברת רשימות משתמשים למסד נתונים
    if ADMINS and not get_bot_setting('admins'):
        set_bot_setting_list('admins', ADMINS, description='רשימת מנהלים')
    if OPERATORS and not get_bot_setting('operators'):
        set_bot_setting_list('operators', OPERATORS, description='רשימת מפעילים')
    if STOCKMEN and not get_bot_setting('stockmen'):
        set_bot_setting_list('stockmen', STOCKMEN, description='רשימת מחסנאים')
    if COURIERS and not get_bot_setting('couriers'):
        set_bot_setting_list('couriers', COURIERS, description='רשימת שליחים')
        
except Exception as e:
    print(f"Error initializing database settings: {e}")

# קבלת הגדרות ממסד הנתונים
try:
    from db.db import get_bot_setting, get_bot_setting_list
    
    # קבלת קבוצות
    admin_chat = get_bot_setting('admin_chat') or ADMIN_CHAT
    order_chat = get_bot_setting('order_chat') or ORDER_CHAT
    
    # קבלת רשימות משתמשים
    admins_list = get_bot_setting_list('admins') or ADMINS
    operators_list = get_bot_setting_list('operators') or OPERATORS
    stockmen_list = get_bot_setting_list('stockmen') or STOCKMEN
    couriers_list = get_bot_setting_list('couriers') or COURIERS
    
    links = Links(admin_chat, order_chat, BOT_TOKEN, API_ID, API_HASH)
    
    print(f"Admins: {admins_list}")
    print(f"Operators: {operators_list}")
    print(f"Stockmen: {stockmen_list}")
    print(f"Couriers: {couriers_list}")
    
except Exception as e:
    print(f"Error loading settings from database: {e}")
    links = Links(ADMIN_CHAT, ORDER_CHAT, BOT_TOKEN, API_ID, API_HASH)
    
    print(f"Admins: {ADMINS}")
    print(f"Operators: {OPERATORS}")
    print(f"Stockmen: {STOCKMEN}")
    print(f"Couriers: {COURIERS}")
