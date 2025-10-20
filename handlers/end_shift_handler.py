from telegram.ext import CallbackQueryHandler, TypeHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram import Message, InlineKeyboardMarkup, InlineKeyboardButton
from telegram import Update
from geopy.geocoders import Nominatim
from db.db import *
from config.config import *
from config.translations import t, get_user_lang
from funcs.utils import *
from funcs.bot_funcs import *
import asyncio

class EndShiftStates:
    OPERATOR_PAID = 0
    RUNNER_PAID = 1
    PETROL_PAID = 2
    CONFIRM = 3


async def start_end_shift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Начало процесса завершения смены.
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    session = Session()
    shift = session.query(Shift).filter(Shift.status==ShiftStatus.opened).first()

    if not shift:
        await update.effective_message.edit_text(t("no_open_shifts", lang))
        session.close()
        return

    context.user_data["end_shift_data"] = {}
    context.user_data["end_shift_data"]["shift_id"] = shift.id
    context.user_data["end_shift_data"]["lang"] = lang
    context.user_data["end_shift_data"]["start_msg"] = await update.effective_message.reply_text(t("enter_operator_payment", lang), reply_markup=get_cancel_kb(lang), parse_mode=ParseMode.HTML)
    session.close()

    return EndShiftStates.OPERATOR_PAID


async def collect_operator_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.delete()
    lang = context.user_data["end_shift_data"]["lang"]

    context.user_data["end_shift_data"]["operator_paid"] = int(update.effective_message.text)
    start_msg: Message = context.user_data["end_shift_data"]["start_msg"]
    context.user_data["end_shift_data"]["start_msg"] = await start_msg.edit_text(t("enter_courier_payment", lang), reply_markup=get_cancel_kb(lang), parse_mode=ParseMode.HTML)

    return EndShiftStates.RUNNER_PAID

async def collect_runner_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.delete()
    lang = context.user_data["end_shift_data"]["lang"]

    context.user_data["end_shift_data"]["runner_paid"] = int(update.effective_message.text)
    start_msg: Message = context.user_data["end_shift_data"]["start_msg"]
    context.user_data["end_shift_data"]["start_msg"] = await start_msg.edit_text(t("enter_petrol_payment", lang), reply_markup=get_cancel_kb(lang), parse_mode=ParseMode.HTML)

    return EndShiftStates.PETROL_PAID


async def collect_petrol_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.delete()
    lang = context.user_data["end_shift_data"]["lang"]
    context.user_data["end_shift_data"]["petrol_paid"] = int(update.effective_message.text)


    session = Session()
    shift = session.query(Shift).filter(Shift.status==ShiftStatus.opened).first()
    shift_start_date = shift.opened_time.strftime("%d.%m.%Y, %H:%M:%S")

    orders = session.query(Order).filter(
        Order.status==Status.completed,
        Order.delivered.between(shift.opened_time, datetime.datetime.now()),
    )

    all_products: list[dict] = [product for order in orders for product in order.get_products()]

    print(all_products)

    summary = {}
    total_sum = 0  # Переменная для хранения общей суммы

    # Обходим все продукты
    for product in all_products:
        name = product["name"]
        quantity = product["quantity"]
        price = product["price"]

        # Вычисляем сумму для текущего продукта
        current_product_total = quantity * price
        total_sum += current_product_total  # Добавляем к общей сумме

        # Если продукт уже есть в словаре, обновляем количество и сумму
        if name in summary:
            summary[name]["total_quantity"] += quantity
            summary[name]["total_price"] += current_product_total
        else:
            # Если продукта нет, добавляем его в словарь
            summary[name] = {
                "total_quantity": quantity,
                "total_price": quantity * price
            }

    samples = []
    qty_text = "шт" if lang == 'ru' else "יח'"

    for name, data in summary.items():
        sample_text = f"{name} - {data['total_quantity']} {qty_text} - {data['total_price']} ₪"
        samples.append(sample_text)
    
    context.user_data["end_shift_data"]["summary"] = summary

    products_fetched_text = '\n'.join(samples)

    context.user_data["end_shift_data"]["products_fetched_text"] = products_fetched_text

    total_sum_text = "Общая сумма за выданные товары" if lang == 'ru' else "סכום כולל עבור מוצרים שנמסרו"
    products_fetched_text += f'\n\n{total_sum_text}: {total_sum} ₪'

    context.user_data["end_shift_data"]["brutto"] = total_sum
    context.user_data["end_shift_data"]["netto"] = total_sum - context.user_data["end_shift_data"]["operator_paid"] - context.user_data["end_shift_data"]["runner_paid"] - context.user_data["end_shift_data"]["petrol_paid"]

    text = f"""
{t("check_shift_data", lang)}

{t("shift_start_time", lang).format(shift_start_date)}
{t("operator_payment", lang).format(context.user_data["end_shift_data"]["operator_paid"])}
{t("courier_payment", lang).format(context.user_data["end_shift_data"]["runner_paid"])}
{t("petrol_payment", lang).format(context.user_data["end_shift_data"]["petrol_paid"])}

{t("shift_products_summary", lang).format(products_fetched_text)}

"""
    context.user_data["end_shift_data"]["petrol_paid"] = int(update.effective_message.text)
    start_msg: Message = context.user_data["end_shift_data"]["start_msg"]
    context.user_data["end_shift_data"]["start_msg"] = await start_msg.edit_text(text, reply_markup=get_confirm_order_kb(lang), parse_mode=ParseMode.HTML)

    session.close()

    return EndShiftStates.CONFIRM


