import os
from enum import Enum
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram import Update
from functools import wraps
from config.config import *
from config.translations import t, get_user_lang
import datetime, json, io

# Import Supabase client
from .supabase_client import get_supabase_client

# Initialize Supabase client only
db_client = get_supabase_client()
print("✅ Using Supabase database")


def dump_db(format: str):
    """
    Export database to file using Supabase only
    """
    try:
        import pandas as pd
        from io import BytesIO
        
        # List of tables to export
        tables = ['users', 'products', 'orders', 'shifts', 'tgsessions', 'templates']
        output = BytesIO()

        if format == "xlsx":
            filename = f'dump_db_{datetime.datetime.now().strftime("%d_%m_%Y")}.xlsx'
            output.name = filename

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for table_name in tables:
                    try:
                        data = db_client.select(table_name)
                        if data:
                            df = pd.DataFrame(data)
                            df.to_excel(writer, sheet_name=table_name, index=False)
                        else:
                            print(f"Table '{table_name}' is empty and will not be added to Excel.")
                    except Exception as e:
                        print(f"Error exporting table '{table_name}': {e}")

            output.seek(0)
            return output
        else:
            filename = f'dump_db_{datetime.datetime.now().strftime("%d_%m_%Y")}.json'
            output.name = filename

            all_data = {}

            for table_name in tables:
                try:
                    data = db_client.select(table_name)
                    if data:
                        all_data[table_name] = data
                    else:
                        print(f"Table '{table_name}' is empty and will not be added to JSON.")
                except Exception as e:
                    print(f"Error exporting table '{table_name}': {e}")

            # Save data to JSON in byte stream
            json_data = json.dumps(all_data, ensure_ascii=False, indent=4, default=str)
            output.write(json_data.encode('utf-8'))
            output.seek(0)

            return output
    except Exception as e:
        print(f"Error in dump_db: {e}")
        return None


class Status(Enum):
    active = "🟡 Активен / פעיל"
    completed = "✅ Завершён / הושלם"
    cancelled = "❌ Отменён / בוטל"
    pending = "⌛️ Ожидает курьера / ממתין לשליח"
    delay = "⏲️ Задержка /מתעכב"


class ShiftStatus(Enum):
    opened = "Открыта / פתוחה"
    closed = "Закрыта / סגורה"


