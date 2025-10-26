from telegram.ext import CallbackQueryHandler, TypeHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram import Update
from telegram.constants import ParseMode
from db.db import Status, Order, Shift, ShiftStatus, Session, Product
from config.config import *
from config.translations import t
import datetime
import pandas as pd
from io import BytesIO
import json


async def cleanup_old_messages(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    פונקציה כללית למחיקת הודעות קודמות
    """
    if context.user_data.get("msgs_to_delete"):
        msgs = context.user_data["msgs_to_delete"]
        for msg in msgs:
            try:
                await msg.delete()
            except:
                pass
        context.user_data["msgs_to_delete"] = []


def save_message_for_cleanup(context: ContextTypes.DEFAULT_TYPE, msg) -> None:
    """
    פונקציה לשמירת הודעה למחיקה עתידית
    """
    if not context.user_data.get("msgs_to_delete"):
        context.user_data["msgs_to_delete"] = []
    context.user_data["msgs_to_delete"].append(msg)


async def send_message_with_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    """
    פונקציה כללית לשליחת הודעה עם ניקוי אוטומטי של הודעות קודמות
    """
    # מחיקת הודעות קודמות
    await cleanup_old_messages(context)
    
    # שליחת הודעה חדשה
    if update.callback_query:
        msg = await update.callback_query.message.reply_text(text, **kwargs)
    else:
        msg = await update.effective_message.reply_text(text, **kwargs)
    
    # שמירת הודעה למחיקה עתידית
    save_message_for_cleanup(context, msg)
    
    return msg


async def edit_message_with_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    """
    פונקציה כללית לעריכת הודעה עם ניקוי אוטומטי של הודעות קודמות
    """
    # מחיקת הודעות קודמות
    await cleanup_old_messages(context)
    
    # עריכת הודעה קיימת
    if update.callback_query:
        msg = await update.callback_query.message.edit_text(text, **kwargs)
    else:
        msg = await update.effective_message.edit_text(text, **kwargs)
    
    # שמירת הודעה למחיקה עתידית
    save_message_for_cleanup(context, msg)
    
    return msg


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
    session = Session()
    shift = Shift()
    shift.operator_id = update.effective_user.id
    shift.operator_username = update.effective_user.username
    session.add(shift)
    session.commit()

    products_text = " | ".join([((product.get("name") + ' ' + str(product.get("stock")))) for product in shift.get_products()])

    # הוספת RTL mark לתחילת ההודעה אם בעברית
    rtl = '\u200F' if lang == 'he' else ''
    
    msg = f"""{rtl}<b>{t("shift_start_title", lang)} –</b> <i>{shift.opened_time.strftime("%d.%m.%Y, %H:%M:%S")}</i>
<b>{t("operator", lang)}:</b> <i>{update.effective_user.first_name} @{update.effective_user.username}</i>

<b>{t("initial_stock", lang)}:</b>
{products_text}
    """
    session.close()

    try:
        from db.db import get_bot_setting
        admin_chat = get_bot_setting('admin_chat') or links.ADMIN_CHAT
        if admin_chat:
            await context.bot.send_message(admin_chat, msg, parse_mode=ParseMode.HTML,)
    except Exception as e:
        await update.effective_message.reply_text(repr(e))
    
    # החזרה למסך הראשי
    from config.kb import build_start_menu
    reply_markup = await build_start_menu(update.effective_user.id)
    await send_message_with_cleanup(update, context, t("main_menu", lang), reply_markup=reply_markup)


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

{(t("order_status", lang).format(order.status.value) if order.status else '')}
"""

    return msg

async def form_confirm_order_courier_info(order: Order, lang: str = 'ru') -> str:
    products = order.get_products()
    print(products)

    qty_text = t("units", lang)
    products_text = ", ".join([f"{product['name']} - {product['quantity']} {qty_text} - {product['total_price']}₪/{qty_text}" for product in products])

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

{t("courier_name", lang).format(order.courier_name)}
{t("courier_username", lang).format(order.courier_username)}
{t("courier_id", lang).format(order.courier_id)}
{(t('selected_time', lang).format(order.courier_minutes)) if order.courier_minutes else ''}

{(t('delay_reason', lang).format(order.delay_reason)) if order.delay_reason else ''}
{(t('delay_time', lang).format(order.delay_minutes)) if order.delay_minutes else ''}

{(t('order_status', lang).format(order.status.value)) if order.status else ''}
"""

    return msg

async def form_confirm_order_courier(order: Order, lang: str = 'ru') -> str:
    products = order.get_products()
    print(products)

    qty_text = t("units", lang)
    products_text = ", ".join([f"{product['name']} - {product['quantity']} {qty_text} - {product['total_price']}₪" for product in products])

    price_all_text = sum([(product['total_price']) for product in products])

    # הוספת RTL mark לתחילת ההודעה אם בעברית
    rtl = '\u200F' if lang == 'he' else ''
    
    msg = f"""{rtl}{t("order_id", lang).format(order.id if order.id else '')}

{t("client_name", lang).format(order.client_name)}
{t("address", lang).format(order.address)}
{t("products", lang).format(products_text)}
{t("total_price", lang).format(price_all_text)}
{(t('selected_time', lang).format(order.courier_minutes)) if order.courier_minutes else ''}

{(t('delay_reason', lang).format(order.delay_reason)) if order.delay_reason else ''}
{(t('delay_time', lang).format(order.delay_minutes)) if order.delay_minutes else ''}

{(t('order_status', lang).format(order.status.value)) if order.status else ''}
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


async def form_week_report():
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
    session = Session()

    now = datetime.datetime.now()
    seven_days_ago = now - datetime.timedelta(days=7)
    shifts = session.query(Shift).filter(Shift.closed_time >= seven_days_ago).all()

    brutto = sum([shift.brutto for shift in shifts])
    avg_brutto = brutto // 7
    netto = sum([shift.netto for shift in shifts])
    avg_netto = netto // 7

    expenses = sum([(shift.operator_paid + shift.runner_paid + shift.petrol_paid) for shift in shifts])

    summaries = [shift.get_summary() for shift in shifts]

    result = {}

    for entry in summaries:
        for key, value in entry.items():
            print(f"Processing {key}: {value}")  # Print key and value
            if key not in result:
                result[key] = {'quantity': value['total_quantity'], 'price': value['total_price']}  # Initialize dictionary
            else:
                result[key]['quantity'] += value['total_quantity']  # Add quantity

    result = [f"{k} {v['quantity']}" for k,v in result.items()]
    summary_text = " | ".join(result)

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

async def form_end_shift_report(shift: Shift):
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
    session = Session()
    
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
        shifts = session.query(Shift).filter(
            Shift.closed_time.between(start_of_day, end_of_day),
            Shift.status == ShiftStatus.closed
        ).all()
        
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
        orders = session.query(Order).filter(
            Order.delivered.between(start_of_day, end_of_day),
            Order.status == Status.completed
        ).all()
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
        
    finally:
        session.close()

# מערכת היסטוריית ניווט
def add_to_navigation_history(context, menu_name, data=None):
    """הוספת תפריט להיסטוריית הניווט"""
    if 'navigation_history' not in context.user_data:
        context.user_data['navigation_history'] = []
    
    context.user_data['navigation_history'].append({
        'menu': menu_name,
        'data': data,
        'timestamp': datetime.datetime.now()
    })

def get_previous_menu(context):
    """קבלת התפריט הקודם"""
    if 'navigation_history' in context.user_data and len(context.user_data['navigation_history']) > 1:
        return context.user_data['navigation_history'].pop()
    return None

def add_back_button_to_keyboard(keyboard, lang):
    """הוספת כפתור חזרה לכל תפריט"""
    if isinstance(keyboard, list):
        keyboard.append([InlineKeyboardButton(t('btn_back', lang), callback_data="back")])
    return keyboard

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
    """מחיקת ההודעה הקודמת לפני הצגת תפריט חדש"""
    if 'last_message_id' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['last_message_id']
            )
        except Exception as e:
            # הודעה כבר נמחקה או אין הרשאה
            print(f"Could not delete message: {e}")
            pass

