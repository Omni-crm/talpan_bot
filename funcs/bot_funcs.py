import datetime, traceback
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
        await update.callback_query.answer()
        # Clean previous message first
        await clean_previous_message(update, context)
        # Send new message instead of editing
        await send_message_with_cleanup(update, context, t("choose_language", lang), reply_markup=reply_markup)


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language selection callback."""
    await update.callback_query.answer()
    
    lang_code = update.callback_query.data.replace("set_lang_", "")
    user = update.effective_user
    
    # מחיקת הודעות קודמות
    await clean_previous_message(update, context)
    
    # Update user language in DB - Supabase only
    from db.db import db_client
    
    results = db_client.select('users', {'user_id': user.id})
    if results:
        db_client.update('users', {'lang': lang_code}, {'user_id': user.id})
    
    # Send confirmation in new language
    await send_message_with_cleanup(update, context, t("language_changed", lang_code))
    
    # Small delay to show confirmation
    import asyncio
    await asyncio.sleep(1)
    
    # Clean confirmation and show main menu in new language
    await clean_previous_message(update, context)
    reply_markup = await build_start_menu(user.id)
    await send_message_with_cleanup(update, context, t("main_menu", lang_code), reply_markup=reply_markup)


@is_user_in_db
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Available features buttons."""
    user = update.effective_user
    lang = get_user_lang(user.id)

    # TEMPORARILY DISABLED: מחיקת הודעת /start גורמת ללופ
    # if update.message and update.message.text == '/start':
    #     try:
    #         await update.message.delete()
    #         print(f"🧹 Deleted /start message from user {update.effective_user.id}")
    #     except Exception as e:
    #         print(f"Could not delete /start message: {e}")

    # send_message_with_cleanup already handles cleanup_old_messages, so no need to do it here
    # Clear navigation history when returning to main menu (but add main_menu)
    if 'navigation_history' in context.user_data:
        context.user_data['navigation_history'] = []

    # Always add main_menu to navigation history
    add_to_navigation_history(context, 'main_menu')

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
async def quick_reports(update: Update, context: ContextTypes.DEFAULT_TYPE, from_back_button: bool = False) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Add to navigation history ONLY if not coming from back button
    if not from_back_button:
        add_to_navigation_history(context, 'quick_reports_menu')
    
    await send_message_with_cleanup(update, context, t('choose_report_param', lang), reply_markup=get_quick_reports_kb(lang))


@is_admin
async def show_daily_profit_options(update: Update, context: ContextTypes.DEFAULT_TYPE, from_back_button: bool = False) -> None:
    """Show daily profit report options."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Add to navigation history ONLY if not coming from back button
    if not from_back_button:
        add_to_navigation_history(context, 'daily_profit_menu')
    
    keyboard = [
        [InlineKeyboardButton(t("btn_today", lang), callback_data="profit_today")],
        [InlineKeyboardButton(t("btn_yesterday", lang), callback_data="profit_yesterday")],
        [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Use send_message_with_cleanup for consistent cleanup handling
    await send_message_with_cleanup(update, context, t("choose_period", lang), reply_markup=reply_markup)


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
            try:
                delivered_time = datetime.datetime.fromisoformat(order['delivered'])
                if delivered_time >= seven_days_ago:
                    # CRITICAL: Safe JSON parsing with error handling
                    products_json = order.get('products', '[]')
                    if not products_json or not isinstance(products_json, str):
                        continue
                    try:
                        products = json.loads(products_json)
                        if not isinstance(products, list):
                            continue
                        for product in products:
                            if isinstance(product, dict):
                                product_key = json.dumps([product], ensure_ascii=False)
                                if product_key not in results:
                                    results[product_key] = 0
                                results[product_key] += 1
                    except (json.JSONDecodeError, TypeError):
                        continue  # Skip invalid products JSON
            except (ValueError, TypeError, AttributeError):
                continue  # Skip invalid delivered timestamp
    
    # Convert to list format
    results_list = [(k, v) for k, v in results.items()]

    # Check if we have any data
    if not results_list:
        await send_message_with_cleanup(update, context, text=t("no_data_for_report", lang))
        # Return to main menu after 2 seconds
        import asyncio
        await asyncio.sleep(2)
        await start(update, context)
        return

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
            try:
                delivered_time = datetime.datetime.fromisoformat(order['delivered'])
                if delivered_time >= seven_days_ago:
                    key = (order.get('client_name', ''), order.get('client_username', ''), order.get('client_phone', ''))
                    if key not in client_orders:
                        client_orders[key] = 0
                    client_orders[key] += 1
            except (ValueError, TypeError, AttributeError):
                continue  # Skip invalid delivered timestamp
    
    results = [(name, username, phone, count) for (name, username, phone), count in client_orders.items()]

    # Check if we have any data
    if not results:
        await send_message_with_cleanup(update, context, text=t("no_data_for_report", lang))
        # Return to main menu after 2 seconds
        import asyncio
        await asyncio.sleep(2)
        await start(update, context)
        return

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
        try:
            # CRITICAL: Safe JSON parsing with error handling
            products_json = getattr(order, 'products', '[]')
            if not products_json or not isinstance(products_json, str):
                continue
            try:
                products = json.loads(products_json)
                if not isinstance(products, list):
                    continue
                total_price = sum(product.get('total_price', 0) or 0 for product in products if isinstance(product, dict))
                order_prices.append((order.id, order.client_name, order.client_username, order.client_phone, order.delivered, total_price))
            except (json.JSONDecodeError, TypeError):
                continue  # Skip invalid products JSON
        except (AttributeError, TypeError):
            continue  # Skip orders with missing attributes

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

    # Check if we have any data
    if not sorted_weekdays:
        await send_message_with_cleanup(update, context, text=t("no_data_for_report", lang))
        # Return to main menu after 2 seconds
        import asyncio
        await asyncio.sleep(2)
        await start(update, context)
        return

    report = t("orders_by_days_title", lang) + "\n\n"
    
    for index, (weekday, count) in enumerate(sorted_weekdays, start=1):
        report += f"{index}. {weekdays_translation[weekday]} - {count} {t('orders', lang)}.\n"

    await send_message_with_cleanup(update, context, text=report)

@is_admin
async def show_admin_action_kb(update: Update, context: ContextTypes.DEFAULT_TYPE, from_back_button: bool = False) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Add to navigation history ONLY if not coming from back button
    if not from_back_button:
        add_to_navigation_history(context, 'admin_menu')
    
    await send_message_with_cleanup(update, context, t('admin_menu', lang), reply_markup=get_admin_action_kb(lang), parse_mode=ParseMode.HTML)

@is_operator
async def beginning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle shift start/status check"""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
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
        # Use edit_message_with_cleanup for graceful error handling
        await edit_message_with_cleanup(
            update, context,
            t('shift_not_closed', lang).format(shift_start_date), 
            reply_markup=get_shift_end_kb(lang), 
            parse_mode=ParseMode.HTML
        )
    else:
        products = Shift.set_products()
        prod_txt = " | ".join([f"{product['name']} {product['stock']}" for product in products])
        # send_message_with_cleanup already handles cleanup
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
async def manage_roles(update: Update, context: ContextTypes.DEFAULT_TYPE, from_back_button: bool = False) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Add to navigation history ONLY if not coming from back button
    if not from_back_button:
        add_to_navigation_history(context, 'manage_roles_menu')
    
    await send_message_with_cleanup(update, context, t('manage_roles_title', lang), reply_markup=get_manage_roles_kb(lang))

