from sqlalchemy import create_engine, inspect
import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, BigInteger, Boolean, UniqueConstraint, Integer, DateTime, Enum as SqlEnum
from enum import Enum
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram import Update
from functools import wraps
from config.config import *
import datetime, json, io
import pandas as pd

Base = declarative_base()

# Determine SQLite database location in a portable way.
# - Locally: defaults to ./database.db (or DB_NAME if provided)
# - Railway: recommend setting DB_DIR=/data via railway.toml to persist on a volume
# You can also override with DB_PATH to point directly to a file.
db_path_env = os.getenv("DB_PATH")
if db_path_env:
    sqlite_path = db_path_env
else:
    db_dir = os.getenv("DB_DIR", ".")
    db_name = os.getenv("DB_NAME", "database.db")
    sqlite_path = os.path.join(db_dir, db_name)

engine = create_engine(f"sqlite:///{sqlite_path}")
Session = sessionmaker()
Session.configure(bind=engine)


def dump_db(format: str):
    global engine

    insp = inspect(engine)
    tables = insp.get_table_names()
    output = io.BytesIO()

    if format == "xlsx":
        filename = f'dump_db_{datetime.datetime.now().strftime("%d_%m_%Y")}.xlsx'
        output.name = filename

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for table_name in tables:
                df = pd.read_sql_table(table_name, con=engine)

                if not df.empty:
                    df.to_excel(writer, sheet_name=table_name, index=False)
                else:
                    print(f"Table '{table_name}' is empty and will not be added to Excel.")

        output.seek(0)

        return output
    else:
        filename = f'dump_db_{datetime.datetime.now().strftime("%d_%m_%Y")}.json'
        output.name = filename

        all_data = {}

        for table_name in tables:
            df = pd.read_sql_table(table_name, con=engine)

            if not df.empty:
                for column in df.select_dtypes(include=['datetime64[ns]']).columns:
                    df[column] = df[column].dt.strftime('%Y-%m-%d %H:%M:%S')

                all_data[table_name] = df.to_dict(orient='records')
            else:
                print(f"Table '{table_name}' is empty and will not be added to JSON.")

        # Save data to JSON in byte stream
        json_data = json.dumps(all_data, ensure_ascii=False, indent=4)
        output.write(json_data.encode('utf-8'))
        output.seek(0)

        return output


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


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    firstname = Column(String)
    lastname = Column(String)
    username = Column(String)
    lang = Column(String, default='ru')
    role = Column(SqlEnum(Role), default=Role.GUEST,)


class Product(Base):
    """Products listed in db."""
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    name = Column(String(22))
    stock = Column(Integer, default=0)
    crude = Column(Integer, default=0)
    price = Column(Integer, default=0)  # מחיר המוצר


class Template(Base):
    """Template messages using to send to clients."""
    __tablename__ = 'templates'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    text = Column(String)


class TgSession(Base):
    """Template messages using to send to clients."""
    __tablename__ = 'tgsessions'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    username = Column(String)
    api_id = Column(BigInteger, default=11858687)
    api_hash = Column(String, default="c0bf09e63e57259cc0bd793727ec448b")
    string = Column(String, nullable=False)
    owner_id = Column(BigInteger)
    is_worker = Column(Boolean, default=False)

    @staticmethod
    def get_api_id():
        return TgSession.api_id.default.arg

    @staticmethod
    def get_api_hash():
        return TgSession.api_hash.default.arg


class Order(Base):
    """Orders in the system."""
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    client_name = Column(String)
    client_username = Column(String)
    client_phone = Column(String)
    address = Column(String)
    products = Column(String)  # JSON with total_price instead of price
    total_order_price = Column(Integer, default=0)  # מחיר כולל להזמנה
    courier_name = Column(String)
    courier_username = Column(String)
    courier_id = Column(BigInteger)
    courier_minutes = Column(Integer)
    delay_reason = Column(String)
    delay_minutes = Column(Integer)
    created = Column(DateTime, default=datetime.datetime.now())
    delivered = Column(DateTime)
    status = Column(SqlEnum(Status), default=Status.pending,)

    def set_products(self, data):
        self.products = json.dumps(data)  # Serialization

    def get_products(self) -> list[dict]:
        return json.loads(self.products)  # Deserialization
    
    def calculate_total_price(self) -> int:
        """חישוב מחיר כולל של ההזמנה"""
        products = self.get_products()
        return sum([product.get('total_price', 0) for product in products])
    
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Shift(Base):
    __tablename__ = 'shifts'

    id = Column(Integer, primary_key=True)
    products_start = Column(String, default=lambda: json.dumps(Shift.set_products()))
    summary = Column(String)
    products_end = Column(String)
    operator_id = Column(BigInteger)
    operator_username = Column(BigInteger)
    status = Column(SqlEnum(ShiftStatus), default=ShiftStatus.opened,)
    opened_time = Column(DateTime, default=datetime.datetime.now())
    closed_time = Column(DateTime)

    operator_paid = Column(Integer)
    runner_paid = Column(Integer)
    petrol_paid = Column(Integer)
    products_fetched_text = Column(String)

    brutto = Column(Integer)
    netto = Column(Integer)

    operator_close_id = Column(BigInteger)
    operator_close_username = Column(BigInteger)

    @staticmethod
    def set_products():
        session = Session()
        products = session.query(Product).all()
        data = [{'id': product.id, 'name': product.name, 'stock': product.stock} for product in products]
        session.close()

        return data

    def get_products(self) -> list[dict]:
        return json.loads(self.products_start)

    def get_summary(self) -> list[dict]:
        return json.loads(self.summary)