def save_message_id(context, message_id):
    """שמירת ID של הודעה לניקוי עתידי"""
    context.user_data['last_message_id'] = message_id

# דוח סיום משמרת
async def send_shift_end_report_to_admins(shift, lang: str = 'ru') -> None:
    """שליחת דוח סיום משמרת לקבוצת מנהלים"""
    from config.config import links
    from telegram.constants import ParseMode
    
    rtl = '\u200F' if lang == 'he' else ''
    
    # חישוב נתונים
    total_orders = len(json.loads(shift.summary)) if shift.summary else 0
    total_brutto = shift.brutto or 0
    total_expenses = (shift.operator_paid or 0) + (shift.runner_paid or 0) + (shift.petrol_paid or 0)
    net_profit = shift.netto or 0
    
    # בניית הדוח
    report = f"""{rtl}<b>{t("shift_end_report_title", lang)}</b>
<i>{shift.closed_time.strftime("%d.%m.%Y, %H:%M:%S")}</i>

<b>{t("total_orders", lang)}:</b> {total_orders}
<b>{t("total_brutto", lang)}:</b> {total_brutto}₪
<b>{t("total_expenses", lang)}:</b> {total_expenses}₪
<b>{t("net_profit", lang)}:</b> {net_profit}₪

<b>{t("expenses_breakdown", lang)}:</b>
• {t("operator_pay", lang)}: {shift.operator_paid or 0}₪
• {t("courier_pay", lang)}: {shift.runner_paid or 0}₪
• {t("fuel_pay", lang)}: {shift.petrol_paid or 0}₪
"""
    
    # שליחה לקבוצת מנהלים
    try:
        from telegram import Bot
        from db.db import get_bot_setting
        admin_chat = get_bot_setting('admin_chat') or links.ADMIN_CHAT
        if admin_chat:
            bot = Bot(token=links.BOT_TOKEN)
            await bot.send_message(
                admin_chat,
                report,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        print(f"Error sending shift report: {e}")

# ייצוא הזמנות כטקסט
async def export_orders_as_text(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = 'ru') -> None:
    """ייצוא הזמנות כטקסט במקום Excel"""
    session = Session()
    
    # קבלת כל ההזמנות
    orders = session.query(Order).all()
    
    if not orders:
        await update.effective_message.reply_text(t("no_orders_found", lang))
        session.close()
        return
    
    # בניית טקסט
    rtl = '\u200F' if lang == 'he' else ''
    export_text = f"{rtl}<b>{t('orders_export_title', lang)}</b>\n\n"
    
    for order in orders:
        products = json.loads(order.products) if order.products else []
        products_text = ", ".join([f"{p['name']} x{p['quantity']}" for p in products])
        
        export_text += f"<b>{t('order_id', lang)}:</b> {order.id}\n"
        export_text += f"<b>{t('client_name', lang)}:</b> {order.client_name}\n"
        export_text += f"<b>{t('client_phone', lang)}:</b> {order.client_phone}\n"
        export_text += f"<b>{t('address', lang)}:</b> {order.address}\n"
        export_text += f"<b>{t('products', lang)}:</b> {products_text}\n"
        export_text += f"<b>{t('status', lang)}:</b> {order.status.value if order.status else 'N/A'}\n"
        export_text += f"<b>{t('created', lang)}:</b> {order.created.strftime('%d.%m.%Y %H:%M')}\n"
        if order.delivered:
            export_text += f"<b>{t('delivered', lang)}:</b> {order.delivered.strftime('%d.%m.%Y %H:%M')}\n"
        export_text += "\n" + "─" * 50 + "\n\n"
    
    # חלוקה להודעות אם הטקסט ארוך מדי
    if len(export_text) > 4000:
        # חלוקה לחלקים
        parts = [export_text[i:i+4000] for i in range(0, len(export_text), 4000)]
        for part in parts:
            await update.effective_message.reply_text(part, parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(export_text, parse_mode=ParseMode.HTML)
    
    session.close()

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
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    if update.callback_query.data.startswith("confirm_"):
        action = update.callback_query.data.replace("confirm_", "")
        await execute_confirmed_action(update, context, action, lang)
    elif update.callback_query.data.startswith("cancel_"):
        action = update.callback_query.data.replace("cancel_", "")
        await update.effective_message.reply_text(t("action_cancelled", lang))

async def execute_confirmed_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, lang: str) -> None:
    """ביצוע הפעולה המאושרת"""
    if action == "end_shift":
        # ביצוע סיום משמרת
        from handlers.end_shift_handler import confirm_end_shift
        await confirm_end_shift(update, context)
    elif action == "delete_order":
        # ביצוע מחיקת הזמנה
        await update.effective_message.reply_text(t("order_deleted", lang))
    # הוספת פעולות נוספות לפי הצורך