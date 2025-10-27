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
        await send_message_with_cleanup(update, context, t("choose_language", lang), reply_markup=reply_markup)
    elif update.callback_query:
        await edit_message_with_cleanup(update, context, t("choose_language", lang), reply_markup=reply_markup)


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language selection callback."""
    await update.callback_query.answer()
    
    lang_code = update.callback_query.data.replace("set_lang_", "")
    user = update.effective_user
    
    # מחיקת הודעות קודמות
    await cleanup_old_messages(context)
    
    # Update user language in DB - Supabase only
    from db.db import db_client
    
    results = db_client.select('users', {'user_id': user.id})
    if results:
        db_client.update('users', {'lang': lang_code}, {'user_id': user.id})
    
    # Send confirmation in new language with cleanup
    await edit_message_with_cleanup(update, context, t("language_changed", lang_code))
    
    # Show main menu in new language immediately
    reply_markup = await build_start_menu(user.id)
    await send_message_with_cleanup(update, context, t("main_menu", lang_code), reply_markup=reply_markup)


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
    await send_message_with_cleanup(update, context, t("main_menu", lang), reply_markup=reply_markup)


@is_admin
async def dump_choose_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await send_message_with_cleanup(update, context, t('choose_format', lang), reply_markup=get_db_format_kb(lang))


@is_admin
async def dump_database(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    format_file = update.callback_query.data

    if format_file == "xlsx":
        # Replace Excel export with text export
        from funcs.utils import export_orders_as_text
        await export_orders_as_text(update, context, lang)
    else:
        # JSON remains as is
        try:
            file = dump_db(format_file)
            await update.effective_message.reply_document(document=file, filename=file.name)
        except Exception as e:
            await update.effective_message.reply_document(repr(e))

@is_admin
async def quick_reports(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await send_message_with_cleanup(update, context, t('choose_report_param', lang), reply_markup=get_quick_reports_kb(lang))


@is_admin
async def show_daily_profit_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show daily profit report options."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    keyboard = [
        [InlineKeyboardButton(t("btn_today", lang), callback_data="profit_today")],
        [InlineKeyboardButton(t("btn_yesterday", lang), callback_data="profit_yesterday")],
        [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.reply_text(
        t("choose_period", lang),
        reply_markup=reply_markup
    )


@is_admin
async def daily_profit_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show daily profit report."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Determine period based on button clicked
    date_option = update.callback_query.data.replace("profit_", "")  # 'today' or 'yesterday'
    
    try:
        report = await form_daily_profit_report(date_option, lang)
        await send_message_with_cleanup(update, context, report, parse_mode=ParseMode.HTML)
    except Exception as e:
        await send_message_with_cleanup(update, context, t("error", lang).format(repr(e)), parse_mode=ParseMode.HTML)


@is_admin
async def report_by_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Using Supabase only
    from db.db import db_client
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    
    all_orders = db_client.select('orders', {'status': 'completed'})
    results = {}
    
    for order in all_orders:
        if order.get('delivered'):
            delivered_time = datetime.datetime.fromisoformat(order['delivered'])
            if delivered_time >= seven_days_ago:
                products = json.loads(order['products'])
                for product in products:
                    product_key = json.dumps([product], ensure_ascii=False)
                    if product_key not in results:
                        results[product_key] = 0
                    results[product_key] += 1
    
    # Convert to list format
    results_list = [(k, v) for k, v in results.items()]

    report = t("product_report_title", lang) + "\n\n"
    total_count = 0

    for product_data, count in results_list:
        products = json.loads(product_data)  # JSON deserialization
        for product in products:
            product_name = product['name']
            product_quantity = product['quantity']
            report += f"{product_name} – {product_quantity * count} {t('units', lang)}.\n"  # Multiply by number of orders
            total_count += product_quantity * count  # Count total quantity

    report += f"\n{t('total', lang)}: {total_count} {t('units', lang)}"

    await send_message_with_cleanup(update, context, text=report)


@is_admin
async def report_by_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Using Supabase only
    from db.db import db_client
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    
    all_orders = db_client.select('orders', {'status': 'completed'})
    client_orders = {}
    
    for order in all_orders:
        if order.get('delivered'):
            delivered_time = datetime.datetime.fromisoformat(order['delivered'])
            if delivered_time >= seven_days_ago:
                key = (order['client_name'], order['client_username'], order['client_phone'])
                if key not in client_orders:
                    client_orders[key] = 0
                client_orders[key] += 1
    
    results = [(name, username, phone, count) for (name, username, phone), count in client_orders.items()]

    report = t("client_report_title", lang) + "\n\n"
    total_orders = 0

    for index, (client_name, client_username, client_phone, count) in enumerate(results, start=1):
        report += f"{index}. {client_name} {client_username} +{client_phone} – {count} {t('orders', lang)}\n"
        total_orders += count  # Count total number of orders

    report += f"\n{t('total', lang)}: {total_orders} {t('orders', lang)}."

    await send_message_with_cleanup(update, context, text=report)


@is_admin
async def report_by_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Using Supabase only
    from db.db import db_client
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    
    # Get all orders delivered in the last 7 days
    all_orders = db_client.select('orders', {'status': 'completed'})
    results = []
    for order in all_orders:
        if order.get('delivered'):
            delivered_time = datetime.datetime.fromisoformat(order['delivered'])
            if delivered_time >= seven_days_ago:
                # Convert to object-like structure
                obj = type('Order', (), order)()
                # Ensure delivered is a datetime object
                obj.delivered = delivered_time
                results.append(obj)

    order_prices = []

    # Calculate total price for each order
    for order in results:
        products = json.loads(order.products)  # JSON deserialization
        total_price = sum(product['total_price'] for product in products)
        order_prices.append((order.id, order.client_name, order.client_username, order.client_phone, order.delivered, total_price))

    # Sort orders by total price and take top 15
    sorted_orders = sorted(order_prices, key=lambda x: x[2], reverse=True)[:15]

    report = t("top_15_orders_by_price", lang) + "\n\n"
    
    for index, (order_id, client_name, client_username, client_phone, delivered, total) in enumerate(sorted_orders, start=1):
        report += f"{index}. {t('order', lang)} #{order_id} {client_name} {client_username} +{client_phone} {delivered.strftime('%d.%m.%Y, %H:%M:%S')} - {total} ₪.\n"

    await send_message_with_cleanup(update, context, text=report)

@is_admin
async def report_by_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Using Supabase only
    from db.db import db_client
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)

    # Get all orders delivered in the last 7 days
    all_orders = db_client.select('orders', {'status': 'completed'})
    results = []
    for order in all_orders:
        if order.get('delivered'):
            delivered_time = datetime.datetime.fromisoformat(order['delivered'])
            if delivered_time >= seven_days_ago:
                obj = type('Order', (), order)()
                obj.delivered = delivered_time
                results.append(obj)

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


    # Count orders by day of week
    for order in results:
        if order.delivered:
            weekday = order.delivered.strftime('%A')  # Get day of week
            if weekday in weekday_count:
                weekday_count[weekday] += 1
            else:
                weekday_count[weekday] = 1

    # Sort weekdays by number of orders
    sorted_weekdays = sorted(weekday_count.items(), key=lambda x: x[1], reverse=True)

    report = t("orders_by_days_title", lang) + "\n\n"
    
    for index, (weekday, count) in enumerate(sorted_weekdays, start=1):
        report += f"{index}. {weekdays_translation[weekday]} - {count} {t('orders', lang)}.\n"

    await send_message_with_cleanup(update, context, text=report)

@is_admin
async def show_admin_action_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await send_message_with_cleanup(update, context, t('admin_menu', lang), reply_markup=get_admin_action_kb(lang), parse_mode=ParseMode.HTML)

@is_operator
async def beginning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # מחיקת הודעות קודמות
    await cleanup_old_messages(context)
    
    # Using Supabase only
    from db.db import get_opened_shift
    
    shift_data = get_opened_shift()
    if shift_data:
        # Convert dict to object
        shift = type('Shift', (), shift_data)()
        shift.opened_time = datetime.datetime.fromisoformat(shift_data['opened_time'])
    else:
        shift = None

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
        await send_message_with_cleanup(update, context, t('available_stock', lang).format(prod_txt), 
                                       reply_markup=get_operator_shift_start_kb(lang), 
                                       parse_mode=ParseMode.HTML)


@is_operator
async def msg_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    reply_markup = await get_all_active_orders_to_msg_kb()

    if reply_markup:
        await send_message_with_cleanup(update, context, t('choose_client_to_msg', lang), reply_markup=reply_markup)
    else:
        await send_message_with_cleanup(update, context, t('no_active_orders', lang))


@is_admin
async def manage_roles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await send_message_with_cleanup(update, context, t('manage_roles_title', lang), reply_markup=get_manage_roles_kb(lang))

@is_admin
async def show_security_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await send_message_with_cleanup(update, context, t('security_menu', lang), reply_markup=get_security_kb(lang))


async def all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    await update.effective_message.edit_text(t("filter_by", lang), reply_markup=get_orders_filter_kb(lang))

async def filter_orders_by_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    "order:dd.mm.yyyy:dd.mm.yyyy"
    # Extract dates from message
    _, start_date_str, end_date_str = update.effective_message.text.split(':')
    
    # Convert strings to datetime objects
    start_date = datetime.datetime.strptime(start_date_str, '%d.%m.%Y')
    end_date = datetime.datetime.strptime(end_date_str, '%d.%m.%Y')

    
    # Make sure end_date is greater than start_date
    if start_date > end_date:
        await send_message_with_cleanup(update, context, t("date_error", get_user_lang(update.effective_user.id)))
        return

    # Using Supabase only
    from db.db import get_all_orders
    import datetime
    
    # Filter orders by date
    all_orders = get_all_orders()
    orders = []
    for order_dict in all_orders:
        if order_dict.get('created'):
            created_time = datetime.datetime.fromisoformat(order_dict['created'])
            if start_date <= created_time <= end_date:
                obj = type('Order', (), order_dict)()
                orders.append(obj)

    if not orders:
        lang = get_user_lang(update.effective_user.id)
        not_found = t("no_orders_found_dates", lang)
        await send_message_with_cleanup(update, context, f"{not_found}: {start_date} - {end_date}")
        return

    lang = get_user_lang(update.effective_user.id)
    msg = t("total_found", lang).format(len(orders))
    context.user_data["orders_filtered"] = [order.to_dict() for order in orders]

    await send_message_with_cleanup(update, context, msg, parse_mode=ParseMode.HTML)
    await update.effective_message.delete()


async def filter_orders_by_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    "order$название_товара"
    product_names = update.effective_message.text.split('$')[1:]
    print(product_names)

    # Using Supabase only
    from db.db import get_all_orders
    
    # Example query to check products field content
    orders = []
    
    all_orders = get_all_orders()
    for order_dict in all_orders:
        products = json.loads(order_dict.get('products', '[]'))
        products_names_db = [p.get('name') for p in products]
        found = bool(set(products_names_db).intersection(product_names))
        if found:
            obj = type('Order', (), order_dict)()
            obj.get_products = lambda: products
            obj.to_dict = lambda: order_dict
            orders.append(obj)

    if not orders:
        lang = get_user_lang(update.effective_user.id)
        not_found = t("no_orders_found_products", lang)
        await send_message_with_cleanup(update, context, f"{not_found}: {product_names}")
        return

    lang = get_user_lang(update.effective_user.id)
    msg = t("total_found", lang).format(len(orders))
    context.user_data["orders_filtered"] = [order.to_dict() for order in orders]

    await send_message_with_cleanup(update, context, msg, parse_mode=ParseMode.HTML)
    await update.effective_message.delete()


async def fetch_orders_excel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    "Export orders as text instead of Excel"
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Use new function for text export
    from funcs.utils import export_orders_as_text
    await export_orders_as_text(update, context, lang)

async def filter_orders_by_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    "order@username | order@phone"
    identifier = update.effective_message.text.replace("order@", "")

    # Using Supabase only
    from db.db import get_all_orders
    
    all_orders = get_all_orders()
    orders = []
    for order_dict in all_orders:
        if identifier.isdigit():
            if order_dict.get('client_phone') == identifier:
                obj = type('Order', (), order_dict)()
                orders.append(obj)
        else:
            search_identifier = "@" + identifier
            if order_dict.get('client_username') == search_identifier:
                obj = type('Order', (), order_dict)()
                orders.append(obj)

    if not orders:
        lang = get_user_lang(update.effective_user.id)
        not_found = t("no_orders_found_param", lang)
        await send_message_with_cleanup(update, context, f"{not_found}: {identifier}")
        return

    lang = get_user_lang(update.effective_user.id)
    msg = t("total_found", lang).format(len(orders))
    context.user_data["orders_filtered"] = [order.to_dict() for order in orders]

    await send_message_with_cleanup(update, context, msg, parse_mode=ParseMode.HTML)
    await update.effective_message.delete()


async def filter_orders_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    status_value = update.callback_query.data

    for status in (Status.completed,Status.active,Status.pending,Status.cancelled,Status.delay,):
        if status.value == status_value:
            break

    # Using Supabase only
    from db.db import get_all_orders
    
    all_orders = get_all_orders()
    orders = []
    for order_dict in all_orders:
        if order_dict.get('status') == status.value:
            obj = type('Order', (), order_dict)()
            orders.append(obj)

    if not orders:
        not_found = t("no_orders_found_status", lang)
        await send_message_with_cleanup(update, context, f"{not_found}: {status}")
        return

    msg = t("total_found", lang).format(len(orders))
    context.user_data["orders_filtered"] = [order.to_dict() for order in orders]

    await send_message_with_cleanup(update, context, msg, parse_mode=ParseMode.HTML)


@is_admin
async def manage_links_tip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Get current groups from database
    from db.db import get_bot_setting
    admin_chat = get_bot_setting('admin_chat') or links.ADMIN_CHAT
    order_chat = get_bot_setting('order_chat') or links.ORDER_CHAT
    
    admin_group_link = ('@' + admin_chat) if '@' not in admin_chat else admin_chat
    order_group_link = ('@' + order_chat) if '@' not in order_chat else order_chat

    msg = t("current_links", lang).format(admin_group_link, order_group_link)
    
    await send_message_with_cleanup(update, context, msg, reply_markup=get_change_links_kb(lang), parse_mode=ParseMode.HTML)


@is_admin
async def erase_orders_before_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        _, start_date_str = update.effective_message.text.split(':')
        
        # Convert strings to datetime objects
        date = datetime.datetime.strptime(start_date_str, '%d.%m.%Y')

        # Using Supabase only
        from db.db import get_all_orders, db_client
        
        all_orders = get_all_orders()
        orders_count = 0
        for order in all_orders:
            if order.get('created'):
                created_time = datetime.datetime.fromisoformat(order['created'])
                if created_time < date:
                    db_client.delete('orders', {'id': order['id']})
                    orders_count += 1
    except Exception as e:
        await send_message_with_cleanup(update, context, f"{t('error', get_user_lang(update.effective_user.id))}: {repr(e)}")
        await update.effective_message.delete()
        return

    await send_message_with_cleanup(update, context, t("orders_deleted_success", get_user_lang(update.effective_user.id)).format(count=orders_count))
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
    lang = get_user_lang(update.effective_user.id)
    if update.callback_query.data == "fdate":
        await send_message_with_cleanup(update, context, """
