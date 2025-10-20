from telegram.ext import CallbackQueryHandler, TypeHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram import Message, InlineKeyboardMarkup, InlineKeyboardButton
from telegram import Update
from sqlalchemy import or_
from geopy.geocoders import Nominatim
from db.db import *
from config.config import *
from config.translations import t, get_user_lang
from funcs.utils import *
from funcs.bot_funcs import *
import asyncio

class WriteMinStates:
    WRITE_MIN = 0


async def choose_minutes_courier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Выбрать минуты нажатием по кнопке для курьера до выполнения заказа.
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    session = Session()
    courier = session.query(User).filter(
        User.user_id == update.effective_user.id,
        or_(User.role == Role.RUNNER, User.role == Role.ADMIN)
    ).first()
    if not courier:
        await update.effective_message.reply_text(t('need_courier_role', lang))
        session.close()
        return ConversationHandler.END
    session.close()

    start_msg = await update.effective_message.edit_reply_markup(reply_markup=get_cancel_kb(lang))
    context.user_data["choose_min_data"] = {}
    context.user_data["choose_min_data"]["start_msg"] = start_msg
    context.user_data["choose_min_data"]["lang"] = lang

    order_id = int(update.callback_query.data.replace("write_min_", ""))

    context.user_data["choose_min_data"]["order_id"] = order_id

    return WriteMinStates.WRITE_MIN

async def write_minutes_courier_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    minutes = int(update.effective_message.text)
    lang = context.user_data["choose_min_data"]["lang"]

    order_id = context.user_data["choose_min_data"]["order_id"]

    session = Session()

    order = session.query(Order).filter(Order.id==order_id).first()

    order.courier_id = update.effective_user.id
    order.courier_name = f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip()
    order.courier_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    order.courier_minutes = minutes
    order.status = Status.active

    session.commit()

    msg: Message = context.user_data["choose_min_data"]["start_msg"]

    try:
        text = await form_confirm_order_courier(order, lang)
        context.user_data["choose_min_data"]["start_msg"] = await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=(await form_courier_action_kb(order.id, lang)))

        shift = session.query(Shift).filter(Shift.status==ShiftStatus.opened).first()

        if shift:
            try:
                operator_lang = get_user_lang(shift.operator_id)
                await context.bot.send_message(shift.operator_id, (await form_notif_ready_order_short(order, operator_lang)), reply_markup=(await form_operator_action_kb(order, operator_lang)), parse_mode=ParseMode.HTML)
            except Exception as e:
                print(repr(e))
    except Exception:
        traceback.print_exc(chain=False)

    session.close()
    del context.user_data["choose_min_data"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["choose_min_data"]["lang"]
    msg: Message = context.user_data["choose_min_data"]["start_msg"]
    order_id: int = context.user_data["choose_min_data"]["order_id"]
    markup = await form_courier_action_kb(order_id, lang)
    await msg.edit_reply_markup(markup)
    del context.user_data["choose_min_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["choose_min_data"]["lang"]
    msg: Message = context.user_data["choose_min_data"]["start_msg"]
    order_id: int = context.user_data["choose_min_data"]["order_id"]
    markup = await form_courier_action_kb(order_id, lang)
    await msg.edit_reply_markup(markup)
    await msg.reply_text(t("timeout_error", lang))
    del context.user_data["choose_min_data"]

    return ConversationHandler.END


states = {
    WriteMinStates.WRITE_MIN: [
        MessageHandler(filters.Regex('^\d+$'), write_minutes_courier_end),
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


WRITE_MINUTES_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(choose_minutes_courier, pattern="write_min_*[0-9]")
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    conversation_timeout=120,
)