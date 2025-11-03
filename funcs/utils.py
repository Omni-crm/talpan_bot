from telegram.ext import CallbackQueryHandler, TypeHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from db.db import Status, Order, Shift, ShiftStatus, Product
from config.config import *
from config.translations import t, get_user_lang
import datetime
import pandas as pd
from io import BytesIO
import json


def create_order_obj(order_dict: dict):
    """
    Create Order object with get_products() method for compatibility with form_confirm_order functions.
    
    This utility ensures all Order objects used with form_confirm_order_courier, 
    form_confirm_order_courier_info, and form_confirm_order have the required get_products() method.
    
    Args:
        order_dict: Dictionary containing order data from database
        
    Returns:
        Order object with get_products() method
    """
    class OrderObj:
        def __init__(self, data):
            for k, v in data.items():
                if k == 'status':
                    # Create Status-like object for compatibility
                    setattr(self, k, type('Status', (), {'value': v})())
                else:
                    setattr(self, k, v)
        
        def get_products(self):
            """Get products from order's products field (JSON string)"""
            if not hasattr(self, 'products'):
                return []
            if isinstance(self.products, str):
                try:
                    parsed = json.loads(self.products)
                    return parsed if isinstance(parsed, list) else []
                except (json.JSONDecodeError, TypeError):
                    return []
            return self.products if isinstance(self.products, list) else []
    
    return OrderObj(order_dict)


async def cleanup_old_messages(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    פונקציה כללית למחיקת הודעות קודמות
    Handles deletion gracefully - ignores errors if messages already deleted
    """
    if context.user_data.get("msgs_to_delete"):
        msgs = context.user_data["msgs_to_delete"]
        for msg in msgs:
            try:
                await msg.delete()
            except (BadRequest, Forbidden):
                # Message already deleted or no permission - silently ignore
                pass
            except Exception as e:
                # Other errors - log but don't crash
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Could not delete message in cleanup_old_messages: {e}")
        context.user_data["msgs_to_delete"] = []


def save_message_for_cleanup(context: ContextTypes.DEFAULT_TYPE, msg) -> None:
    """
    פונקציה לשמירת הודעה למחיקה עתידית
    """
    if not context.user_data.get("msgs_to_delete"):
        context.user_data["msgs_to_delete"] = []
    context.user_data["msgs_to_delete"].append(msg)


async def cleanup_start_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    ניקוי חכם של הודעות /start ישנות
    - מוחק את הודעת /start של המשתמש הנוכחי
    - בודק 30 ההודעות האחרונות ומחק הודעות /start ישנות של אותו משתמש
    - משאיר הודעת /start אחת אחרונה לכל היותר

    זה חשוב לחוויית המשתמש - מונע הצטברות של הודעות /start בצ'אט
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # מחיקת הודעת המשתמש הנוכחית אם היא /start
        if update.message and update.message.text == '/start':
            try:
                await update.message.delete()
                logger.debug(f"🧹 Deleted current /start message from user {update.effective_user.id}")
            except (BadRequest, Forbidden) as e:
                logger.debug(f"Could not delete current /start message: {e}")
            except Exception as e:
                logger.error(f"Unexpected error deleting current /start message: {e}")

        # קבלת 30 ההודעות האחרונות בצ'אט
        chat_id = update.effective_chat.id
        try:
            recent_messages = await context.bot.get_chat_history(
                chat_id=chat_id,
                limit=30
            )

            start_messages = []
            for msg in recent_messages:
                if (msg.text == '/start' and
                    msg.from_user and
                    msg.from_user.id == update.effective_user.id):
                    start_messages.append(msg)

            # מוחק את כל הודעות /start חוץ מהאחרונה (למקרה שיש כמה)
            deleted_count = 0
            for msg in start_messages[:-1]:  # משאיר את האחרונה
                try:
                    await msg.delete()
                    deleted_count += 1
                except (BadRequest, Forbidden):
                    # הודעה כבר נמחקה או אין הרשאה
                    pass
                except Exception as e:
                    logger.error(f"Error deleting old /start message: {e}")

            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old /start messages from user {update.effective_user.id}")

        except Exception as e:
            logger.error(f"Could not get chat history for start cleanup: {e}")

    except Exception as e:
        logger.error(f"Critical error in cleanup_start_messages: {e}")
        # לא נזרוק שגיאה - פונקציית ניקוי לא צריכה להפיל את הבוט


def is_in_conversation(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    בודק אם המשתמש נמצא כרגע בתוך ConversationHandler

    זה חשוב לניווט - כפתורי חזור צריכים להתנהג שונה בתוך conversation
    לעומת ניווט רגיל בין תפריטים.

    הבדיקה מבוססת על נתוני context שמאפיינים conversation פעיל:
    - add_product: הוספת מוצר חדש
    - edit_product_data: עריכת מוצר קיים
    - new_order_data: יצירת הזמנה חדשה
    - edit_crude_data: עריכת מלאי
    - template_data: עריכת תבנית
    - session_data: ניהול סשנים

    Returns:
        bool: True אם המשתמש בתוך conversation, False אחרת
    """
    import logging
    logger = logging.getLogger(__name__)

    # רשימת כל המפתחות שמציינים conversation פעיל
    conversation_indicators = [
        'add_product',              # הוספת מוצר חדש
        'edit_product_data',        # עריכת מוצר קיים
        'new_order_data',           # יצירת הזמנה חדשה
        'edit_crude_data',          # עריכת מלאי
        'template_data',            # עריכת תבנית
        'session_data',             # ניהול סשנים
        'create_template_data',     # יצירת תבנית חדשה
        'send_template_data',       # שליחת תבנית
        'end_shift_data',           # סיום משמרת
        'change_links_data',        # שינוי קישורים
        'make_session_data',        # יצירת סשן
        'add_staff_data',           # הוספת עובד
        'auth_data',                # אימות
        'choose_min_data',          # בחירת דקות
        'collect_order_data',       # איסוף הזמנה
        'create_new_shab_data',     # יצירת תבנית חדשה
        'dealing_template_data',    # טיפול בתבנית
        'delay_min_data',           # עיכוב דקות
        'edit_group_link_data',     # עריכת קישור קבוצה
        'edit_product_with_crude_data', # עריכת מוצר עם חומר גלם
        'pending_order_with_data'   # הזמנה ממתינה
    ]

    for indicator in conversation_indicators:
        if indicator in context.user_data:
            logger.debug(f"🗣️ User detected in conversation: {indicator}")
            return True

    logger.debug("📱 User not in conversation - regular navigation")
    return False


async def send_message_with_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    """
    פונקציה כללית לשליחת הודעה עם ניקוי אוטומטי של הודעות קודמות
    CRITICAL: Handles errors gracefully - messages may already be deleted
    """
    # מחיקת הודעות קודמות (handles errors gracefully)
    await cleanup_old_messages(context)
    
    # שליחת הודעה חדשה
    try:
        if update.callback_query:
            msg = await update.callback_query.message.reply_text(text, **kwargs)
        else:
            msg = await update.effective_message.reply_text(text, **kwargs)
        
        # שמירת הודעה למחיקה עתידית
        save_message_for_cleanup(context, msg)
        return msg
    except Exception as e:
        # If reply fails, try alternative method
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send message in send_message_with_cleanup: {e}")
        # Try sending directly to chat
        if update.callback_query:
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                **kwargs
            )
        else:
            msg = await update.effective_message.reply_text(text, **kwargs)
        save_message_for_cleanup(context, msg)
        return msg