@is_admin
async def show_security_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_back_button: bool = False) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Add to navigation history ONLY if not coming from back button
    if not from_back_button:
        add_to_navigation_history(context, 'security_menu')
    
    await send_message_with_cleanup(update, context, t('security_menu', lang), reply_markup=get_security_kb(lang))


async def all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE, from_back_button: bool = False) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Add to navigation history ONLY if not coming from back button
    if not from_back_button:
        add_to_navigation_history(context, 'orders_filter_menu')
    
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
        # CRITICAL: Safe JSON parsing with error handling
        products_json = order_dict.get('products', '[]')
        if not products_json or not isinstance(products_json, str):
            continue
        try:
            products = json.loads(products_json)
            if not isinstance(products, list):
                continue
            products_names_db = [p.get('name') for p in products if isinstance(p, dict) and p.get('name')]
            found = bool(set(products_names_db).intersection(product_names))
            if found:
                obj = type('Order', (), order_dict)()
                obj.get_products = lambda p=products: p  # Fix closure issue
                obj.to_dict = lambda d=order_dict: d  # Fix closure issue
                orders.append(obj)
        except (json.JSONDecodeError, TypeError):
            continue  # Skip invalid products JSON

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
    
    # Import the keyboard function
    from config.kb import get_filter_instruction_kb
    
    if update.callback_query.data == "fdate":
        await send_message_with_cleanup(
            update, 
            context, 
            t('filter_by_date_instruction', lang),
            reply_markup=get_filter_instruction_kb(lang),
            parse_mode=ParseMode.HTML
        )
    elif update.callback_query.data == "fproduct":
        await send_message_with_cleanup(
            update, 
            context, 
            t('filter_by_product_instruction', lang),
            reply_markup=get_filter_instruction_kb(lang),
            parse_mode=ParseMode.HTML
        )
    elif update.callback_query.data == "fclient":
        await send_message_with_cleanup(
            update, 
            context, 
            t('filter_by_client_instruction', lang),
            reply_markup=get_filter_instruction_kb(lang),
            parse_mode=ParseMode.HTML
        )
    elif update.callback_query.data == "fstatus":
        await edit_message_with_cleanup(update, context, t("choose_status", lang), reply_markup=get_filter_orders_by_status_kb(lang))

async def show_week_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_lang(update.effective_user.id)
    week_report = await form_week_report(lang)

    if update.callback_query:
        await update.callback_query.answer()
        await send_message_with_cleanup(update, context, week_report, parse_mode=ParseMode.HTML)
    else:
        # Using Supabase only
        from db.db import db_client
        
        admins = db_client.select('users', {'role': 'admin'})
        
        for admin in admins:
            try:
                admin_lang = get_user_lang(admin['user_id'])
                week_report_admin = await form_week_report(admin_lang)
                await context.bot.send_message(admin['user_id'], week_report_admin, parse_mode=ParseMode.HTML)
            except Exception as e:
                print(repr(e))