async def confirm_end_shift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["end_shift_data"]["lang"]
    session = Session()

    shift: Shift = session.query(Shift).get(context.user_data["end_shift_data"]["shift_id"])

    user: User = session.query(User).filter(User.user_id==update.effective_user.id).first()

    shift.operator_paid = context.user_data["end_shift_data"]["operator_paid"]
    shift.runner_paid = context.user_data["end_shift_data"]["runner_paid"]
    shift.petrol_paid = context.user_data["end_shift_data"]["petrol_paid"]
    shift.brutto = context.user_data["end_shift_data"]["brutto"]
    shift.netto = context.user_data["end_shift_data"]["netto"]
    shift.products_fetched_text = context.user_data["end_shift_data"]["products_fetched_text"]
    shift.operator_close_id = user.user_id
    shift.operator_close_username = user.username
    shift.summary = json.dumps(context.user_data["end_shift_data"]["summary"])

    shift.products_end = json.dumps(shift.set_products())
    shift.closed_time = datetime.datetime.now()
    shift.status = ShiftStatus.closed
    session.commit()

    report = await form_end_shift_report(shift)

    session.close()

    start_msg: Message = context.user_data["end_shift_data"]["start_msg"]
    context.user_data["end_shift_data"]["start_msg"] = await start_msg.edit_text(report, parse_mode=ParseMode.HTML)
    await update.effective_message.reply_text(t("shift_closed_success", lang))

    try:
        await context.bot.send_message(links.ADMIN_CHAT, report, parse_mode=ParseMode.HTML)
    except Exception as e:
        error_msg = "Не смогли отправить отчёт в контрольную группу. Ошибка" if lang == 'ru' else "לא הצליח לשלוח דוח לקבוצת הבקרה. שגיאה"
        await update.effective_message.reply_text(f"{error_msg}: {repr(e)}")

    del context.user_data["end_shift_data"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["end_shift_data"]["lang"]
    await update.callback_query.answer(t('operation_cancelled', lang))
    msg: Message = context.user_data["end_shift_data"]["start_msg"]
    await msg.delete()
    del context.user_data["end_shift_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["end_shift_data"]["lang"]
    msg: Message = context.user_data["end_shift_data"]["start_msg"]
    await msg.edit_text(t("timeout_error", lang))
    del context.user_data["end_shift_data"]

    return ConversationHandler.END


states = {
    EndShiftStates.OPERATOR_PAID: [
        MessageHandler(filters.Regex('^\d+$'), collect_operator_paid),
    ],
    EndShiftStates.RUNNER_PAID: [
        MessageHandler(filters.Regex('^\d+$'), collect_runner_paid),
    ],
    EndShiftStates.PETROL_PAID: [
        MessageHandler(filters.Regex('^\d+$'), collect_petrol_paid),
    ],
    EndShiftStates.CONFIRM: [
        CallbackQueryHandler(confirm_end_shift, pattern='confirm'),
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


END_SHIFT_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_end_shift, pattern="end_shift")
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    conversation_timeout=120,
)