async def edit_message_with_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, message_to_edit=None, **kwargs):
    """
    פונקציה כללית לעריכת הודעה עם ניקוי אוטומטי של הודעות קודמות
    CRITICAL: Handles errors gracefully - if edit fails, sends new message instead
    
    Args:
        update: Telegram Update object
        context: Bot context
        text: Text to set in the message
        message_to_edit: Optional - specific message to edit. If not provided, tries to infer from update.
        **kwargs: Additional arguments for edit_text
    """
    # מחיקת הודעות קודמות (handles errors gracefully)
    await cleanup_old_messages(context)
    
    # עריכת הודעה קיימת
    try:
        if message_to_edit:
            # If a specific message was provided, edit it
            msg = await message_to_edit.edit_text(text, **kwargs)
        elif update.callback_query:
            # If it's a callback query, edit the message that contains the button
            msg = await update.callback_query.message.edit_text(text, **kwargs)
        else:
            # WARNING: This will fail if update.effective_message is from the user!
            # Only works if the effective_message is from the bot
            msg = await update.effective_message.edit_text(text, **kwargs)
        
        # שמירת הודעה למחיקה עתידית
        save_message_for_cleanup(context, msg)
        return msg
    except (BadRequest, Forbidden) as e:
        # Message was deleted or can't be edited - send new message instead
        # This is expected in some cases, so don't log as error
        import logging
        logger = logging.getLogger(__name__)
        if 'message not found' not in str(e).lower() and 'message to edit not found' not in str(e).lower():
            logger.debug(f"Could not edit message, sending new: {e}")
        
        # Send new message instead
        if update.callback_query:
            msg = await update.callback_query.message.reply_text(text, **kwargs)
        else:
            msg = await update.effective_message.reply_text(text, **kwargs)
        
        save_message_for_cleanup(context, msg)
        return msg
    except Exception as e:
        # Other unexpected errors - log and try to send new message
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Unexpected error in edit_message_with_cleanup: {e}")
        
        # Try sending new message as fallback
        try:
            if update.callback_query:
                msg = await update.callback_query.message.reply_text(text, **kwargs)
            else:
                msg = await update.effective_message.reply_text(text, **kwargs)
            save_message_for_cleanup(context, msg)
            return msg
        except Exception as e2:
            logger.error(f"Failed to send new message after edit failure: {e2}")
            raise


