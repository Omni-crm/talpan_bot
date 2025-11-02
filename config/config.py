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

# =========================================
# 🔒 RAILWAY ENV ONLY (קבוע - לא משתנה)
# =========================================
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
API_ID = os.getenv('API_ID', '')
API_HASH = os.getenv('API_HASH', '')

# רשימת מנהלים ראשית - מ-ENV (קבועה)
try:
    ADMINS = list(map(int, os.getenv("ADMINS", "").split(","))) if os.getenv("ADMINS") else []
except:
    ADMINS = []

# =========================================
# 💾 DATABASE ONLY (דינמי - ניתן לשינוי)
# =========================================
# אלה יטענו מהדאטהבייס בזמן ריצה, לא מ-ENV!
# - order_chat (קבוצת שליחים)
# - admin_chat (קבוצת מנהלים)
# - operators (רשימת מפעילים)
# - stockmen (רשימת מחסנאים)  
# - couriers (רשימת שליחים)

# הגדרות בסיסיות לתאימות לאחור (deprecated - use get_bot_setting instead)
admin_chat = ""  # יטען מהדאטהבייס
order_chat = ""  # יטען מהדאטהבייס
admins_list = ADMINS  # מ-ENV בלבד
operators_list = []  # יטען מהדאטהבייס
stockmen_list = []  # יטען מהדאטהבייס
couriers_list = []  # יטען מהדאטהבייס

# יצירת object links (ריק - יטען מהדאטהבייס)
links = Links(admin_chat, order_chat, BOT_TOKEN, API_ID, API_HASH)

print(f"🔒 Admins from ENV: {admins_list}")
print(f"💾 Other settings will load from Supabase database...")