<b>Чтобы показать список заказов по дате напишите боту сообщение такого формата -</b> <i>order:dd.mm.yyyy:dd.mm.yyyy</i>

<b>Пример:</b>
<pre>order:06.05.2025:16.05.2025</pre>

<i>
Будет сформирован список заказов с 6 Мая 2025 по 16 Мая 2025.
P.S.: Эта команда всегда доступна в чате бота, а это сообщение просто подсказка.
</i>
""", parse_mode=ParseMode.HTML)
    elif update.callback_query.data == "fproduct":
        await send_message_with_cleanup(update, context, """
<b>Чтобы показать список заказов по товару напишите боту сообщение такого формата -</b> <i>order$название_товара</i>

<b>Пример:</b>
<pre>order$🟣</pre>

<b>Если по нескольким товарам, то перечисляем товары через знак $:</b>
<pre>order$🟣$🟠</pre>

<i>
Будет сформирован список заказов с указанными товарами.
P.S.: Эта команда всегда доступна в чате бота, а это сообщение просто подсказка.
</i>
""", parse_mode=ParseMode.HTML)
    elif update.callback_query.data == "fclient":
        await send_message_with_cleanup(update, context, """
<b>Чтобы показать список заказов по КЛИЕНТУ напишите боту сообщение такого формата -</b> <i>order@username или order@phone</i>