async def edit_conversation_message(message_to_edit, text: str, **kwargs):
    """
    פונקציה פשוטה לעריכת הודעה ב-ConversationHandler
    ללא cleanup אוטומטי שיכול למחוק את ההודעה שאנחנו רוצים לערוך!
    
    Args:
        message_to_edit: The message object to edit
        text: Text to set in the message
        **kwargs: Additional arguments for edit_text (reply_markup, parse_mode, etc.)
    
    Returns:
        The edited message
    """
    return await message_to_edit.edit_text(text, **kwargs)


def dicts_to_xlsx(dicts_list):
    df = pd.DataFrame(dicts_list)
    
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)  # Move pointer to beginning of file
    return output


async def send_shift_start_msg(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = 'ru'):
    """
    Example message in control group:

    Start of work day – 17.04.2025
    Operator: @Vanillanew

    Initial stock (packaged):
    🔴 12 | ⚫️ 8 | 🛍️ 10 | 🍿 6
    """
    print(f"🔧 send_shift_start_msg called")
    from db.db import db_client, get_opened_shift
    import json
    
    shift = Shift()
    shift.operator_id = update.effective_user.id
    shift.operator_username = update.effective_user.username
    shift.status = ShiftStatus.opened
    print(f"🔧 Shift object created: ID={shift.operator_id}, Status={shift.status}")
    
    # Using Supabase only
    shift_data = {
        'operator_id': shift.operator_id,
        'operator_username': shift.operator_username,
        'status': shift.status.value,
        'products_start': json.dumps(Shift.set_products()),
        'opened_time': datetime.datetime.now().isoformat()
    }
    print(f"🔧 Inserting shift to Supabase...")
    saved_shift = db_client.insert('shifts', shift_data)
    print(f"🔧 Insert response: {saved_shift}")
    
    # Handle response
    if not saved_shift or 'id' not in saved_shift:
        print(f"❌ Error creating shift: {saved_shift}")
        await update.effective_message.reply_text("❌ Error starting shift")
        return
    
    print(f"🔧 Shift created with ID: {saved_shift['id']}")
    shift.id = saved_shift['id']
    shift.opened_time = datetime.datetime.fromisoformat(saved_shift['opened_time'])
    
    # Get products from the saved shift data
    shift.products_start = shift_data['products_start']
    print(f"🔧 Getting products from shift...")
    products_text = " | ".join([((product.get("name") + ' ' + str(product.get("stock")))) for product in shift.get_products()])
    print(f"🔧 Products text: {products_text}")

    # הוספת RTL mark לתחילת ההודעה אם בעברית
    rtl = '\u200F' if lang == 'he' else ''
    
    msg = f"""{rtl}<b>{t("shift_start_title", lang)} –</b> <i>{shift.opened_time.strftime("%d.%m.%Y, %H:%M:%S")}</i>
<b>{t("operator", lang)}:</b> <i>{update.effective_user.first_name} @{update.effective_user.username}</i>

<b>{t("initial_stock", lang)}:</b>
{products_text}
    """
    
    try:
        from db.db import get_bot_setting
        admin_chat = get_bot_setting('admin_chat') or links.ADMIN_CHAT
        if admin_chat:
            await context.bot.send_message(admin_chat, msg, parse_mode=ParseMode.HTML,)
    except Exception as e:
        await update.effective_message.reply_text(repr(e))
    
    # החזרה למסך הראשי
    print(f"🔧 Returning to main menu...")
    from config.kb import build_start_menu
    reply_markup = await build_start_menu(update.effective_user.id)
    print(f"🔧 Main menu built")
    await send_message_with_cleanup(update, context, t("main_menu", lang), reply_markup=reply_markup)
    print(f"🔧 Main menu sent - shift start complete!")


async def form_confirm_order(order: Order, lang: str = 'ru') -> str:
    products = order.get_products()
    print(products)

    qty_text = t("units", lang)
    products_text = ", ".join([f"{product['name']} - {product['quantity']} {qty_text} - {product['total_price']}₪" for product in products])

    price_all_text = sum([(product['total_price']) for product in products])

    # הוספת RTL mark לתחילת ההודעה אם בעברית
    rtl = '\u200F' if lang == 'he' else ''
    
    msg = f"""{rtl}{t("order_id", lang).format(order.id if order.id else '')}
{t("client_name", lang).format(order.client_name)}
{t("client_username", lang).format(order.client_username)}
{t("client_phone", lang).format(order.client_phone)}
{t("address", lang).format(order.address)}
{t("products", lang).format(products_text)}
{t("total_price", lang).format(price_all_text)}

{(t("order_status", lang).format(order.status if isinstance(order.status, str) else order.status.value) if order.status else '')}
"""

    return msg

