import datetime, traceback
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, Job, ExtBot
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from pyrogram import Client
from config.config import *
from config.kb import *
from config.translations import t, get_user_lang
from db.db import *
from funcs.utils import *

async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Language selection command."""
    user = update.effective_user
    
    # Create language selection keyboard
    keyboard = [
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru"),
            InlineKeyboardButton("🇮🇱 עברית", callback_data="set_lang_he")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Get current language for the message
    lang = get_user_lang(user.id)
    
    if update.message:
        await update.message.reply_text(
            t("choose_language", lang),
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            t("choose_language", lang),
            reply_markup=reply_markup
        )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language selection callback."""
    await update.callback_query.answer()
    
    lang_code = update.callback_query.data.replace("set_lang_", "")
    user = update.effective_user
    
    # Update user language in DB
    session = Session()
    try:
        user_db = session.query(User).filter(User.user_id == user.id).first()
        if user_db:
            user_db.lang = lang_code
            session.commit()
        
        # Send confirmation in new language
        await update.callback_query.message.edit_text(
            t("language_changed", lang_code)
        )
        
        # Show main menu in new language
        reply_markup = await build_start_menu(user.id)
        await update.callback_query.message.reply_text(
            text=t("main_menu", lang_code),
            reply_markup=reply_markup
        )
    finally:
        session.close()