<b>Пример:</b>
<pre>order@JimmyBone</pre>

<b>Или по номеру, который вводился изначально в заказе:</b>
<pre>order@79831639136</pre>

<i>
Будет сформирован список заказов по указанному юзернейму клиента или номеру телефона клиента
P.S.: Эта команда всегда доступна в чате бота, а это сообщение просто подсказка.
</i>
""", parse_mode=ParseMode.HTML)
    elif update.callback_query.data == "fstatus":
        await edit_message_with_cleanup(update, context, t("choose_status", lang), reply_markup=FILTER_ORDERS_BY_STATUS_KB)

async def show_week_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    week_report = await form_week_report()

    if update.callback_query:
        await update.callback_query.answer()
        await send_message_with_cleanup(update, context, week_report, parse_mode=ParseMode.HTML)
    else:
        # Using Supabase only
        from db.db import db_client
        
        admins = db_client.select('users', {'role': 'admin'})
        
        for admin in admins:
            try:
                await context.bot.send_message(admin['user_id'], week_report, parse_mode=ParseMode.HTML,)
            except Exception as e:
                print(repr(e))


@is_operator
async def confirm_stock_shift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # מחיקת הודעות קודמות
    await cleanup_old_messages(context)
    
    # Using Supabase only
    from db.db import get_opened_shift
    
    shift_data = get_opened_shift()
    shift = type('Shift', (), shift_data)() if shift_data and isinstance(shift_data, dict) else None
    
    if shift:
        await send_message_with_cleanup(update, context, t('close_previous_shift', lang))
        return
    else:
        await send_shift_start_msg(update,context, lang)
        # send_shift_start_msg כבר מחזירה למסך הראשי ואוטומטית, לא צריך לעשות כלום נוסף
        return


@is_operator
async def show_templates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    order_id = int(update.callback_query.data.replace('msg_', ''))

    # Using Supabase only
    from db.db import db_client
    
    orders = db_client.select('orders', {'id': order_id})
    order = type('Order', (), orders[0])() if orders else None

    mrkp = await form_operator_templates_kb(order, lang)

    await update.effective_message.reply_text(
        text=t('choose_template', lang),
        reply_markup=mrkp,
    )


@is_admin
async def show_session_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    sess_id = update.callback_query.data.replace('sess_act_', '')

    await update.effective_message.edit_reply_markup(show_tg_session_action_kb(sess_id, lang))


@is_admin
async def make_tg_session_as_worker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    sess_id = int(update.callback_query.data.replace('worker_', ''))

    # Using Supabase only
    from db.db import db_client
    
    sessions = db_client.select('tgsessions', {'id': sess_id})
    if sessions:
        db_client.update('tgsessions', {'is_worker': True}, {'id': sess_id})
        session_data = sessions[0]
        await send_message_with_cleanup(update, context, t('session_now_worker', lang).format(session_data['name'], session_data['username']))
        await update.effective_message.edit_reply_markup(reply_markup=create_tg_sessions_kb())
    else:
        await send_message_with_cleanup(update, context, t('session_not_found', lang))

@is_admin
async def delete_tg_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    sess_id = int(update.callback_query.data.replace('del_sess_', ''))

    # Using Supabase only
    from db.db import db_client
    
    sessions = db_client.select('tgsessions', {'id': sess_id})
    if sessions:
        db_client.delete('tgsessions', {'id': sess_id})
        session_data = sessions[0]
        await send_message_with_cleanup(update, context, t('session_deleted', lang).format(session_data['name'], session_data['username']))
        await update.effective_message.edit_reply_markup(reply_markup=create_tg_sessions_kb())
    else:
        await send_message_with_cleanup(update, context, t('session_not_found', lang))


@is_admin
async def back_session_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()

    reply_markup = create_tg_sessions_kb()

    await update.effective_message.edit_reply_markup(reply_markup)


@is_admin
async def show_tg_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    reply_markup = create_tg_sessions_kb(lang)

    await send_message_with_cleanup(update, context, t("tg_sessions_info", lang), reply_markup=reply_markup)


@is_courier
async def order_ready(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Using Supabase only
    from db.db import db_client
    
    try:
        order_id = int(update.callback_query.data.replace('ready_', ''))
        
        orders = db_client.select('orders', {'id': order_id})
        if orders:
            order = orders[0]
            # Update order
            db_client.update('orders', {
                'courier_id': update.effective_user.id,
                'courier_name': f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip(),
                'courier_username': f"@{update.effective_user.username}" if update.effective_user.username else "",
                'status': Status.completed.value,
                'delivered': datetime.datetime.now().isoformat()
            }, {'id': order_id})
            
            # Update products stock
            chosen_products = json.loads(order['products'])
            for chosen_product in chosen_products:
                products = db_client.select('products', {'name': chosen_product["name"]})
                if products:
                    product = products[0]
                    new_stock = product['stock'] - chosen_product["quantity"]
                    db_client.update('products', {'stock': new_stock}, {'id': product['id']})
            
            # Convert to object for form_confirm_order_courier
            order_obj = type('Order', (), order)()
            
            text = await form_confirm_order_courier(order_obj, lang)
            await update.effective_message.edit_text(text=text, parse_mode=ParseMode.HTML)
        else:
            await send_message_with_cleanup(update, context, t('order_not_found', lang))
            return

        from db.db import get_bot_setting
        admin_chat = get_bot_setting('admin_chat') or links.ADMIN_CHAT
        if admin_chat:
            text = await form_confirm_order_courier_info(order_obj, 'ru')  # For admin group always in Russian
            await context.bot.send_message(admin_chat, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await send_message_with_cleanup(update, context, t('error', lang).format(repr(e)))


@is_operator
async def notif_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    client_username = update.callback_query.data.replace('notif_', '')

    # Using Supabase only
    from db.db import db_client
    
    sessions = db_client.select('tgsessions', {'is_worker': True})
    if not sessions:
        await send_message_with_cleanup(update, context, t('no_worker_session', lang))
        return
    
    tgsession_data = sessions[0]
    tgsession = type('TgSession', (), tgsession_data)()

    try:
        client = Client(name='default', api_id=tgsession.api_id, api_hash=tgsession.api_hash, session_string=tgsession.string)

        async with client:
            await client.send_message(client_username, t('notif_client_order_active', lang))
    except Exception as e:
        await send_message_with_cleanup(update, context, t('send_message_error', lang).format(repr(e)))
        return

    await send_message_with_cleanup(update, context, t('notification_sent', lang))


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

    await send_message_with_cleanup(update, context, t('edit_stock_or_delete', lang), reply_markup=inline_markup)


@is_stockman
async def show_menu_edit_crude_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Редактирование продуктов с сырьём.
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Clean previous message
    await clean_previous_message(update, context)
    
    # Add to navigation history
    add_to_navigation_history(context, 'stock_menu')

    inline_markup = get_products_markup_left_edit_stock_crude()

    msg = await send_message_with_cleanup(update, context, t('edit_crude_stock_prompt', lang), reply_markup=inline_markup)
    
    # Save ID for future cleanup
    save_message_id(context, msg.message_id)

# Central navigation handler
async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle navigation buttons (back and home)"""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Clean previous message
    await clean_previous_message(update, context)
    
    if update.callback_query.data == "back":
        # Back logic
        previous_menu = get_previous_menu(context)
        if not previous_menu:
            msg = await send_message_with_cleanup(update, context, t("no_previous_menu", lang))
            save_message_id(context, msg.message_id)
            return
        
        # Restore previous menu
        menu_name = previous_menu['menu']
        if menu_name == 'main_menu':
            await start(update, context)
        elif menu_name == 'stock_menu':
            await show_menu_edit_crude_stock(update, context)
        elif menu_name == 'admin_menu':
            await show_admin_action_kb(update, context)
        else:
            msg = await send_message_with_cleanup(update, context, t("no_previous_menu", lang))
            save_message_id(context, msg.message_id)
    
    elif update.callback_query.data == "home":
        # Return to home page
        await start(update, context)