async def form_confirm_order_courier_info(order: Order, lang: str = 'ru') -> str:
    """
    Format order for ADMIN GROUP - BILINGUAL (RU + HE)
    Used when sending to admin group chat with full courier info
    """
    products = order.get_products()
    print(products)

    # Get text in both languages
    qty_text_ru = t("units", 'ru')
    qty_text_he = t("units", 'he')
    
    products_text_ru = ", ".join([f"{product['name']} - {product['quantity']} {qty_text_ru} - {product['total_price']}₪/{qty_text_ru}" for product in products])
    products_text_he = ", ".join([f"{product['name']} - {product['quantity']} {qty_text_he} - {product['total_price']}₪/{qty_text_he}" for product in products])

    price_all_text = sum([(product['total_price']) for product in products])
    
    # Bilingual message - Russian + Hebrew
    msg = f"""<b>Заказ #{order.id if order.id else ''} | הזמנה #{order.id if order.id else ''}</b>

<b>Имя клиента | שם לקוח:</b> {order.client_name}
<b>Username клиента | יוזרניים לקוח:</b> {order.client_username}
<b>Телефон клиента | טלפון לקוח:</b> {order.client_phone}
<b>Адрес | כתובת:</b> {order.address}
<b>Товары | מוצרים:</b>
  🇷🇺 {products_text_ru}
  🇮🇱 {products_text_he}
<b>Общая цена | מחיר כולל:</b> {price_all_text}₪

<b>Имя курьера | שם שליח:</b> {order.courier_name}
<b>Username курьера | יוזרניים שליח:</b> {order.courier_username}
<b>ID курьера | מזהה שליח:</b> {order.courier_id}
{(f'<b>Время доставки | זמן הגעה:</b> {order.courier_minutes} мин / דק') if order.courier_minutes else ''}

{(f'<b>Причина задержки | סיבת עיכוב:</b> {order.delay_reason}') if order.delay_reason else ''}
{(f'<b>Время задержки | זמן עיכוב:</b> {order.delay_minutes} мин / דק') if order.delay_minutes else ''}

{(f'<b>Статус заказа | סטטוס הזמנה:</b> {order.status if isinstance(order.status, str) else order.status.value}') if order.status else ''}
"""

    return msg

async def form_confirm_order_courier(order: Order, lang: str = 'ru') -> str:
    """
    Format order for COURIER GROUP - BILINGUAL (RU + HE)
    Used when sending to courier group chat
    """
    products = order.get_products()
    print(products)

    # Get text in both languages
    qty_text_ru = t("units", 'ru')
    qty_text_he = t("units", 'he')
    
    products_text_ru = ", ".join([f"{product['name']} - {product['quantity']} {qty_text_ru} - {product['total_price']}₪" for product in products])
    products_text_he = ", ".join([f"{product['name']} - {product['quantity']} {qty_text_he} - {product['total_price']}₪" for product in products])

    price_all_text = sum([(product['total_price']) for product in products])
    
    # Bilingual message - Russian + Hebrew
    msg = f"""<b>Заказ #{order.id if order.id else ''} | הזמנה #{order.id if order.id else ''}</b>

<b>Имя клиента | שם לקוח:</b> {order.client_name}
<b>Адрес | כתובת:</b> {order.address}
<b>Товары | מוצרים:</b>
  🇷🇺 {products_text_ru}
  🇮🇱 {products_text_he}
<b>Общая цена | מחיר כולל:</b> {price_all_text}₪
{(f'<b>Время доставки | זמן הגעה:</b> {order.courier_minutes} мин / דק') if order.courier_minutes else ''}

{(f'<b>Причина задержки | סיבת עיכוב:</b> {order.delay_reason}') if order.delay_reason else ''}
{(f'<b>Время задержки | זמן עיכוב:</b> {order.delay_minutes} мин / דק') if order.delay_minutes else ''}

{(f'<b>Статус заказа | סטטוס הזמנה:</b> {order.status if isinstance(order.status, str) else order.status.value}') if order.status else ''}
"""

    return msg

async def form_notif_delay_short(order: Order, lang: str = 'ru') -> str:
    msg = t('notif_courier_delayed', lang).format(
        order.client_name,
        order.client_username,
        order.delay_reason,
        order.delay_minutes
    )
    
    return msg