@is_operator
async def confirm_stock_shift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        print(f"🔧 confirm_stock_shift called")
        await update.callback_query.answer()
        lang = get_user_lang(update.effective_user.id)
        print(f"🔧 Language: {lang}")
        
        # מחיקת הודעות קודמות
        await cleanup_old_messages(context)
        print(f"🔧 Messages cleaned")
        
        # Using Supabase only
        from db.db import get_opened_shift
        
        print(f"🔧 Getting opened shift...")
        shift_data = get_opened_shift()
        print(f"🔧 Shift data: {shift_data}")
        shift = type('Shift', (), shift_data)() if shift_data and isinstance(shift_data, dict) else None
        print(f"🔧 Shift object: {shift}")
        
        if shift:
            print(f"🔧 Shift exists, closing previous shift")
            await send_message_with_cleanup(update, context, t('close_previous_shift', lang))
            return
        else:
            print(f"🔧 No shift, starting new shift")
            await send_shift_start_msg(update,context, lang)
            # send_shift_start_msg כבר מחזירה למסך הראשי ואוטומטית, לא צריך לעשות כלום נוסף
            return
    except Exception as e:
        print(f"❌ ERROR in confirm_stock_shift: {e}")
        import traceback
        traceback.print_exc()
        await update.effective_message.reply_text(f"Error: {e}")


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
async def show_tg_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE, from_back_button: bool = False) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Add to navigation history ONLY if not coming from back button
    if not from_back_button:
        add_to_navigation_history(context, 'tg_sessions_menu')
    
    reply_markup = create_tg_sessions_kb(lang)

    await send_message_with_cleanup(update, context, t("tg_sessions_info", lang), reply_markup=reply_markup)


