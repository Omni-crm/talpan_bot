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


def dicts_to_xlsx(dicts_list):
    df = pd.DataFrame(dicts_list)
    
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)  # Перемещаем указатель в начало файла
    return output


async def send_shift_start_msg(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = 'ru'):
    """
    Пример сообщения в группе контроля:

    Начало рабочего дня – 17.04.2025
    Оператор: @Vanillanew

    Начальный остаток (расфасовано):
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
        await context.bot.send_message(links.ADMIN_CHAT, msg, parse_mode=ParseMode.HTML,)
    except Exception as e:
        await update.effective_message.reply_text(repr(e))


async def form_confirm_order(order: Order, lang: str = 'ru') -> str:
    products = order.get_products()
    print(products)

    qty_text = "шт" if lang == 'ru' else "יח'"
    products_text = ", ".join([f"{product['name']} - {product['quantity']} {qty_text} - {product['price']}₪" for product in products])

    price_all_text = sum([(product['price']*product['quantity']) for product in products])

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

    qty_text = "шт" if lang == 'ru' else "יח'"
    products_text = ", ".join([f"{product['name']} - {product['quantity']} {qty_text} - {product['price']}₪/{qty_text}" for product in products])

    price_all_text = sum([(product['price']*product['quantity']) for product in products])

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

    qty_text = "шт" if lang == 'ru' else "יח'"
    products_text = ", ".join([f"{product['name']} - {product['quantity']} {qty_text} - {product['price']}₪" for product in products])

    price_all_text = sum([(product['price']*product['quantity']) for product in products])

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
    Пример отчета:
    Недельный отчет – 13–19 апреля 2025  
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
            print(f"Processing {key}: {value}")  # Выводим ключ и значение
            if key not in result:
                result[key] = {'quantity': value['total_quantity'], 'price': value['total_price']}  # Инициализируем словарь
            else:
                result[key]['quantity'] += value['total_quantity']  # Складываем quantity

    result = [f"{k} {v['quantity']}" for k,v in result.items()]
    summary_text = " | ".join(result)

    msg = f"""
<b>Недельный отчет – </b><i>{seven_days_ago.strftime("%d.%m.%Y")} - {now.strftime("%d.%m.%Y")}</i>
<b>Общий доход (брутто):</b> <i>{brutto}₪</i>
<b>Расходы:</b> <i>{expenses}₪</i>
<b>Чистая прибыль (нетто):</b> <i>{netto}₪</i>

<b>Всего выдано:</b>
{summary_text}

<b>Средние показатели: </b>
<b>Брутто:</b> <i>{avg_brutto}₪ в день | Нетто: {avg_netto}₪ в день</i>
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

    text = f"""<b>Отчет за день -</b> {shift_start_date}
<b>Общая выручка (брутто):</b> {shift.brutto}
<b>Расходы: Оператор –</b> {shift.operator_paid}₪ | Курьер – {shift.runner_paid}₪ | Топливо – {shift.petrol_paid}₪  
<b>Чистая прибыль (нетто):</b> {shift.netto}₪

<b>Выдано за день:</b>
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
            qty_text = "шт" if lang == 'ru' else "יח'"
            for product_name, data in product_summary.items():
                report += f"  • {product_name} - {data['quantity']} {qty_text} - {data['total_price']}₪\n"
        
        return report
        
    finally:
        session.close()