async def form_week_report(lang: str = 'ru'):
    """
    Example report:
    Weekly report – April 13-19, 2025  
    Общий доход (брутто): 27,350₪  
    Расходы: 4,600₪  
    Чистая прибыль (нетто): 22,750₪

    Всего выдано:  
    🔴 40 | ⚫️ 22 | 🟢 18 | 🛍️ 25

    Средние показатели:  
    Брутто: 3,907₪ в день | Нетто: 3,250₪ в день
    """
    # Using Supabase only
    from db.db import db_client
    
    now = datetime.datetime.now()
    seven_days_ago = now - datetime.timedelta(days=7)
    
    # Helper function to parse datetime from Supabase format
    def parse_datetime(dt_str):
        """Parse datetime from Supabase format (handles both ISO and PostgreSQL timestamp formats)"""
        if not dt_str:
            return None
        if isinstance(dt_str, datetime.datetime):
            return dt_str
        try:
            # Try ISO format first (with T)
            if 'T' in str(dt_str):
                return datetime.datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
            # Try PostgreSQL format (space instead of T)
            return datetime.datetime.strptime(str(dt_str), '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            # Fallback: try without microseconds
            try:
                return datetime.datetime.strptime(str(dt_str), '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return None
    
    # Fetch all shifts and filter in Python (Supabase doesn't support >= directly)
    all_shifts = db_client.select('shifts', {'status': 'closed'})
    shifts = []
    for shift in all_shifts:
        if shift.get('closed_time'):
            closed_time = parse_datetime(shift['closed_time'])
            if closed_time and closed_time >= seven_days_ago:
                shifts.append(shift)
    # Convert dicts to objects for compatibility
    shift_objects = []
    for s in shifts:
        obj = type('Shift', (), {})()
        obj.brutto = s.get('brutto', 0) or 0
        obj.netto = s.get('netto', 0) or 0
        obj.operator_paid = s.get('operator_paid', 0) or 0
        obj.runner_paid = s.get('runner_paid', 0) or 0
        obj.petrol_paid = s.get('petrol_paid', 0) or 0
        # Fix closure issue - create method that captures s
        def make_get_summary(shift_dict):
            def get_summary():
                summary = shift_dict.get('summary')
                # Handle None, empty string, or invalid JSON
                if summary is None or not isinstance(summary, str) or not summary.strip():
                    return {}
                try:
                    return json.loads(summary)
                except (json.JSONDecodeError, TypeError):
                    return {}
            return get_summary
        obj.get_summary = make_get_summary(s)
        shift_objects.append(obj)
    shifts = shift_objects

    brutto = sum([shift.brutto for shift in shifts]) or 0
    avg_brutto = brutto // 7 if brutto else 0
    netto = sum([shift.netto for shift in shifts]) or 0
    avg_netto = netto // 7 if netto else 0

    expenses = sum([(shift.operator_paid + shift.runner_paid + shift.petrol_paid) for shift in shifts]) or 0

    summaries = [shift.get_summary() for shift in shifts]

    result = {}

    for entry in summaries:
        for key, value in entry.items():
            print(f"Processing {key}: {value}")  # Print key and value
            # Handle None values safely
            total_quantity = value.get('total_quantity') or 0
            total_price = value.get('total_price') or 0
            
            if key not in result:
                result[key] = {'quantity': total_quantity, 'price': total_price}  # Initialize dictionary
            else:
                result[key]['quantity'] += total_quantity  # Add quantity

    result = [f"{k} {v['quantity']}" for k,v in result.items()]
    summary_text = " | ".join(result) if result else t("no_data_for_period", lang)

    rtl = '\u200F' if lang == 'he' else ''
    msg = f"""{rtl}<b>{t('weekly_report_title', lang)} – </b><i>{seven_days_ago.strftime("%d.%m.%Y")} - {now.strftime("%d.%m.%Y")}</i>
<b>{t('total_brutto', lang)}:</b> <i>{brutto}₪</i>
<b>{t('total_expenses', lang)}:</b> <i>{expenses}₪</i>
<b>{t('net_profit', lang)}:</b> <i>{netto}₪</i>

<b>{t('total_issued', lang)}:</b>
{summary_text}

<b>{t('average_indicators', lang)}: </b>
<b>{t('brutto', lang)}:</b> <i>{avg_brutto}₪ {t('per_day', lang)} | {t('netto', lang)}: {avg_netto}₪ {t('per_day', lang)}</i>
"""

    return msg


async def form_notif_ready_order_short(order: Order, lang: str = 'ru') -> str:
    msg = t('notif_courier_on_way', lang).format(
        order.id,
        order.client_name,
        order.client_username,
        order.courier_minutes
    )
    return msg

async def form_end_shift_report(shift: Shift, lang: str = 'ru'):
    """
    Отчет за день – 17.04.2025
    Общая выручка (брутто): 4,800₪  
    Расходы: Оператор – 500₪ | Курьер – 300₪ | Топливо – 200₪  
    Чистая прибыль (нетто): 3,800₪

    Выдано за день:
    🔴 10 | 🛍️ 6 | ⚫️ 4 | 🍿 2
    """

    shift_start_date = shift.opened_time.strftime("%d.%m.%Y")

    rtl = '\u200F' if lang == 'he' else ''
    text = f"""{rtl}<b>{t('daily_report_title', lang)} -</b> {shift_start_date}
<b>{t('total_brutto', lang)}:</b> {shift.brutto}
<b>{t('expenses', lang)}: {t('operator', lang)} –</b> {shift.operator_paid}₪ | {t('courier', lang)} – {shift.runner_paid}₪ | {t('fuel', lang)} – {shift.petrol_paid}₪  
<b>{t('net_profit', lang)}:</b> {shift.netto}₪

<b>{t('issued_today', lang)}:</b>
{shift.products_fetched_text}
"""
    
    return text


async def form_daily_profit_report(date_option: str, lang: str = 'ru') -> str:
    """
    יצירת דוח רווח יומי מפורט
    
    Args:
        date_option: 'today' או 'yesterday'
        lang: שפה ('ru' או 'he')
    
    Returns:
        דוח מפורמט ב-HTML
    """
    # Using Supabase only
    from db.db import db_client
    
    try:
        # קביעת טווח התאריכים
        now = datetime.datetime.now()
        
        if date_option == 'today':
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            period_text = t("today", lang)
        else:  # yesterday
            yesterday = now - datetime.timedelta(days=1)
            start_of_day = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            period_text = t("yesterday", lang)
        
        # שליפת משמרות שנסגרו ביום הנבחר
        all_shifts = db_client.select('shifts', {'status': 'closed'})
        shifts = []
        for shift_data in all_shifts:
            if shift_data.get('closed_time'):
                closed_time = datetime.datetime.fromisoformat(shift_data['closed_time'])
                if start_of_day <= closed_time <= end_of_day:
                    obj = type('Shift', (), shift_data)()
                    shifts.append(obj)
        
        if not shifts:
            return t("no_data_for_period", lang)
        
        # חישובים
        total_brutto = sum(shift.brutto or 0 for shift in shifts)
        total_operator_paid = sum(shift.operator_paid or 0 for shift in shifts)
        total_runner_paid = sum(shift.runner_paid or 0 for shift in shifts)
        total_petrol_paid = sum(shift.petrol_paid or 0 for shift in shifts)
        total_expenses = total_operator_paid + total_runner_paid + total_petrol_paid
        total_netto = sum(shift.netto or 0 for shift in shifts)
        
        # ספירת הזמנות
        all_orders = db_client.select('orders', {'status': 'completed'})
        orders = []
        for order_data in all_orders:
            if order_data.get('delivered'):
                delivered_time = datetime.datetime.fromisoformat(order_data['delivered'])
                if start_of_day <= delivered_time <= end_of_day:
                    obj = type('Order', (), order_data)()
                    orders.append(obj)
        total_orders = len(orders)
        
        # איסוף מוצרים שנמכרו
        product_summary = {}
        for shift in shifts:
            if shift.summary:
                summary_data = json.loads(shift.summary)
                for product_name, data in summary_data.items():
                    if product_name not in product_summary:
                        product_summary[product_name] = {
                            'quantity': 0,
                            'total_price': 0
                        }
                    product_summary[product_name]['quantity'] += data.get('total_quantity', 0)
                    product_summary[product_name]['total_price'] += data.get('total_price', 0)
        
        # בניית הדוח
        report = t("daily_report_title", lang).format(period_text)
        report += f"\n{start_of_day.strftime('%d.%m.%Y')}\n\n"
        
        report += t("total_brutto", lang).format(total_brutto) + "\n"
        report += t("total_expenses", lang).format(total_expenses) + "\n"
        report += t("expenses_breakdown", lang).format(
            total_operator_paid,
            total_runner_paid,
            total_petrol_paid
        ) + "\n"
        report += t("total_netto", lang).format(total_netto) + "\n"
        
        report += t("total_orders", lang).format(total_orders) + "\n"
        
        if product_summary:
            report += t("products_sold", lang) + "\n"
            qty_text = t("units", lang)
            for product_name, data in product_summary.items():
                report += f"  • {product_name} - {data['quantity']} {qty_text} - {data['total_price']}₪\n"
        
        return report
    except Exception as e:
        print(f"Error in form_daily_profit_report: {e}")
        return t("no_data_for_period", lang)

# מערכת היסטוריית ניווט
def add_to_navigation_history(context, menu_name, data=None, max_history=5):
    """הוספת תפריט להיסטוריית הניווט (מקסימום 5 מסכים)"""
    if 'navigation_history' not in context.user_data:
        context.user_data['navigation_history'] = []
    
    # מניעת כפילויות - אם התפריט האחרון זהה, לא מוסיפים
    if context.user_data['navigation_history'] and context.user_data['navigation_history'][-1]['menu'] == menu_name:
        print(f"🔍 Skipping duplicate: {menu_name} (already last in history)")
        return
    
    # הגבלה ל-5 מסכים אחרונים
    if len(context.user_data['navigation_history']) >= max_history:
        context.user_data['navigation_history'].pop(0)
    
    context.user_data['navigation_history'].append({
        'menu': menu_name,
        'data': data,
        'timestamp': datetime.datetime.now()
    })
    print(f"🔍 Navigation history: {[m['menu'] for m in context.user_data['navigation_history']]}")

def get_previous_menu(context):
    """קבלת התפריט הקודם"""
    if 'navigation_history' in context.user_data and len(context.user_data['navigation_history']) > 0:
        menu = context.user_data['navigation_history'].pop()
        return menu
    return None


def peek_navigation_history(context):
    """קבלת התפריט האחרון בהיסטוריה בלי להסיר אותו"""
    if 'navigation_history' in context.user_data and len(context.user_data['navigation_history']) > 0:
        menu = context.user_data['navigation_history'][-1]  # peek without pop
        return menu
    return None

def add_back_button_to_keyboard(keyboard, lang):
    """הוספת כפתור חזרה לכל תפריט"""
    if isinstance(keyboard, list):
        keyboard.append([InlineKeyboardButton(t('btn_back', lang), callback_data="back")])

async def delayed_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פתיחת תפריט ראשי עם delay קטן"""
    import asyncio
    await asyncio.sleep(1.0)  # תן זמן לפעולה להסתיים
    from funcs.bot_funcs import start
    await start(update, context)

def add_navigation_buttons_to_keyboard(keyboard, lang):
    """הוספת כפתורי חזרה ועמוד הבית לכל תפריט"""
    if isinstance(keyboard, list):
        keyboard.append([
            InlineKeyboardButton(t('btn_back', lang), callback_data="back"),
            InlineKeyboardButton(t('btn_home', lang), callback_data="home")
        ])
    return keyboard

# מערכת ניקוי הודעות
async def clean_previous_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    מחיקת ההודעה הקודמת לפני הצגת תפריט חדש
    CRITICAL: Handles errors gracefully - messages may already be deleted by cleanup_old_messages
    """
    if 'last_message_id' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['last_message_id']
            )
            # Clear the ID after successful deletion
            del context.user_data['last_message_id']
        except (BadRequest, Forbidden) as e:
            # Message already deleted or no permission - this is OK, silently ignore
            # Don't log errors that are expected (message already deleted)
            if 'message to delete not found' not in str(e).lower() and 'message not found' not in str(e).lower():
                # Only log unexpected BadRequest/Forbidden errors
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Could not delete message in clean_previous_message: {e}")
            # Clear the ID even if deletion failed (message doesn't exist)
            if 'last_message_id' in context.user_data:
                del context.user_data['last_message_id']
        except Exception as e:
            # Other unexpected errors - log but don't crash
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Unexpected error in clean_previous_message: {e}")
            # Clear the ID to prevent repeated attempts
            if 'last_message_id' in context.user_data:
                del context.user_data['last_message_id']

def save_message_id(context, message_id):
    """שמירת ID של הודעה לניקוי עתידי"""
    context.user_data['last_message_id'] = message_id

# דוח סיום משמרת
async def send_shift_end_report_to_admins(shift, lang: str = 'ru') -> None:
    """שליחת דוח סיום משמרת לקבוצת מנהלים"""
    print(f"🔧 send_shift_end_report_to_admins called")
    print(f"🔧 Shift type: {type(shift)}")
    print(f"🔧 Lang: {lang}")
    
    from config.config import links
    from telegram.constants import ParseMode
    
    rtl = '\u200F' if lang == 'he' else ''
    
    # Handle both dict and object
    summary = shift.summary if hasattr(shift, 'summary') else shift.get('summary', '{}')
    brutto = shift.brutto if hasattr(shift, 'brutto') else shift.get('brutto', 0)
    operator_paid = shift.operator_paid if hasattr(shift, 'operator_paid') else shift.get('operator_paid', 0)
    runner_paid = shift.runner_paid if hasattr(shift, 'runner_paid') else shift.get('runner_paid', 0)
    petrol_paid = shift.petrol_paid if hasattr(shift, 'petrol_paid') else shift.get('petrol_paid', 0)
    netto = shift.netto if hasattr(shift, 'netto') else shift.get('netto', 0)
    closed_time = shift.closed_time if hasattr(shift, 'closed_time') else shift.get('closed_time')
    
    # חישוב נתונים
    total_orders = len(json.loads(summary)) if summary else 0
    total_brutto = brutto or 0
    total_expenses = (operator_paid or 0) + (runner_paid or 0) + (petrol_paid or 0)
    net_profit = netto or 0
    
    # Handle closed_time
    import datetime
    if isinstance(closed_time, str):
        closed_time = datetime.datetime.fromisoformat(closed_time)
    elif not isinstance(closed_time, datetime.datetime):
        closed_time = datetime.datetime.now()
    
    # בניית הדוח
    report = f"""{rtl}<b>{t("shift_end_report_title", lang)}</b>
<i>{closed_time.strftime("%d.%m.%Y, %H:%M:%S")}</i>

<b>{t("total_orders", lang)}:</b> {total_orders}
<b>{t("total_brutto", lang)}:</b> {total_brutto}₪
<b>{t("total_expenses", lang)}:</b> {total_expenses}₪
<b>{t("net_profit", lang)}:</b> {net_profit}₪

<b>{t("expenses_breakdown", lang)}:</b>
• {t("operator_pay", lang)}: {operator_paid or 0}₪
• {t("courier_pay", lang)}: {runner_paid or 0}₪
• {t("fuel_pay", lang)}: {petrol_paid or 0}₪
"""
    
    # שליחה לקבוצת מנהלים
    try:
        from telegram import Bot
        from db.db import get_bot_setting
        admin_chat = get_bot_setting('admin_chat') or links.ADMIN_CHAT
        print(f"🔧 Admin chat ID: {admin_chat}")
        if admin_chat:
            bot = Bot(token=links.BOT_TOKEN)
            await bot.send_message(
                admin_chat,
                report,
                parse_mode=ParseMode.HTML
            )
            print(f"✅ Report sent to admin chat: {admin_chat}")
        else:
            print(f"⚠️ No admin chat configured, skipping report send")
    except Exception as e:
        print(f"❌ Error sending shift report: {e}")
        import traceback
        traceback.print_exc()

# ייצוא הזמנות כטקסט
async def export_orders_as_text(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = 'ru') -> None:
    """ייצוא הזמנות כטקסט במקום Excel"""
    # Using Supabase only
    from db.db import get_all_orders
    
    # קבלת כל ההזמנות
    all_orders = get_all_orders()
    
    if not all_orders:
        await update.effective_message.reply_text(t("no_orders_found", lang))
        return
    
    # בניית טקסט
    rtl = '\u200F' if lang == 'he' else ''
    export_text = f"{rtl}<b>{t('orders_export_title', lang)}</b>\n\n"
    
    for order_data in all_orders:
        # CRITICAL: Safe JSON parsing with error handling
        products_json = order_data.get('products', '[]')
        products = []
        if products_json and isinstance(products_json, str):
            try:
                parsed = json.loads(products_json)
                if isinstance(parsed, list):
                    products = parsed
            except (json.JSONDecodeError, TypeError):
                products = []  # Fallback to empty list
        
        products_text = ", ".join([f"{p.get('name', 'Unknown')} x{p.get('quantity', 0)}" for p in products if isinstance(p, dict)])
        
        export_text += f"<b>{t('order_id', lang)}:</b> {order_data['id']}\n"
        export_text += f"<b>{t('client_name', lang)}:</b> {order_data['client_name']}\n"
        export_text += f"<b>{t('client_phone', lang)}:</b> {order_data['client_phone']}\n"
        export_text += f"<b>{t('address', lang)}:</b> {order_data['address']}\n"
        export_text += f"<b>{t('products', lang)}:</b> {products_text}\n"
        export_text += f"<b>{t('status', lang)}:</b> {order_data['status'] if order_data.get('status') else 'N/A'}\n"
        
        if order_data.get('created'):
            created_time = datetime.datetime.fromisoformat(order_data['created'])
            export_text += f"<b>{t('created', lang)}:</b> {created_time.strftime('%d.%m.%Y %H:%M')}\n"
        
        if order_data.get('delivered'):
            delivered_time = datetime.datetime.fromisoformat(order_data['delivered'])
            export_text += f"<b>{t('delivered', lang)}:</b> {delivered_time.strftime('%d.%m.%Y %H:%M')}\n"
        
        export_text += "\n" + "─" * 50 + "\n\n"
    
    # חלוקה להודעות אם הטקסט ארוך מדי
    if len(export_text) > 4000:
        # חלוקה לחלקים
        parts = [export_text[i:i+4000] for i in range(0, len(export_text), 4000)]
        for part in parts:
            await update.effective_message.reply_text(part, parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(export_text, parse_mode=ParseMode.HTML)

# מערכת אישור וביטול
async def show_confirmation_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 action: str, details: str, lang: str = 'ru') -> None:
    """הצגת דיאלוג אישור לפעולה"""
    rtl = '\u200F' if lang == 'he' else ''
    
    confirmation_text = f"""{rtl}<b>{t('confirmation_title', lang)}</b>

<b>{t('action', lang)}:</b> {action}
<b>{t('details', lang)}:</b> {details}

{t('confirmation_warning', lang)}"""
    
    keyboard = [
        [InlineKeyboardButton(t('btn_confirm', lang), callback_data=f"confirm_{action}")],
        [InlineKeyboardButton(t('btn_cancel', lang), callback_data=f"cancel_{action}")]
    ]
    
    await update.effective_message.reply_text(
        confirmation_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול באישור/ביטול"""
    print(f"🔧 handle_confirmation called with data: {update.callback_query.data}")
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    print(f"🔧 Language: {lang}")
    
    if update.callback_query.data.startswith("confirm_"):
        action = update.callback_query.data.replace("confirm_", "")
        print(f"🔧 Confirm action: {action}")
        await execute_confirmed_action(update, context, action, lang)
    elif update.callback_query.data.startswith("cancel_"):
        action = update.callback_query.data.replace("cancel_", "")
        print(f"🔧 Cancel action: {action}")
        await update.effective_message.reply_text(t("action_cancelled", lang))

async def execute_confirmed_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, lang: str) -> None:
    """ביצוע הפעולה המאושרת"""
    print(f"🔧 execute_confirmed_action: action='{action}'")
    
    # Check if it's end_shift (could be with RTL markers or Hebrew text)
    if "סיום" in action or "משמרת" in action or action.strip() == "end_shift":
        print(f"🔧 Executing end_shift")
        # ביצוע סיום משמרת
        from handlers.end_shift_handler import confirm_end_shift
        await confirm_end_shift(update, context)
    elif action == "delete_order":
        # ביצוע מחיקת הזמנה
        await update.effective_message.reply_text(t("order_deleted", lang))
    # הוספת פעולות נוספות לפי הצורך