class Role(Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    STOCKMAN = "stockman"
    RUNNER = "courier"
    GUEST = "guest"
# Note: Models are now managed in Supabase, these classes are kept for type hints only
class User:
    """User model - Supabase managed"""
    pass

class Product:
    """Product model - Supabase managed"""
    pass

class Template:
    """Template model - Supabase managed"""
    pass

class TgSession:
    """TgSession model - Supabase managed"""
    @staticmethod
    def get_api_id():
        import os
        return os.getenv("API_ID")
    
    @staticmethod
    def get_api_hash():
        import os
        return os.getenv("API_HASH")

class Order:
    """Order model - Supabase managed"""
    pass

class Shift:
    """Shift model - Supabase managed"""
    @staticmethod
    def set_products():
        # Using Supabase only
        products = db_client.select('products')
        data = [{'id': product['id'], 'name': product['name'], 'stock': product['stock']} for product in products]
        return data

class BotSettings:
    """BotSettings model - Supabase managed"""
    pass

def get_bot_setting(key: str, default_value: str = "") -> str:
    """קבלת הגדרה מהמסד הנתונים - Supabase only"""
    try:
        results = db_client.select('bot_settings', {'key': key})
        if results:
            return results[0].get('value', default_value)
        return default_value
    except Exception as e:
        # If table doesn't exist yet, return default value
        return default_value

def get_bot_setting_list(key: str) -> list:
    """קבלת רשימה מהמסד נתונים"""
    value = get_bot_setting(key)
    if value:
        try:
            return json.loads(value)
        except:
            return value.split(',') if ',' in value else [value]
    return []

def set_bot_setting(key: str, value: str, user_id: int = None, value_type: str = 'string', description: str = None) -> None:
    """עדכון הגדרה במסד הנתונים - Supabase only"""
    try:
        # Check if setting exists
        results = db_client.select('bot_settings', {'key': key})
        
        if results:
            # Update existing setting
            db_client.update('bot_settings', {
                'value': value,
                'value_type': value_type,
                'updated_at': datetime.datetime.now().isoformat(),
                'updated_by': user_id,
                'description': description or results[0].get('description', '')
            }, {'key': key})
        else:
            # Create new setting
            db_client.insert('bot_settings', {
                'key': key,
                'value': value,
                'value_type': value_type,
                'description': description or '',
                'updated_by': user_id,
                'updated_at': datetime.datetime.now().isoformat()
            })
    except Exception as e:
        # If table doesn't exist yet, ignore the error
        # The table will be created in bot.py
        print(f"Error setting bot_setting: {e}")

def set_bot_setting_list(key: str, value_list: list, user_id: int = None, description: str = None) -> None:
    """שמירת רשימה במסד הנתונים"""
    set_bot_setting(key, json.dumps(value_list), user_id, 'list', description)

def initialize_default_settings():
    """אתחול הגדרות ברירת מחדל"""
    # הגדרות קבוצות
    if not get_bot_setting('admin_chat'):
        set_bot_setting('admin_chat', '', description='קבוצת מנהלים')
    if not get_bot_setting('order_chat'):
        set_bot_setting('order_chat', '', description='קבוצת שליחים')
    
    # הגדרות משתמשים
    if not get_bot_setting('admins'):
        set_bot_setting_list('admins', [], description='רשימת מנהלים')
    if not get_bot_setting('operators'):
        set_bot_setting_list('operators', [], description='רשימת מפעילים')
    if not get_bot_setting('stockmen'):
        set_bot_setting_list('stockmen', [], description='רשימת מחסנאים')
    if not get_bot_setting('couriers'):
        set_bot_setting_list('couriers', [], description='רשימת שליחים')
    
    # הגדרות API
    if not get_bot_setting('bot_token'):
        set_bot_setting('bot_token', '', description='טוקן הבוט')
    if not get_bot_setting('api_id'):
        set_bot_setting('api_id', '', description='API ID')
    if not get_bot_setting('api_hash'):
        set_bot_setting('api_hash', '', description='API Hash')
    
    # הגדרות מסד נתונים
    if not get_bot_setting('db_name'):
        set_bot_setting('db_name', 'database.db', description='שם מסד הנתונים')
    if not get_bot_setting('db_dir'):
        set_bot_setting('db_dir', '/data', description='תיקיית מסד הנתונים')

async def resolve_username_to_id(username: str, bot_token: str = None) -> str:
    """המרת username ל-ID"""
    try:
        from telegram import Bot
        from config.config import links
        
        # קבלת טוקן
        if not bot_token:
            bot_token = get_bot_setting('bot_token') or links.BOT_TOKEN
        
        if not bot_token:
            return username  # אם אין טוקן, החזר את ה-username
        
        bot = Bot(token=bot_token)
        
        # הסרת @ אם קיים
        clean_username = username.replace('@', '')
        
        # ניסיון לקבל מידע על המשתמש
        try:
            # ניסיון לקבל chat info
            chat = await bot.get_chat(f"@{clean_username}")
            return str(chat.id)
        except:
            # אם זה לא עבד, ננסה לחפש במשתמשים
            try:
                # זה לא יעבוד עם username, אבל ננסה בכל זאת
                return username
            except:
                return username
                
    except Exception as e:
        print(f"Error resolving username {username}: {e}")
        return username

async def resolve_chat_identifier(identifier: str, bot_token: str = None) -> str:
    """פתרון מזהה קבוצה/משתמש - מחזיר ID"""
    try:
        from telegram import Bot
        from config.config import links
        
        # קבלת טוקן
        if not bot_token:
            bot_token = get_bot_setting('bot_token') or links.BOT_TOKEN
        
        if not bot_token:
            return identifier
        
        bot = Bot(token=bot_token)
        
        # אם זה כבר ID (מספר)
        if identifier.isdigit() or (identifier.startswith('-') and identifier[1:].isdigit()):
            return identifier
        
        # אם זה username
        if identifier.startswith('@'):
            clean_username = identifier.replace('@', '')
            try:
                chat = await bot.get_chat(f"@{clean_username}")
                return str(chat.id)
            except:
                return identifier
        
        # אם זה invite link
        if 't.me/' in identifier:
            try:
                chat = await bot.get_chat(identifier)
                return str(chat.id)
            except:
                return identifier
        
        # אם זה username רגיל
        try:
            chat = await bot.get_chat(f"@{identifier}")
            return str(chat.id)
        except:
            return identifier
            
    except Exception as e:
        print(f"Error resolving chat identifier {identifier}: {e}")
        return identifier


def is_admin(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        msg = update.effective_message
        
        print(f"🔧 is_admin decorator called for user {user.id}")
        
        # Check user role - Supabase only
        results = db_client.select('users', {'user_id': user.id, 'role': 'admin'})
        is_admin_role = len(results) > 0
        
        print(f"🔧 Is admin role: {is_admin_role}")
        
        if not is_admin_role:
            print(f"❌ Access denied - not admin")
            lang = get_user_lang(user.id)
            await msg.reply_text(t("admin_only", lang))
            return

        print(f"✅ Access granted - executing admin function")
        await func(update, context, *args, **kwargs)

    return wrapper


def is_operator(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        msg = update.effective_message
        
        print(f"🔧 is_operator decorator called for user {user.id}")
        
        # Check user role - Supabase only
        results = db_client.select('users', {'user_id': user.id})
        user_data = results[0] if results else None
        is_operator_role = user_data and user_data['role'] in ['operator', 'admin']
        
        print(f"🔧 User role check: {user_data['role'] if user_data else 'None'}")
        print(f"🔧 Is operator role: {is_operator_role}")
        
        if not is_operator_role:
            print(f"❌ Access denied - not operator")
            lang = get_user_lang(user.id)
            await msg.reply_text(t("operator_only", lang))
            return

        print(f"✅ Access granted - executing function")
        await func(update, context, *args, **kwargs)

    return wrapper


def is_stockman(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        msg = update.effective_message
        
        # Check user role - Supabase only
        results = db_client.select('users', {'user_id': user.id})
        user_data = results[0] if results else None
        is_stockman_role = user_data and user_data['role'] in ['stockman', 'admin']
        
        if not is_stockman_role:
            lang = get_user_lang(user.id)
            await msg.reply_text(t("stockman_only", lang))
            return

        await func(update, context, *args, **kwargs)

    return wrapper


def is_courier(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        msg = update.effective_message
        
        # Check user role - Supabase only
        results = db_client.select('users', {'user_id': user.id})
        user_data = results[0] if results else None
        is_courier_role = user_data and user_data['role'] in ['courier', 'admin']
        
        if not is_courier_role:
            lang = get_user_lang(user.id)
            await msg.reply_text(t("courier_only", lang))
            return

        await func(update, context, *args, **kwargs)

    return wrapper


def is_user_in_db(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes, *args, **kwargs):
        from config.translations import t
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        user = update.effective_user
        msg = update.effective_message
        
        try:
            # Check if user exists in database - Supabase only
            results = db_client.select('users', {'user_id': user.id})
            user_db = results[0] if results else None
            
            if not user_db:
                # משתמש חדש - צריך ליצור אותו
                # קודם נשאל אותו איזו שפה הוא מעדיף
                
                # Determine role
                role = Role.GUEST
                if user.id in ADMINS:
                    role = Role.ADMIN
                elif user.id in OPERATORS:
                    role = Role.OPERATOR
                elif user.id in STOCKMEN:
                    role = Role.STOCKMAN
                elif user.id in COURIERS:
                    role = Role.RUNNER
                
                # Create user in database
                user_data = {
                    'user_id': user.id,
                    'firstname': user.first_name,
                    'lastname': user.last_name,
                    'username': user.username,
                    'lang': 'ru',  # ברירת מחדל, ישתנה אחרי בחירה
                    'role': role.value
                }
                
                # Using Supabase only
                db_client.insert('users', user_data)
                
                print(f"New user created: {user}")
                
                # הצגת בחירת שפה למשתמשים חדשים (לא אורחים)
                if role != Role.GUEST:
                    keyboard = [
                        [
                            InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru"),
                            InlineKeyboardButton("🇮🇱 עברית", callback_data="set_lang_he")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # שליחת הודעת תפקיד לפי שפת המשתמש
                    user_lang = get_user_lang(user.id)
                    
                    # אם המשתמש עדיין לא בחר שפה, נשלח הודעה דו-לשונית
                    if user_lang == "ru":  # ברירת מחדל
                        if role == Role.ADMIN:
                            await msg.reply_text("Вам присвоена роль - <b>Администратор.</b>\n\nYou have been assigned the role - <b>Administrator.</b>", parse_mode=ParseMode.HTML)
                        elif role == Role.OPERATOR:
                            await msg.reply_text("Вам присвоена роль - <b>Оператор.</b>\n\nYou have been assigned the role - <b>Operator.</b>", parse_mode=ParseMode.HTML)
                        elif role == Role.STOCKMAN:
                            await msg.reply_text("Вам присвоена роль - <b>Кладовщик.</b>\n\nYou have been assigned the role - <b>Stockman.</b>", parse_mode=ParseMode.HTML)
                        elif role == Role.RUNNER:
                            await msg.reply_text("Вам присвоена роль - <b>Курьер.</b>\n\nYou have been assigned the role - <b>Courier.</b>", parse_mode=ParseMode.HTML)
                    else:
                        # אם המשתמש כבר בחר שפה
                        if role == Role.ADMIN:
                            await msg.reply_text(t("role_assigned_admin", user_lang), parse_mode=ParseMode.HTML)
                        elif role == Role.OPERATOR:
                            await msg.reply_text(t("role_assigned_operator", user_lang), parse_mode=ParseMode.HTML)
                        elif role == Role.STOCKMAN:
                            await msg.reply_text(t("role_assigned_stockman", user_lang), parse_mode=ParseMode.HTML)
                        elif role == Role.RUNNER:
                            await msg.reply_text(t("role_assigned_courier", user_lang), parse_mode=ParseMode.HTML)
                    
                    await msg.reply_text(
                        "בחר שפה / Выберите язык:",
                        reply_markup=reply_markup
                    )
                    # נחכה לבחירת השפה לפני שנמשיך
                    # הפונקציה set_language תטפל בהמשך
                    return
                else:
                    # אורחים - הודעת ברוכים הבאים
                    await msg.reply_text(t("guest_welcome", "ru"))
                    return
                    
            else:
                # משתמש קיים
                # Convert user_db dict to object-like for compatibility
                if isinstance(user_db, dict):
                    user_role = Role(user_db.get('role'))
                    user_lang = user_db.get('lang', 'ru')
                else:
                    user_role = user_db.role
                    user_lang = user_db.lang
                
                if user_role == Role.GUEST:
                    await msg.reply_text(t("guest_welcome", user_lang or "ru"))
                    return

            await func(update, context, *args, **kwargs)
            
        finally:
            pass

    return wrapper

def if_table():
    """Creates all tables if not existed yet - Supabase only (tables managed in Supabase dashboard)."""
    print("✅ Supabase - tables managed in cloud")

# Helper functions for Supabase migration

def get_user_by_id(user_id: int):
    """Get user by ID - Supabase only"""
    results = db_client.select('users', {'user_id': user_id})
    if results:
        return results[0]
    return None

def get_product_by_id(product_id: int):
    """Get product by ID - Supabase only"""
    results = db_client.select('products', {'id': product_id})
    if results:
        return results[0]
    return None

def get_all_products():
    """Get all products - Supabase only"""
    return db_client.select('products')

def create_shift(shift_data: dict):
    """Create a new shift - Supabase only"""
    result = db_client.insert('shifts', shift_data)
    return result

def get_opened_shift():
    """Get the currently opened shift - Supabase only"""
    all_shifts = db_client.select('shifts')  # Get all shifts
    # Sort by id descending to get most recent first
    all_shifts.sort(key=lambda x: x.get('id', 0), reverse=True)
    print(f"🔧 get_opened_shift: Checking {len(all_shifts)} shifts")
    
    for shift in all_shifts:
        status = shift.get('status', '')
        shift_id = shift.get('id', 'unknown')
        print(f"🔧 get_opened_shift: Shift ID={shift_id}, Status='{status}'")
        
        # Check for opened status (Hebrew, Russian, or English)
        is_opened = (
            status == 'opened' or 
            status == 'Открыта / פתוחה' or
            ('פתוח' in status and 'closed' not in status.lower()) or 
            ('Открыта' in status and 'closed' not in status.lower())
        )
        
        # Double check it's not closed
        is_closed = (
            status == 'closed' or 
            'closed' in status.lower() or 
            'закрыт' in status.lower() or
            'סגור' in status
        )
        
        if is_opened and not is_closed:
            print(f"🔧 get_opened_shift: Found opened shift ID={shift_id}, Status='{status}'")
            return shift  # Return first (most recent) opened shift
    
    print(f"🔧 get_opened_shift: No opened shift found")
    return None

def update_shift(shift_id: int, updates: dict):
    """Update a shift - Supabase only"""
    db_client.update('shifts', updates, {'id': shift_id})

def get_orders_by_filter(filters: dict, sort_by: str = None):
    """Get orders by filter - Supabase only"""
    # Get all orders and filter in Python
    all_orders = db_client.select('orders')
    filtered = all_orders
    
    if filters:
        for key, value in filters.items():
            if key == 'created' and isinstance(value, dict):
                # Handle date ranges
                if '>=' in value:
                    filtered = [o for o in filtered if o.get('created') and o['created'] >= str(value['>='])]
                if '<=' in value:
                    filtered = [o for o in filtered if o.get('created') and o['created'] <= str(value['<='])]
            else:
                filtered = [o for o in filtered if o.get(key) == value]
    
    if sort_by:
        filtered = sorted(filtered, key=lambda x: x.get(sort_by))
    
    # Convert to objects
    return [type('Order', (), order)() for order in filtered]

def get_all_orders():
    """Get all orders - Supabase only"""
    return db_client.select('orders')