@is_courier
async def order_ready(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Mark order as delivered - PRODUCTION-GRADE: Full validation, transaction safety, error handling.
    
    CRITICAL SAFETY FEATURES:
    1. Double-check status before update (race condition prevention)
    2. Validate all products before any updates
    3. Track all stock updates for rollback on failure
    4. Verify order update success before finalizing
    5. Rollback stock changes if order update fails
    6. Comprehensive error logging
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # Using Supabase only
    from db.db import db_client
    import logging
    
    logger = logging.getLogger(__name__)
    order_id = None
    stock_updates = []  # Track all stock updates for potential rollback
    
    try:
        # Parse order_id with validation
        try:
            order_id = int(update.callback_query.data.replace('ready_', ''))
            if order_id <= 0:
                raise ValueError(f"Invalid order ID: {order_id}")
        except (ValueError, AttributeError) as e:
            logger.error(f"❌ order_ready: Invalid order ID format: {update.callback_query.data} - {repr(e)}")
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Invalid order ID format"
            )
            return
        
        # Fetch order with race condition protection (re-check after validation)
        orders = db_client.select('orders', {'id': order_id})
        if not orders:
            logger.warning(f"⚠️ order_ready: Order {order_id} not found")
            await send_message_with_cleanup(update, context, t('order_not_found', lang))
            return
        
        order = orders[0]
        logger.info(f"🔧 order_ready: Processing order {order_id}, current status: {order.get('status')}")
        
        # CRITICAL CHECK 1: Prevent double delivery! (re-check with fresh data)
        current_status = order.get('status', '')
        is_already_completed = (
            current_status == 'completed' or 
            current_status == Status.completed.value or
            'Завершён' in str(current_status) or
            'הושלם' in str(current_status) or
            order.get('delivered') is not None  # Also check if delivered timestamp exists
        )
        
        if is_already_completed:
            logger.warning(f"⚠️ order_ready: Order {order_id} already completed (status: {current_status})")
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Order #{order_id} already completed!"
            )
            return
        
        # CRITICAL CHECK 2: Validate products JSON exists and is valid
        products_json = order.get('products')
        if not products_json or not isinstance(products_json, str) or not products_json.strip():
            logger.error(f"❌ order_ready: Order {order_id} has no products JSON")
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Order #{order_id} has no products!"
            )
            return
        
        # Parse products with comprehensive error handling
        try:
            chosen_products = json.loads(products_json)
        except json.JSONDecodeError as e:
            logger.error(f"❌ order_ready: Invalid JSON for order {order_id}: {repr(e)}")
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Invalid products data for order #{order_id}"
            )
            return
        except TypeError as e:
            logger.error(f"❌ order_ready: TypeError parsing products for order {order_id}: {repr(e)}")
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Products data type error for order #{order_id}"
            )
            return
        
        # Validate products structure
        if not isinstance(chosen_products, list):
            logger.error(f"❌ order_ready: Products is not a list for order {order_id}: {type(chosen_products)}")
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Invalid products format for order #{order_id}"
            )
            return
        
        if len(chosen_products) == 0:
            logger.error(f"❌ order_ready: Empty products list for order {order_id}")
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Order #{order_id} has empty products list!"
            )
            return
        
        # CRITICAL CHECK 3: Validate ALL products before ANY updates
        # This ensures atomicity - if any product is invalid, nothing is updated
        stock_update_errors = []
        
        # CRITICAL: Aggregate duplicate products (same product name, sum quantities)
        # This prevents double/triple stock deduction for same product
        product_aggregates = {}  # {product_name: total_quantity}
        for idx, chosen_product in enumerate(chosen_products):
            # Validate product structure first
            if not isinstance(chosen_product, dict):
                stock_update_errors.append(f"Product #{idx+1}: Not a dictionary - {type(chosen_product)}")
                continue
            
            product_name = chosen_product.get('name')
            quantity = chosen_product.get('quantity')
            
            # Validate product_name
            if not product_name:
                stock_update_errors.append(f"Product #{idx+1}: Missing product name")
                continue
            
            if not isinstance(product_name, str) or not product_name.strip():
                stock_update_errors.append(f"Product #{idx+1}: Invalid name (empty or not string)")
                continue
            
            product_name = product_name.strip()
            
            # Validate quantity
            if quantity is None:
                stock_update_errors.append(f"Product '{product_name}': Missing quantity")
                continue
            
            # Handle float quantities (round down to int)
            if isinstance(quantity, float):
                quantity = int(quantity)
                if quantity <= 0:
                    stock_update_errors.append(f"Product '{product_name}': Invalid quantity (float converted to {quantity})")
                    continue
            elif isinstance(quantity, str):
                try:
                    quantity = int(float(quantity))  # Handle "5.0" strings
                    if quantity <= 0:
                        stock_update_errors.append(f"Product '{product_name}': Invalid quantity (string converted to {quantity})")
                        continue
                except (ValueError, TypeError):
                    stock_update_errors.append(f"Product '{product_name}': Cannot convert quantity '{quantity}' to integer")
                    continue
            else:
                try:
                    quantity = int(quantity)
                    if quantity <= 0:
                        stock_update_errors.append(f"Product '{product_name}': Invalid quantity ({quantity})")
                        continue
                except (ValueError, TypeError):
                    stock_update_errors.append(f"Product '{product_name}': Invalid quantity type ({type(quantity)})")
                    continue
            
            # Aggregate quantities for same product
            if product_name in product_aggregates:
                product_aggregates[product_name] += quantity
            else:
                product_aggregates[product_name] = quantity
        
        # If any validation failed, abort completely
        if stock_update_errors:
            error_msg = f"⚠️ {t('error', lang)}: Cannot complete order #{order_id}:\n" + "\n".join(stock_update_errors)
            logger.error(f"❌ order_ready: Validation failed for order {order_id}: {stock_update_errors}")
            await send_message_with_cleanup(update, context, error_msg)
            return
        
        # Now process aggregated products (one entry per unique product name)
        validated_products = []  # Store validated products for update
        
        for product_name, total_quantity in product_aggregates.items():
            # Get product from database
            products = db_client.select('products', {'name': product_name})
            if not products:
                stock_update_errors.append(f"Product '{product_name}': Not found in database")
                continue
            
            product = products[0]
            product_id = product.get('id')
            
            if not product_id:
                stock_update_errors.append(f"Product '{product_name}': Missing ID in database")
                continue
            
            current_stock = product.get('stock', 0)
            
            # Handle None stock (default to 0)
            if current_stock is None:
                current_stock = 0
                logger.warning(f"⚠️ order_ready: Product '{product_name}' has None stock, defaulting to 0")
            
            # Ensure current_stock is integer
            try:
                current_stock = int(current_stock)
            except (ValueError, TypeError):
                logger.error(f"❌ order_ready: Product '{product_name}' has invalid stock type: {type(current_stock)}")
                stock_update_errors.append(f"Product '{product_name}': Invalid stock type in database")
                continue
            
            # Prevent negative stock (using aggregated total_quantity)
            new_stock = current_stock - total_quantity
            if new_stock < 0:
                stock_update_errors.append(
                    f"Product '{product_name}': Insufficient stock ({current_stock} available, {total_quantity} required)"
                )
                continue
            
            # All validations passed for this product - store for update
            validated_products.append({
                'product_id': product_id,
                'product_name': product_name,
                'old_stock': current_stock,
                'new_stock': new_stock,
                'quantity': total_quantity  # Use aggregated quantity
            })
        
        # If any validation failed, abort completely
        if stock_update_errors:
            error_msg = f"⚠️ {t('error', lang)}: Cannot complete order #{order_id}:\n" + "\n".join(stock_update_errors)
            logger.error(f"❌ order_ready: Validation failed for order {order_id}: {stock_update_errors}")
            await send_message_with_cleanup(update, context, error_msg)
            return
        
        # CRITICAL CHECK 4: Re-check order status before updating (race condition protection)
        orders = db_client.select('orders', {'id': order_id})
        if not orders:
            logger.error(f"❌ order_ready: Order {order_id} disappeared during processing")
            await send_message_with_cleanup(update, context, t('order_not_found', lang))
            return
        
        order = orders[0]
        if order.get('status') == 'completed' or order.get('delivered'):
            logger.warning(f"⚠️ order_ready: Order {order_id} was completed by another process (race condition)")
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Order #{order_id} was already completed!"
            )
            return
        
        # All validations passed - update stock for all products
        logger.info(f"✅ order_ready: Updating stock for {len(validated_products)} products")
        for product_update in validated_products:
            # CRITICAL: Re-fetch product to verify current stock before update (race condition protection)
            products_before_update = db_client.select('products', {'id': product_update['product_id']})
            if not products_before_update:
                logger.error(f"❌ order_ready: Product {product_update['product_name']} disappeared before update")
                # Rollback previous stock updates
                for rollback in stock_updates:
                    try:
                        rollback_result = db_client.update('products', {'stock': rollback['old_stock']}, {'id': rollback['product_id']})
                        if rollback_result:
                            logger.info(f"🔄 order_ready: Rolled back stock for {rollback['product_name']}")
                        else:
                            logger.error(f"❌ order_ready: Rollback verification failed for {rollback['product_name']}")
                    except Exception as rollback_error:
                        logger.error(f"❌ order_ready: Rollback failed for {rollback['product_name']}: {repr(rollback_error)}")
                
                await send_message_with_cleanup(
                    update, context, 
                    f"⚠️ {t('error', lang)}: Product '{product_update['product_name']}' disappeared. All changes rolled back."
                )
                return
            
            current_stock_before = products_before_update[0].get('stock', 0)
            if current_stock_before is None:
                current_stock_before = 0
            
            # CRITICAL: Verify stock hasn't changed since validation (race condition check)
            if int(current_stock_before) != product_update['old_stock']:
                logger.warning(f"⚠️ order_ready: Stock changed for '{product_update['product_name']}' - was {product_update['old_stock']}, now {current_stock_before}")
                # Re-calculate new stock based on current value
                new_stock_recalculated = int(current_stock_before) - product_update['quantity']
                if new_stock_recalculated < 0:
                    logger.error(f"❌ order_ready: Insufficient stock after race condition check for '{product_update['product_name']}'")
                    # Rollback previous stock updates
                    for rollback in stock_updates:
                        try:
                            rollback_result = db_client.update('products', {'stock': rollback['old_stock']}, {'id': rollback['product_id']})
                            if rollback_result:
                                logger.info(f"🔄 order_ready: Rolled back stock for {rollback['product_name']}")
                            else:
                                logger.error(f"❌ order_ready: Rollback verification failed for {rollback['product_name']}")
                        except Exception as rollback_error:
                            logger.error(f"❌ order_ready: Rollback failed for {rollback['product_name']}: {repr(rollback_error)}")
                    
                    await send_message_with_cleanup(
                        update, context, 
                        f"⚠️ {t('error', lang)}: Insufficient stock for '{product_update['product_name']}' (race condition detected). All changes rolled back."
                    )
                    return
                
                # Update with recalculated value
                product_update['old_stock'] = int(current_stock_before)
                product_update['new_stock'] = new_stock_recalculated
            
            # Perform stock update
            result = db_client.update('products', 
                {'stock': product_update['new_stock']}, 
                {'id': product_update['product_id']}
            )
            
            # CRITICAL: Verify stock update succeeded
            if not result:
                logger.error(f"❌ order_ready: Stock update failed for product {product_update['product_name']}")
                # Rollback previous stock updates
                for rollback in stock_updates:
                    try:
                        rollback_result = db_client.update('products', {'stock': rollback['old_stock']}, {'id': rollback['product_id']})
                        if rollback_result:
                            logger.info(f"🔄 order_ready: Rolled back stock for {rollback['product_name']}")
                        else:
                            logger.error(f"❌ order_ready: Rollback verification failed for {rollback['product_name']}")
                    except Exception as rollback_error:
                        logger.error(f"❌ order_ready: Rollback failed for {rollback['product_name']}: {repr(rollback_error)}")
                
                await send_message_with_cleanup(
                    update, context, 
                    f"⚠️ {t('error', lang)}: Failed to update stock for '{product_update['product_name']}'. All changes rolled back."
                )
                return
            
            # CRITICAL: Verify stock was actually updated correctly (post-update verification)
            products_after_update = db_client.select('products', {'id': product_update['product_id']})
            if products_after_update:
                actual_stock_after = products_after_update[0].get('stock', 0)
                if actual_stock_after is None:
                    actual_stock_after = 0
                
                if int(actual_stock_after) != product_update['new_stock']:
                    logger.error(f"❌ order_ready: Stock verification failed for '{product_update['product_name']}' - expected {product_update['new_stock']}, got {actual_stock_after}")
                    # Rollback ALL updates (including this failed one)
                    for rollback in stock_updates:
                        try:
                            rollback_result = db_client.update('products', {'stock': rollback['old_stock']}, {'id': rollback['product_id']})
                            if rollback_result:
                                logger.info(f"🔄 order_ready: Rolled back stock for {rollback['product_name']}")
                            else:
                                logger.error(f"❌ order_ready: Rollback verification failed for {rollback['product_name']}")
                        except Exception as rollback_error:
                            logger.error(f"❌ order_ready: Rollback failed for {rollback['product_name']}: {repr(rollback_error)}")
                    
                    # Rollback this update too
                    try:
                        db_client.update('products', {'stock': product_update['old_stock']}, {'id': product_update['product_id']})
                    except:
                        pass
                    
                    await send_message_with_cleanup(
                        update, context, 
                        f"⚠️ {t('error', lang)}: Stock verification failed for '{product_update['product_name']}'. All changes rolled back."
                    )
                    return
            else:
                logger.error(f"❌ order_ready: Product {product_update['product_name']} disappeared after update")
                # Rollback
                for rollback in stock_updates:
                    try:
                        rollback_result = db_client.update('products', {'stock': rollback['old_stock']}, {'id': rollback['product_id']})
                        if rollback_result:
                            logger.info(f"🔄 order_ready: Rolled back stock for {rollback['product_name']}")
                    except Exception as rollback_error:
                        logger.error(f"❌ order_ready: Rollback failed: {repr(rollback_error)}")
                
                await send_message_with_cleanup(
                    update, context, 
                    f"⚠️ {t('error', lang)}: Product '{product_update['product_name']}' disappeared after update. All changes rolled back."
                )
                return
            
            # Track successful update for potential rollback
            stock_updates.append(product_update)
            logger.info(f"✅ order_ready: Stock updated for '{product_update['product_name']}': {product_update['old_stock']} -> {product_update['new_stock']}")
        
        # CRITICAL CHECK 5: Update order status and verify success
        courier_name = f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip()
        courier_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
        
        # Use consistent datetime format (ISO format for Supabase compatibility)
        delivered_timestamp = datetime.datetime.now().isoformat()
        
        order_update_result = db_client.update('orders', {
            'courier_id': update.effective_user.id,
            'courier_name': courier_name,
            'courier_username': courier_username,
            'status': 'completed',  # Simple string for database consistency
            'delivered': delivered_timestamp
        }, {'id': order_id})
        
        # CRITICAL: Verify order update succeeded
        if not order_update_result:
            logger.error(f"❌ order_ready: Order update failed for order {order_id} - ROLLING BACK STOCK!")
            # Rollback ALL stock updates
            for rollback in stock_updates:
                try:
                    rollback_result = db_client.update('products', {'stock': rollback['old_stock']}, {'id': rollback['product_id']})
                    if rollback_result:
                        # Verify rollback succeeded
                        verify_products = db_client.select('products', {'id': rollback['product_id']})
                        if verify_products and int(verify_products[0].get('stock', 0) or 0) == rollback['old_stock']:
                            logger.info(f"🔄 order_ready: Verified rollback for {rollback['product_name']}")
                        else:
                            logger.error(f"❌ order_ready: Rollback verification failed for {rollback['product_name']}")
                    else:
                        logger.error(f"❌ order_ready: Rollback failed for {rollback['product_name']} - update returned empty")
                except Exception as rollback_error:
                    logger.error(f"❌ order_ready: Rollback exception for {rollback['product_name']}: {repr(rollback_error)}")
            
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Failed to update order #{order_id}. All stock changes have been rolled back."
            )
            return
        
        # CRITICAL: Verify order was actually updated
        orders_after_update = db_client.select('orders', {'id': order_id})
        if not orders_after_update:
            logger.error(f"❌ order_ready: Order {order_id} disappeared after update - ROLLING BACK STOCK!")
            # Rollback stock
            for rollback in stock_updates:
                try:
                    db_client.update('products', {'stock': rollback['old_stock']}, {'id': rollback['product_id']})
                except:
                    pass
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Order disappeared after update. All changes rolled back."
            )
            return
        
        order_after = orders_after_update[0]
        if order_after.get('status') != 'completed' or not order_after.get('delivered'):
            logger.error(f"❌ order_ready: Order {order_id} status not updated correctly - status={order_after.get('status')}, delivered={order_after.get('delivered')}")
            # Rollback stock
            for rollback in stock_updates:
                try:
                    db_client.update('products', {'stock': rollback['old_stock']}, {'id': rollback['product_id']})
                except:
                    pass
            await send_message_with_cleanup(
                update, context, 
                f"⚠️ {t('error', lang)}: Order status update verification failed. All changes rolled back."
            )
            return
        
        logger.info(f"✅ order_ready: Successfully completed order {order_id}")
        
        # Refresh order from database to get updated data
        orders = db_client.select('orders', {'id': order_id})
        if orders:
            order_dict = orders[0]
        else:
            logger.warning(f"⚠️ order_ready: Could not refresh order {order_id} after update")
            order_dict = {}  # Fallback
        
        # Convert to object for form_confirm_order_courier - MUST have get_products() method!
        from funcs.utils import create_order_obj
        order_obj = create_order_obj(order_dict)
        
        # Update message in courier group
        try:
            text = await form_confirm_order_courier(order_obj, lang)
            await update.effective_message.edit_text(text=text, parse_mode=ParseMode.HTML)
        except Exception as msg_error:
            logger.error(f"❌ order_ready: Failed to update message for order {order_id}: {repr(msg_error)}")
            import traceback
            traceback.print_exc()
            # Order is already completed, so just log the error
        
        # Send notification to admin group
        from db.db import get_bot_setting
        admin_chat = get_bot_setting('admin_chat') or links.ADMIN_CHAT
        if admin_chat:
            try:
                # Send BILINGUAL message to admin group (RU + HE)
                text = await form_confirm_order_courier_info(order_obj, 'ru')  # lang param ignored - now bilingual
                await context.bot.send_message(admin_chat, text, parse_mode=ParseMode.HTML)
            except Exception as admin_msg_error:
                logger.error(f"❌ order_ready: Failed to send admin notification for order {order_id}: {repr(admin_msg_error)}")
                import traceback
                traceback.print_exc()
                # Order is already completed, so just log the error
            
    except ValueError as e:
        logger.error(f"❌ order_ready: ValueError for order {order_id}: {repr(e)}")
        # Rollback stock if any updates were made
        if stock_updates:
            for rollback in stock_updates:
                try:
                    rollback_result = db_client.update('products', {'stock': rollback['old_stock']}, {'id': rollback['product_id']})
                    if rollback_result:
                        logger.info(f"🔄 order_ready: Rolled back stock for {rollback['product_name']} after ValueError")
                    else:
                        logger.error(f"❌ order_ready: Rollback failed for {rollback['product_name']} after ValueError - update returned empty")
                except Exception as rollback_error:
                    logger.error(f"❌ order_ready: Rollback exception: {repr(rollback_error)}")
        
        await send_message_with_cleanup(
            update, context, 
            f"⚠️ {t('error', lang)}: Invalid data format: {repr(e)}"
        )
    except Exception as e:
        logger.error(f"❌ order_ready: Unexpected error for order {order_id}: {repr(e)}", exc_info=True)
        import traceback
        traceback.print_exc()
        
        # Rollback stock if any updates were made
        if stock_updates:
            for rollback in stock_updates:
                try:
                    rollback_result = db_client.update('products', {'stock': rollback['old_stock']}, {'id': rollback['product_id']})
                    if rollback_result:
                        logger.info(f"🔄 order_ready: Rolled back stock for {rollback['product_name']} after exception")
                    else:
                        logger.error(f"❌ order_ready: Rollback failed for {rollback['product_name']} after exception - update returned empty")
                except Exception as rollback_error:
                    logger.error(f"❌ order_ready: Rollback exception: {repr(rollback_error)}")
        
        await send_message_with_cleanup(
            update, context, 
            f"⚠️ {t('error', lang)}: Unexpected error occurred. All changes have been rolled back."
        )


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
async def show_rest_from_last_day(update: Update, context: ContextTypes.DEFAULT_TYPE, from_back_button: bool = False) -> None:
    """
    [📊 Текущий остаток на складе]
    • Показывает, сколько осталось от каждого товара
    • Сколько уже выдано
    • Возможность ручного редактирования остатков
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Add to navigation history ONLY if not coming from back button
    if not from_back_button:
        add_to_navigation_history(context, 'stock_list_menu')

    # הוספה: שמירת מידע על מלאי נוכחי
    context.user_data['current_inventory_view'] = 'stock_list'
    context.user_data['came_from_inventory'] = True  # דגל חדש

    inline_markup = get_products_markup_left_edit_stock(lang)

    await send_message_with_cleanup(update, context, t('edit_stock_or_delete', lang), reply_markup=inline_markup)


@is_stockman
async def show_menu_edit_crude_stock(update: Update, context: ContextTypes.DEFAULT_TYPE, from_back_button: bool = False) -> None:
    """
    Редактирование продуктов с сырьём.
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Clean previous message
    await clean_previous_message(update, context)

    # Add to navigation history ONLY if not coming from back button
    if not from_back_button:
        add_to_navigation_history(context, 'stock_menu')

    # הוספה: שמירת מידע על מלאי חומר גלם (גם הוא מלאי)
    context.user_data['current_inventory_view'] = 'crude_stock'
    context.user_data['came_from_inventory'] = True  # דגל חשוב גם כאן

    inline_markup = get_products_markup_left_edit_stock_crude(lang)

    msg = await send_message_with_cleanup(update, context, t('edit_crude_stock_prompt', lang), reply_markup=inline_markup)
    
    # Save ID for future cleanup
    save_message_id(context, msg.message_id)