class BotSettings(Base):
    """הגדרות הבוט - קבוצות, משתמשים וכו'"""
    __tablename__ = 'bot_settings'

    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)  # 'admin_chat', 'order_chat', 'bot_token', etc.
    value = Column(String(500), nullable=False)  # ערך ההגדרה
    value_type = Column(String(20), default='string')  # 'string', 'int', 'list', 'json'
    description = Column(String(200))  # תיאור ההגדרה
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    updated_by = Column(BigInteger)  # user_id של מי שעדכן

def get_bot_setting(key: str, default_value: str = "") -> str:
    """קבלת הגדרה מהמסד הנתונים"""
    try:
        session = Session()
        setting = session.query(BotSettings).filter(BotSettings.key == key).first()
        session.close()
        return setting.value if setting else default_value
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
    """עדכון הגדרה במסד הנתונים"""
    try:
        session = Session()
        setting = session.query(BotSettings).filter(BotSettings.key == key).first()
        
        if setting:
            setting.value = value
            setting.value_type = value_type
            setting.updated_at = datetime.datetime.now()
            setting.updated_by = user_id
            if description:
                setting.description = description
        else:
            setting = BotSettings(
                key=key, 
                value=value, 
                value_type=value_type,
                description=description,
                updated_by=user_id
            )
            session.add(setting)
        
        session.commit()
        session.close()
    except Exception as e:
        # If table doesn't exist yet, ignore the error
        # The table will be created in bot.py
        pass

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
        from config.translations import t, get_user_lang
        session = Session()
        user = update.effective_user
        msg = update.effective_message
        q = session.query(User).filter(User.user_id==user.id, User.role==Role.ADMIN)
        if not session.query(q.exists()).scalar():
            lang = get_user_lang(user.id)
            await msg.reply_text(t("admin_only", lang))
            return
        
        session.close()

        await func(update, context, *args, **kwargs)

    return wrapper


def is_operator(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from config.translations import t, get_user_lang
        session = Session()
        user = update.effective_user
        msg = update.effective_message
        q = session.query(User).filter(
            User.user_id == user.id,
            User.role.in_([Role.OPERATOR, Role.ADMIN])
        )
        if not session.query(q.exists()).scalar():
            lang = get_user_lang(user.id)
            await msg.reply_text(t("operator_only", lang))
            return

        session.close()

        await func(update, context, *args, **kwargs)

    return wrapper


def is_stockman(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from config.translations import t, get_user_lang
        session = Session()
        user = update.effective_user
        msg = update.effective_message
        q = session.query(User).filter(
            User.user_id == user.id,
            User.role.in_([Role.STOCKMAN, Role.ADMIN])
        )
        if not session.query(q.exists()).scalar():
            lang = get_user_lang(user.id)
            await msg.reply_text(t("stockman_only", lang))
            return

        session.close()

        await func(update, context, *args, **kwargs)

    return wrapper


def is_courier(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from config.translations import t, get_user_lang
        session = Session()
        user = update.effective_user
        msg = update.effective_message
        q = session.query(User).filter(
            User.user_id == user.id,
            User.role.in_([Role.RUNNER, Role.ADMIN])
        )
        if not session.query(q.exists()).scalar():
            lang = get_user_lang(user.id)
            await msg.reply_text(t("courier_only", lang))
            return

        session.close()

        await func(update, context, *args, **kwargs)

    return wrapper


def is_user_in_db(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes, *args, **kwargs):
        from config.translations import t
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        user = update.effective_user
        msg = update.effective_message
        session = Session()
        
        try:
            q = session.query(User).filter(User.user_id==user.id)
            user_db = q.first()
            
            if not user_db:
                # משתמש חדש - צריך ליצור אותו
                # קודם נשאל אותו איזו שפה הוא מעדיף
                new_user_db = User(
                    firstname=user.first_name,
                    lastname=user.last_name,
                    username=user.username,
                    user_id=user.id,
                    lang='ru',  # ברירת מחדל, ישתנה אחרי בחירה
                )

                if user.id in ADMINS:
                    new_user_db.role = Role.ADMIN
                elif user.id in OPERATORS:
                    new_user_db.role = Role.OPERATOR
                elif user.id in STOCKMEN:
                    new_user_db.role = Role.STOCKMAN
                elif user.id in COURIERS:
                    new_user_db.role = Role.RUNNER

                session.add(new_user_db)
                session.commit()
                print(f"New user created: {user}")
                
                # הצגת בחירת שפה למשתמשים חדשים (לא אורחים)
                if new_user_db.role != Role.GUEST:
                    keyboard = [
                        [
                            InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru"),
                            InlineKeyboardButton("🇮🇱 עברית", callback_data="set_lang_he")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # שליחת הודעת תפקיד קודם (ברוסית בברירת מחדל)
                    if new_user_db.role == Role.ADMIN:
                        await msg.reply_text(t("role_assigned_admin", "ru"), parse_mode=ParseMode.HTML)
                    elif new_user_db.role == Role.OPERATOR:
                        await msg.reply_text(t("role_assigned_operator", "ru"), parse_mode=ParseMode.HTML)
                    elif new_user_db.role == Role.STOCKMAN:
                        await msg.reply_text(t("role_assigned_stockman", "ru"), parse_mode=ParseMode.HTML)
                    elif new_user_db.role == Role.RUNNER:
                        await msg.reply_text(t("role_assigned_courier", "ru"), parse_mode=ParseMode.HTML)
                    
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
                    
            else:
                # משתמש קיים
                if user_db.role == Role.GUEST:
                    await msg.reply_text(t("guest_welcome", user_db.lang or "ru"))
                    return

            await func(update, context, *args, **kwargs)
            
        finally:
            session.close()

    return wrapper

def if_table():
    """Creates all tables if not existed yet."""
    Base.metadata.create_all(engine)