@is_admin
async def show_staff_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display list of employees in the system"""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Using Supabase only
    from db.db import db_client
    
    # Get all users
    users_data = db_client.select('users')
    users = [type('User', (), user)() for user in users_data]
    
    # Group employees by role
    staff_by_role = {
        'admin': [],
        'operator': [],
        'stockman': [],
        'courier': [],
        'guest': []
    }
    
    for user in users:
        role = user.role.value if hasattr(user.role, 'value') else (user.role if user.role else 'guest')
        staff_by_role[role].append({
            'name': f"{user.firstname or ''} {user.lastname or ''}".strip(),
            'username': f"@{user.username}" if user.username else t("no_username", lang),
            'user_id': user.user_id,
            'lang': user.lang or 'ru'
        })
    
    # Build message
    rtl = '\u200F' if lang == 'he' else ''
    message = f"{rtl}<b>{t('staff_list_title', lang)}</b>\n\n"
    
    role_translations = {
        'admin': t('role_admin', lang),
        'operator': t('role_operator', lang),
        'stockman': t('role_stockman', lang),
        'courier': t('role_courier', lang),
        'guest': t('role_guest', lang)
    }
    
    for role, staff_list in staff_by_role.items():
        if staff_list:
            message += f"<b>{role_translations[role]}:</b>\n"
            for staff in staff_list:
                message += f"• {staff['name']} {staff['username']} (ID: {staff['user_id']})\n"
            message += "\n"
    
    await send_message_with_cleanup(update, context, message, parse_mode=ParseMode.HTML)