@is_user_in_db
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Available features buttons."""
    user = update.effective_user
    lang = get_user_lang(user.id)

    if not context.user_data.get("msgs_to_delete"):
        context.user_data["msgs_to_delete"] = []
    else:
        msgs = context.user_data["msgs_to_delete"]

        for msg in msgs:
            try:
                await msg.delete()
            except:
                pass
    
    reply_markup = await build_start_menu(user.id)
    msg = await update.message.reply_text(
        text=t("main_menu", lang),
        reply_markup=reply_markup)

    context.user_data["msgs_to_delete"].append(msg)


@is_admin
async def dump_choose_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await update.effective_message.reply_text(t('choose_format', lang), reply_markup=get_db_format_kb(lang))


@is_admin
async def dump_database(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()

    format_file = update.callback_query.data

    try:
        file = dump_db(format_file)
        await update.effective_message.reply_document(document=file, filename=file.name)
    except Exception as e:
        await update.effective_message.reply_document(repr(e))

@is_admin
async def quick_reports(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await update.effective_message.reply_text(t('choose_report_param', lang), reply_markup=get_quick_reports_kb(lang),)


@is_admin
async def show_daily_profit_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """הצגת אפשרויות דוח רווח יומי."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    keyboard = [
        [InlineKeyboardButton(t("btn_today", lang), callback_data="profit_today")],
        [InlineKeyboardButton(t("btn_yesterday", lang), callback_data="profit_yesterday")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.reply_text(
        t("choose_period", lang),
        reply_markup=reply_markup
    )


@is_admin
async def daily_profit_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """הצגת דוח רווח יומי."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # קביעת התקופה לפי הכפתור שנלחץ
    date_option = update.callback_query.data.replace("profit_", "")  # 'today' או 'yesterday'
    
    try:
        report = await form_daily_profit_report(date_option, lang)
        await update.effective_message.reply_text(report, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.effective_message.reply_text(
            t("error", lang).format(repr(e)),
            parse_mode=ParseMode.HTML
        )


@is_admin
async def report_by_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()

    session = Session()
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    
    # Получаем результаты с группировкой по продуктам
    results = session.query(Order.products, func.count(Order.id)).filter(Order.delivered >= seven_days_ago).group_by(Order.products).all()

    report = "📦 Отчёт по товарам (последние 7 дней):\n\n"
    total_count = 0

    for product_data, count in results:
        products = json.loads(product_data)  # Десериализация JSON
        for product in products:
            product_name = product['name']
            product_quantity = product['quantity']
            report += f"{product_name} – {product_quantity * count} шт.\n"  # Умножаем на количество заказов
            total_count += product_quantity * count  # Считаем общее количество

    report += f"\nВсего: {total_count} ед."

    session.close()

    await update.effective_message.reply_text(text=report)


@is_admin
async def report_by_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()

    session = Session()
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    
    # Получаем результаты с группировкой по клиентам
    results = session.query(Order.client_name, Order.client_username, Order.client_phone, func.count(Order.id)).filter(Order.delivered >= seven_days_ago).group_by(Order.client_username).all()

    report = "👥 Отчёт по клиентам (последние 7 дней):\n\n"
    total_orders = 0

    for index, (client_name, client_username, client_phone, count) in enumerate(results, start=1):
        report += f"{index}. {client_name} {client_username} +{client_phone} – {count} заказов\n"
        total_orders += count  # Считаем общее количество заказов

    report += f"\nВсего: {total_orders} заказов."

    session.close()

    await update.effective_message.reply_text(text=report)


@is_admin
async def report_by_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()

    session = Session()
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    
    # Получаем все заказы, которые были доставлены за последние 7 дней
    results = session.query(Order).filter(Order.delivered >= seven_days_ago).all()

    order_prices = []

    # Подсчитываем общую стоимость для каждого заказа
    for order in results:
        products = json.loads(order.products)  # Десериализация JSON
        total_price = sum(product['price'] * product['quantity'] for product in products)
        order_prices.append((order.id, order.client_name, order.client_username, order.client_phone, order.delivered, total_price))

    # Сортируем заказы по общей стоимости и берем топ-15
    sorted_orders = sorted(order_prices, key=lambda x: x[2], reverse=True)[:15]

    report = "💰 Топ-15 заказов по цене (последние 7 дней):\n\n"
    
    for index, (order_id, client_name, client_username, client_phone, delivered, total) in enumerate(sorted_orders, start=1):
        report += f"{index}. Заказ #{order_id} {client_name} {client_username} +{client_phone} {delivered.strftime('%d.%m.%Y, %H:%M:%S')} - {total} ₪.\n"

    session.close()

    await update.effective_message.reply_text(text=report)

@is_admin
async def report_by_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()

    session = Session()
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)

    # Получаем все заказы, которые были доставлены за последние 7 дней
    results = session.query(Order).filter(Order.delivered >= seven_days_ago).all()

    weekday_count = {}

    weekdays_translation = {
        'Monday': 'Понедельник',
        'Tuesday': 'Вторник',
        'Wednesday': 'Среда',
        'Thursday': 'Четверг',
        'Friday': 'Пятница',
        'Saturday': 'Суббота',
        'Sunday': 'Воскресенье'
    }


    # Подсчитываем количество заказов по дням недели
    for order in results:
        if order.delivered:
            weekday = order.delivered.strftime('%A')  # Получаем день недели
            if weekday in weekday_count:
                weekday_count[weekday] += 1
            else:
                weekday_count[weekday] = 1

    # Сортируем дни недели по количеству заказов
    sorted_weekdays = sorted(weekday_count.items(), key=lambda x: x[1], reverse=True)

    report = "📈 Количество заказов по дням (последние 7 дней):\n\n"
    
    for index, (weekday, count) in enumerate(sorted_weekdays, start=1):
        report += f"{index}. {weekdays_translation[weekday]} - {count} заказов.\n"

    session.close()

    await update.effective_message.reply_text(text=report)

@is_admin
async def show_admin_action_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await update.effective_message.reply_text(t('admin_menu', lang), reply_markup=get_admin_action_kb(lang), parse_mode=ParseMode.HTML)

@is_operator
async def beginning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    session = Session()
    shift = session.query(Shift).filter(Shift.status==ShiftStatus.opened).first()

    if shift:
        shift_start_date = shift.opened_time.strftime("%d.%m.%Y, %H:%M:%S")
        await update.effective_message.edit_text(
            t('shift_not_closed', lang).format(shift_start_date), 
            reply_markup=get_shift_end_kb(lang), 
            parse_mode=ParseMode.HTML
        )
    else:
        products = Shift.set_products()
        prod_txt = " | ".join([f"{product['name']} {product['stock']}" for product in products])
        await update.effective_message.reply_text(
            t('available_stock', lang).format(prod_txt), 
            reply_markup=get_operator_shift_start_kb(lang), 
            parse_mode=ParseMode.HTML
        )

    session.close()


@is_operator
async def msg_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    reply_markup = await get_all_active_orders_to_msg_kb()

    if reply_markup:
        await update.effective_message.reply_text(t('choose_client_to_msg', lang), reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text(t('no_active_orders', lang))


@is_admin
async def manage_roles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await update.effective_message.reply_text(t('manage_roles_title', lang), reply_markup=get_manage_roles_kb(lang))

@is_admin
async def show_security_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await update.effective_message.reply_text(t('security_menu', lang), reply_markup=get_security_kb(lang))


async def all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await update.effective_message.edit_text(t("filter_by", lang), reply_markup=get_orders_filter_kb(lang))

async def filter_orders_by_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    "order:dd.mm.yyyy:dd.mm.yyyy"
    # Извлекаем даты из сообщения
    _, start_date_str, end_date_str = update.effective_message.text.split(':')
    
    # Преобразуем строки в объекты datetime
    start_date = datetime.datetime.strptime(start_date_str, '%d.%m.%Y')
    end_date = datetime.datetime.strptime(end_date_str, '%d.%m.%Y')

    
    # Убедимся, что end_date больше start_date
    if start_date > end_date:
        await update.message.reply_text("Ошибка: начальная дата не может быть больше конечной даты.")
        return

    session = Session()

    # Фильтруем заказы по дате
    orders = session.query(Order).filter(
        and_(
            Order.created >= start_date,
            Order.created <= end_date
        )
    ).all()

    if not orders:
        lang = get_user_lang(update.effective_user.id)
        not_found = "Не смогли найти заказов с такими датами" if lang == 'ru' else "לא נמצאו הזמנות בתאריכים אלה"
        await update.effective_message.reply_text(f"{not_found}: {start_date} - {end_date}")
        session.close()
        return

    lang = get_user_lang(update.effective_user.id)
    msg = t("total_found", lang).format(len(orders))
    context.user_data["orders_filtered"] = [order.to_dict() for order in orders]

    await update.effective_message.reply_text(msg, reply_markup=get_fetch_excel_kb(lang), parse_mode=ParseMode.HTML)
    await update.effective_message.delete()

    session.close()


async def filter_orders_by_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    "order$название_товара"
    product_names = update.effective_message.text.split('$')[1:]
    print(product_names)

    session = Session()
    # Пример запроса для проверки содержимого поля products
    orders = []
    all_orders = session.query(Order).all()
    for order in all_orders:
        products_names_db = [p.get('name') for p in order.get_products()]

        found = bool(set(products_names_db).intersection(product_names))

        if found:
            orders.append(order)

    if not orders:
        lang = get_user_lang(update.effective_user.id)
        not_found = "Не смогли найти заказов с такими товарами" if lang == 'ru' else "לא נמצאו הזמנות עם מוצרים אלה"
        await update.effective_message.reply_text(f"{not_found}: {product_names}")
        session.close()
        return

    lang = get_user_lang(update.effective_user.id)
    msg = t("total_found", lang).format(len(orders))
    context.user_data["orders_filtered"] = [order.to_dict() for order in orders]

    await update.effective_message.reply_text(msg, reply_markup=get_fetch_excel_kb(lang), parse_mode=ParseMode.HTML)
    await update.effective_message.delete()

    session.close()


async def fetch_orders_excel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    "Выгрузить Ексель с отфильтрованными заказами"
    await update.callback_query.answer()

    orders_data = context.user_data.get("orders_filtered")

    if not orders_data:
        await update.effective_message.reply_text("В памяти нет отфильтрованных заказов, запустите фильтр по новой.")
        return
    
    file_stream = dicts_to_xlsx(orders_data)

    await update.effective_message.reply_document(document=file_stream, filename='orders.xlsx')

async def filter_orders_by_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    "order@username | order@phone"
    identifier = update.effective_message.text.replace("order@", "")

    session = Session()

    if identifier.isdigit():
        orders = session.query(Order).filter(Order.client_phone==identifier).all()
    else:
        identifier = "@" + identifier
        orders = session.query(Order).filter(Order.client_username==identifier).all()

    if not orders:
        lang = get_user_lang(update.effective_user.id)
        not_found = "Не смогли найти заказов с таким параметром" if lang == 'ru' else "לא נמצאו הזמנות עם פרמטר זה"
        await update.effective_message.reply_text(f"{not_found}: {identifier}")
        session.close()
        return

    lang = get_user_lang(update.effective_user.id)
    msg = t("total_found", lang).format(len(orders))
    context.user_data["orders_filtered"] = [order.to_dict() for order in orders]

    await update.effective_message.reply_text(msg, reply_markup=get_fetch_excel_kb(lang), parse_mode=ParseMode.HTML)
    await update.effective_message.delete()

    session.close()


async def filter_orders_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    status_value = update.callback_query.data

    for status in (Status.completed,Status.active,Status.pending,Status.cancelled,Status.delay,):
        if status.value == status_value:
            break

    session = Session()

    orders = session.query(Order).filter(Order.status==status).all()

    if not orders:
        not_found = "Не смогли найти заказов с таким статусом" if lang == 'ru' else "לא נמצאו הזמנות עם סטטוס זה"
        await update.effective_message.reply_text(f"{not_found}: {status}")
        session.close()
        return

    msg = t("total_found", lang).format(len(orders))
    context.user_data["orders_filtered"] = [order.to_dict() for order in orders]

    await update.effective_message.reply_text(msg, reply_markup=get_fetch_excel_kb(lang), parse_mode=ParseMode.HTML)

    session.close()


@is_admin
async def manage_links_tip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    admin_group_link = ('@' + links.ADMIN_CHAT) if '@' not in links.ADMIN_CHAT else links.ADMIN_CHAT
    order_group_link = ('@' + links.ORDER_CHAT) if '@' not in links.ORDER_CHAT else links.ORDER_CHAT

    msg = t("current_links", lang).format(admin_group_link, order_group_link)
    
    await update.effective_message.reply_text(msg, reply_markup=get_change_links_kb(lang), parse_mode=ParseMode.HTML)


@is_admin
async def erase_orders_before_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        _, start_date_str = update.effective_message.text.split(':')
        
        # Преобразуем строки в объекты datetime
        date = datetime.datetime.strptime(start_date_str, '%d.%m.%Y')

        session = Session()
        orders_count = session.query(Order).filter(Order.created < date).delete()
        session.commit()
        session.close()
    except Exception as e:
        await update.effective_message.reply_text(f"Ошибка: {repr(e)}")
        await update.effective_message.delete()
        return

    await update.effective_message.reply_text(f"Успешно выполнено. Удалено {orders_count} заказов.")
    await update.effective_message.delete()


async def show_cleanup_tip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await update.effective_message.reply_text(
        """
<b>Чтобы очистить старые заказы, клиенты и тд старше определенной даты, напишите боту сообщение в таком формате -</b> <i>clean:dd.mm.yyyy</i>

<b>Пример:</b>
<pre>clean:06.05.2025</pre>

<i>
Все заказы старше этой даты будут удалены.
P.S.: Эта команда всегда доступна в чате бота, а это сообщение просто подсказка.
</i>
    """, parse_mode=ParseMode.HTML,
    )

async def filter_orders_by_param(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    "Filter params: fdate|fproduct|fclient|fstatus"
    await update.callback_query.answer()
    if update.callback_query.data == "fdate":
        await update.effective_message.reply_text(
            """
<b>Чтобы показать список заказов по дате напишите боту сообщение такого формата -</b> <i>order:dd.mm.yyyy:dd.mm.yyyy</i>

<b>Пример:</b>
<pre>order:06.05.2025:16.05.2025</pre>

<i>
Будет сформирован список заказов с 6 Мая 2025 по 16 Мая 2025.
P.S.: Эта команда всегда доступна в чате бота, а это сообщение просто подсказка.
</i>
""", parse_mode=ParseMode.HTML,
)
    elif update.callback_query.data == "fproduct":
        await update.effective_message.reply_text(
            """
<b>Чтобы показать список заказов по товару напишите боту сообщение такого формата -</b> <i>order$название_товара</i>

<b>Пример:</b>
<pre>order$🟣</pre>

<b>Если по нескольким товарам, то перечисляем товары через знак $:</b>
<pre>order$🟣$🟠</pre>

<i>
Будет сформирован список заказов с указанными товарами.
P.S.: Эта команда всегда доступна в чате бота, а это сообщение просто подсказка.
</i>
""", parse_mode=ParseMode.HTML,)
    elif update.callback_query.data == "fclient":
        await update.effective_message.reply_text(
            """
<b>Чтобы показать список заказов по КЛИЕНТУ напишите боту сообщение такого формата -</b> <i>order@username или order@phone</i>

<b>Пример:</b>
<pre>order@JimmyBone</pre>

<b>Или по номеру, который вводился изначально в заказе:</b>
<pre>order@79831639136</pre>

<i>
Будет сформирован список заказов по указанному юзернейму клиента или номеру телефона клиента
P.S.: Эта команда всегда доступна в чате бота, а это сообщение просто подсказка.
</i>
""", parse_mode=ParseMode.HTML,
)
    elif update.callback_query.data == "fstatus":
        await update.effective_message.edit_text("Выбрать статус: ", reply_markup=FILTER_ORDERS_BY_STATUS_KB)

async def show_week_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    week_report = await form_week_report()

    if update.callback_query:
        await update.callback_query.answer()
        await update.effective_message.reply_text(week_report, parse_mode=ParseMode.HTML,)
    else:
        session = Session()
        admins = session.query(User).filter(User.role==Role.ADMIN).all()

        for admin in admins:
            try:
                await context.bot.send_message(admin.user_id, week_report, parse_mode=ParseMode.HTML,)
            except Exception as e:
                print(repr(e))

        session.close()


@is_operator
async def confirm_stock_shift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    session = Session()
    shift = session.query(Shift).filter(Shift.status==ShiftStatus.opened).first()
    if shift:
        await update.effective_message.reply_text(t('close_previous_shift', lang))
        session.close()
        return
    else:
        await send_shift_start_msg(update,context, lang)
        await update.effective_message.edit_text(t('shift_started', lang))


@is_operator
async def show_templates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    order_id = int(update.callback_query.data.replace('msg_', ''))

    session = Session()
    order = session.query(Order).filter(Order.id==order_id).first()

    mrkp = await form_operator_templates_kb(order, lang)

    await update.effective_message.reply_text(
        text=t('choose_template', lang),
        reply_markup=mrkp,
    )


@is_admin
async def show_session_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()

    sess_id = update.callback_query.data.replace('sess_act_', '')

    await update.effective_message.edit_reply_markup(show_tg_session_action_kb(sess_id))


@is_admin
async def make_tg_session_as_worker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    sess_id = int(update.callback_query.data.replace('worker_', ''))

    session = Session()
    tgsession: TgSession = session.query(TgSession).get(sess_id)

    if tgsession:
        tgsession.is_worker = True
        session.commit()
        await update.effective_message.reply_text(t('session_now_worker', lang).format(tgsession.name, tgsession.username))
        await update.effective_message.edit_reply_markup(reply_markup=create_tg_sessions_kb())
    else:
        await update.effective_message.reply_text(t('session_not_found', lang))

    session.close()

@is_admin
async def delete_tg_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    sess_id = int(update.callback_query.data.replace('del_sess_', ''))

    session = Session()
    tgsession: TgSession = session.query(TgSession).get(sess_id)

    if tgsession:
        session.delete(tgsession)
        session.flush()
        session.commit()
        await update.effective_message.reply_text(t('session_deleted', lang).format(tgsession.name, tgsession.username))
        await update.effective_message.edit_reply_markup(reply_markup=create_tg_sessions_kb())
    else:
        await update.effective_message.reply_text(t('session_not_found', lang))

    session.close()


@is_admin
async def back_session_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()

    reply_markup = create_tg_sessions_kb()

    await update.effective_message.edit_reply_markup(reply_markup)


@is_admin
async def show_tg_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    reply_markup = create_tg_sessions_kb()

    await update.effective_message.reply_text(t("tg_sessions_info", lang), reply_markup=reply_markup)


@is_courier
async def order_ready(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    session = Session()

    try:
        order_id = int(update.callback_query.data.replace('ready_', ''))
        order = session.query(Order).filter(Order.id==order_id).first()

        order.courier_id = update.effective_user.id
        order.courier_name = f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip()
        order.courier_username = f"@{update.effective_user.username}" if update.effective_user.username else ""

        order.status = Status.completed
        order.delivered = datetime.datetime.now()

        chosen_products = order.get_products()
        for chosen_product in chosen_products:
            chosen_product: dict
            product = session.query(Product).filter(Product.name==chosen_product["name"]).first()
            product.stock = product.stock - chosen_product["quantity"]

        session.commit()

        text = await form_confirm_order_courier(order, lang)
        await update.effective_message.edit_text(text=text, parse_mode=ParseMode.HTML)

        text = await form_confirm_order_courier_info(order, 'ru')  # לקבוצת אדמינים תמיד ברוסית
        await context.bot.send_message(links.ADMIN_CHAT, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.effective_message.reply_text(t('error', lang).format(repr(e)))
    finally:
        session.close()


@is_operator
async def notif_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    client_username = update.callback_query.data.replace('notif_', '')

    session = Session()

    tgsession = session.query(TgSession).filter_by(is_worker=True).first()

    if not tgsession:
        await update.effective_message.reply_text(t('no_worker_session', lang))
        session.close()
        return

    try:
        client = Client(name='default', api_id=tgsession.api_id, api_hash=tgsession.api_hash, session_string=tgsession.string)

        async with client:
            await client.send_message(client_username, t('notif_client_order_active', lang))
    except Exception as e:
        await update.effective_message.reply_text(t('send_message_error', lang).format(repr(e)))
        session.close()
        return

    session.close()
    await update.effective_message.reply_text(t('notification_sent', lang))


@is_operator
async def show_rest_from_last_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    [📊 Текущий остаток на складе]
    • Показывает, сколько осталось от каждого товара
    • Сколько уже выдано
    • Возможность ручного редактирования остатков
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    inline_markup = get_products_markup_left_edit_stock()

    await update.effective_message.reply_text(t('edit_stock_or_delete', lang), reply_markup=inline_markup)


@is_stockman
async def show_menu_edit_crude_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Редактирование продуктов с сырьём.
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    inline_markup = get_products_markup_left_edit_stock_crude()

    await update.effective_message.reply_text(t('edit_crude_stock_prompt', lang), reply_markup=inline_markup)