async def handle_conversation_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    טיפול בכפתור חזור בתוך ConversationHandler

    כשמשתמש לוחץ על חזור בזמן שהוא בתוך conversation,
    אנחנו צריכים לטפל בזה בצורה שונה מניווט רגיל.

    הפונקציה מזהה את סוג ה-conversation ומפנה לטיפול המתאים:
    - edit_product: חזרה לרשימת מלאי
    - add_product: חזרה לתפריט מלאי
    - new_order: חזרה לתפריט ראשי
    - וכו'
    """
    import logging
    logger = logging.getLogger(__name__)

    # זיהוי סוג ה-conversation
    conversation_name = context.user_data.get('conversation_name')

    logger.info(f"🔙 Handling back button in conversation: {conversation_name}")

    try:
        if 'edit_product_data' in context.user_data:
            # אנחנו בעריכת מוצר - חזרה לרשימת מלאי
            logger.debug("🔙 Back from edit_product conversation")
            from handlers.edit_product_handler import cancel
            await cancel(update, context)

        elif 'add_product' in context.user_data:
            # אנחנו בהוספת מוצר - חזרה לתפריט מלאי
            logger.debug("🔙 Back from add_product conversation")
            from handlers.manage_stock_handler import cancel_stock_management
            await cancel_stock_management(update, context)

        elif 'new_order_data' in context.user_data:
            # אנחנו בהזמנה חדשה - חזרה לתפריט ראשי
            logger.debug("🔙 Back from new_order conversation")
            await start(update, context)

        elif 'edit_crude_data' in context.user_data:
            # אנחנו בעריכת מלאי - חזרה לתפריט מלאי
            logger.debug("🔙 Back from edit_crude conversation")
            await show_menu_edit_crude_stock(update, context, from_back_button=True)

        elif 'template_data' in context.user_data:
            # אנחנו בעריכת תבנית - חזרה לתפריט תבניות
            logger.debug("🔙 Back from template conversation")
            from funcs.bot_funcs import show_templates
            await show_templates(update, context)

        elif 'session_data' in context.user_data:
            # אנחנו בניהול סשנים - חזרה לתפריט סשנים
            logger.debug("🔙 Back from session conversation")
            await show_tg_sessions(update, context)

        elif 'create_template_data' in context.user_data:
            # אנחנו ביצירת תבנית - חזרה לתפריט תבניות
            logger.debug("🔙 Back from create_template conversation")
            from funcs.bot_funcs import show_templates
            await show_templates(update, context)

        elif 'send_template_data' in context.user_data:
            # אנחנו בשליחת תבנית - חזרה לתפריט תבניות
            logger.debug("🔙 Back from send_template conversation")
            from funcs.bot_funcs import show_templates
            await show_templates(update, context)

        elif 'end_shift_data' in context.user_data:
            # אנחנו בסיום משמרת - חזרה לתפריט ראשי
            logger.debug("🔙 Back from end_shift conversation")
            await start(update, context)

        elif 'change_links_data' in context.user_data:
            # אנחנו בשינוי קישורים - חזרה לתפריט ניהול
            logger.debug("🔙 Back from change_links conversation")
            await show_admin_action_kb(update, context, from_back_button=True)

        elif 'make_session_data' in context.user_data:
            # אנחנו ביצירת סשן - חזרה לתפריט סשנים
            logger.debug("🔙 Back from make_session conversation")
            await show_tg_sessions(update, context)

        elif 'add_staff_data' in context.user_data:
            # אנחנו בהוספת עובד - חזרה לתפריט ניהול
            logger.debug("🔙 Back from add_staff conversation")
            await show_admin_action_kb(update, context, from_back_button=True)

        elif 'delay_min_data' in context.user_data:
            # אנחנו בעיכוב הזמנה - חזרה לתפריט השליח
            logger.debug("🔙 Back from delay conversation")
            # צריך למצוא את order_id ולהציג את תפריט הפעולות
            order_id = context.user_data.get('delay_min_data', {}).get('order_id')
            lang = context.user_data.get('delay_min_data', {}).get('lang', 'ru')
            if order_id:
                try:
                    from funcs.bot_funcs import form_courier_action_kb
                    markup = await form_courier_action_kb(order_id, lang)
                    start_msg = context.user_data.get('delay_min_data', {}).get('start_msg')
                    if start_msg:
                        await start_msg.edit_reply_markup(markup)
                        logger.debug(f"🔙 Restored courier action menu for order {order_id}")
                    else:
                        logger.warning("🔙 No start_msg found for delay conversation")
                except Exception as e:
                    logger.error(f"🔙 Error restoring courier menu: {e}")
                    await start(update, context)
            else:
                logger.warning("🔙 No order_id found in delay conversation")
                await start(update, context)

        elif 'collect_order_data' in context.user_data:
            # אנחנו באיסוף הזמנה - חזרה לתפריט הראשי (ההזמנה לא נשמרה)
            logger.debug("🔙 Back from collect_order conversation")
            # ניקוי הנתונים ומעבר לתפריט הראשי
            start_msg = context.user_data.get('collect_order_data', {}).get('start_msg')
            if start_msg:
                try:
                    await start_msg.delete()
                    logger.debug("🔙 Deleted collect_order start message")
                except Exception as e:
                    logger.debug(f"🔙 Could not delete collect_order start message: {e}")

            # ניקוי הנתונים
            if 'collect_order_data' in context.user_data:
                del context.user_data['collect_order_data']
                logger.debug("🔙 Cleaned collect_order_data")

            # חזרה לתפריט הראשי
            await start(update, context)

        else:
            # conversation לא מזוהה - חזרה לעמוד הבית
            logger.warning(f"🔙 Unknown conversation type, falling back to home")
            await start(update, context)

    except Exception as e:
        logger.error(f"❌ Error in handle_conversation_back: {e}")
        # במקרה של שגיאה, חזרה לעמוד הבית
        await start(update, context)


# Central navigation handler
async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle navigation buttons (back and home) - IMPROVED for conversations
    CRITICAL: Handles errors gracefully - messages may already be deleted

    שיפור קריטי: הפונקציה עכשיו יודעת להבדיל בין:
    1. ניווט רגיל בין תפריטים (כשהמשתמש לא בתוך conversation)
    2. ניווט בתוך conversation (כשהמשתמש בעיצומו של תהליך)
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    try:
        if update.callback_query.data == "back":
            print(f"🔍 BACK BUTTON PRESSED - navigation_history: {context.user_data.get('navigation_history', 'NOT SET')}")

            # הוספה: בדיקה אם אנחנו בתוך conversation
            from funcs.utils import is_in_conversation
            if is_in_conversation(context):
                # טיפול מיוחד ל-conversation
                await handle_conversation_back(update, context)
                return

            # לוגיקה רגילה של ניווט
            previous_menu = get_previous_menu(context)
            print(f"🔍 get_previous_menu returned: {previous_menu}")
            if not previous_menu:
                # אין היסטוריה - חזור לעמוד הבית
                # send_message_with_cleanup in start() will handle cleanup
                print(f"🔍 No previous menu - going to start()")
                await start(update, context)
                return

            # Temporarily store the menu we're going back to
            menu_name = previous_menu['menu']
            print(f"🔍 Going back to menu: {menu_name}")

            # send_message_with_cleanup in menu functions will handle cleanup
            # חזרה לתפריט הקודם - Pass from_back_button=True to prevent re-adding to history!
            if menu_name == 'main_menu':
                print(f"🔍 Calling start() for main_menu")
                await start(update, context)
            elif menu_name == 'stock_menu':
                print(f"🔍 Calling show_menu_edit_crude_stock() for stock_menu")
                await show_menu_edit_crude_stock(update, context, from_back_button=True)
            elif menu_name == 'stock_list_menu':
                await show_rest_from_last_day(update, context, from_back_button=True)
            elif menu_name == 'admin_menu':
                await show_admin_action_kb(update, context, from_back_button=True)
            elif menu_name == 'orders_filter_menu':
                await all_orders(update, context, from_back_button=True)
            elif menu_name == 'manage_roles_menu':
                await manage_roles(update, context, from_back_button=True)
            elif menu_name == 'security_menu':
                await show_security_menu(update, context, from_back_button=True)
            elif menu_name == 'daily_profit_menu':
                await show_daily_profit_options(update, context, from_back_button=True)
            elif menu_name == 'quick_reports_menu':
                await quick_reports(update, context, from_back_button=True)
            elif menu_name == 'tg_sessions_menu':
                await show_tg_sessions(update, context, from_back_button=True)
            elif menu_name == 'list_products_menu':
                # חזרה לתפריט ניהול מלאי
                from handlers.manage_stock_handler import manage_stock
                await manage_stock(update, context, from_back_button=True)
            else:
                # תפריט לא מוכר - חזור לעמוד הבית
                await start(update, context)
        
        elif update.callback_query.data == "home":
            # ניקוי היסטוריה וחזרה לעמוד הבית
            if 'navigation_history' in context.user_data:
                context.user_data['navigation_history'].clear()
            
            # ניקוי נתוני ConversationHandler אם יש
            for key in list(context.user_data.keys()):
                if key.endswith("_data"):
                    del context.user_data[key]
                    print(f"🔍 Cleaned up conversation data: {key}")
            
            # send_message_with_cleanup in start() will handle cleanup
            await start(update, context)
    except Exception as e:
        # Critical error handling - ensure user gets main menu even if navigation fails
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ handle_navigation: Critical error: {repr(e)}")
        import traceback
        traceback.print_exc()
        
        # Fallback: try to show main menu
        try:
            await start(update, context)
        except Exception as e2:
            logger.error(f"❌ handle_navigation: Failed to show main menu after error: {repr(e2)}")
            # Last resort: send error message
            try:
                await update.callback_query.message.reply_text(
                    f"⚠️ {t('error', lang)}: Navigation error. Please try /start"
                )
            except:
                pass  # If even this fails, give up

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
