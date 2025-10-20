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
                    print(f"Таблица '{table_name}' пуста и не будет добавлена в Excel.")

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
                print(f"Таблица '{table_name}' пуста и не будет добавлена в JSON.")

        # Сохранение данных в JSON в байтовый поток
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
    """Template messages using to send to clients.
    id = Column(Integer, primary_key=True)
    client_name = Column(String)
    client_username = Column(String)
    client_phone = Column(String)
    address = Column(String)
    products = Column(String)
    courier_name = Column(String)
    courier_username = Column(String)
    courier_id = Column(BigInteger)
    courier_minutes = Column(Integer)
    delay_reason = Column(String)
    delay_minutes = Column(Integer)
    created = Column(DateTime, default=datetime.datetime.now())
    delivered = Column(DateTime)
    status = Column(SqlEnum(Status), default=Status.pending,)
    """
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    client_name = Column(String)
    client_username = Column(String)
    client_phone = Column(String)
    address = Column(String)
    products = Column(String)
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
        self.products = json.dumps(data)  # Сериализация

    def get_products(self) -> list[dict]:
        return json.loads(self.products)  # Десериализация
    
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