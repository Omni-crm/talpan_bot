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

class DelayMinStates:
    WRITE_REASON = 0
    CHOOSE_MIN = 1
    WRITE_MY = 2


async def choose_minutes_courier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Выбрать минуты нажатием по кнопке для курьера для выбора задержки.
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

    start_msg_2 = await update.effective_message.reply_text(t('enter_delay_reason', lang))
    context.user_data["delay_min_data"] = {}
    context.user_data["delay_min_data"]["start_msg"] = await update.effective_message.edit_reply_markup(reply_markup=get_cancel_kb(lang))
    context.user_data["delay_min_data"]["start_msg_2"] = start_msg_2
    context.user_data["delay_min_data"]["lang"] = lang

    order_id = int(update.callback_query.data.replace("delay_min_", ""))

    context.user_data["delay_min_data"]["order_id"] = order_id

    return DelayMinStates.WRITE_REASON


async def write_delay_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message.voice:
        chat_id = str(update.effective_chat.id).replace('-100', '')
        link_to_message = f'https://t.me/c/{chat_id}/{update.effective_message.id}'
        delay_reason = f"<a href='{link_to_message}'>Ссылка на голосовое</a>"
        context.user_data["delay_min_data"]["delay_reason"] = delay_reason
    else:
        delay_reason = update.effective_message.text
        context.user_data["delay_min_data"]["delay_reason"] = delay_reason

    start_msg: Message = context.user_data["delay_min_data"]["start_msg"]
    context.user_data["delay_min_data"]["start_msg"] = await start_msg.edit_reply_markup(reply_markup=DELAY_MINUTES_KB)
    start_msg_2 = context.user_data["delay_min_data"]["start_msg_2"]

    try:
        await start_msg_2.delete()
        await asyncio.sleep(0.1)
        await update.effective_message.delete()
    except: pass

    return DelayMinStates.CHOOSE_MIN

async def delay_minutes_courier_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["delay_min_data"]["lang"]

    delay_minutes = int(update.callback_query.data)

    order_id = context.user_data["delay_min_data"]["order_id"]

    session = Session()

    order = session.query(Order).filter(Order.id==order_id).first()

    order.courier_id = update.effective_user.id
    order.courier_name = f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip()
    order.courier_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    order.delay_minutes = delay_minutes
    order.delay_reason = context.user_data["delay_min_data"]["delay_reason"]
    order.status = Status.delay

    session.commit()

    msg: Message = context.user_data["delay_min_data"]["start_msg"]

    try:
        text = await form_confirm_order_courier(order, lang)
        context.user_data["delay_min_data"]["start_msg"] = await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=(await form_courier_action_kb(order_id, lang)))

        status_text = "Статус заказа" if lang == 'ru' else "סטטוס הזמנה"
        changed_text = "изменился на" if lang == 'ru' else "שונה ל"
        info_text = f"<b>{status_text}</b> <i>#{order_id}</i> {changed_text} <i>{order.status.value}</i>"
        await context.bot.send_message(links.ADMIN_CHAT, info_text, parse_mode=ParseMode.HTML)

        text = await form_confirm_order_courier_info(order, 'ru')  # לקבוצת אדמינים תמיד ברוסית
        await context.bot.send_message(links.ADMIN_CHAT, text, parse_mode=ParseMode.HTML)
    except Exception:
        traceback.print_exc(chain=False)

    session.close()
    del context.user_data["delay_min_data"]

    return ConversationHandler.END

async def write_delay_minutes_courier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Написать текстом количество минут
    """
    await update.callback_query.answer()
    lang = context.user_data["delay_min_data"]["lang"]

    context.user_data["delay_min_data"]["trash"] = []
    context.user_data["delay_min_data"]["trash"].append(await update.effective_message.reply_text(t('enter_minutes', lang)))
    context.user_data["delay_min_data"]["start_msg"] = await update.effective_message.edit_reply_markup(reply_markup=get_cancel_kb(lang))

    return DelayMinStates.WRITE_MY

async def write_delay_minutes_courier_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    minutes = int(update.effective_message.text)
    lang = context.user_data["delay_min_data"]["lang"]

    order_id = context.user_data["delay_min_data"]["order_id"]

    session = Session()

    order = session.query(Order).filter(Order.id==order_id).first()

    order.courier_id = update.effective_user.id
    order.courier_name = f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip()
    order.courier_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    order.delay_minutes = minutes
    order.delay_reason = context.user_data["delay_min_data"]["delay_reason"]
    order.status = Status.delay

    session.commit()

    start_msg: Message = context.user_data["delay_min_data"]["start_msg"]

    try:
        text = await form_confirm_order_courier(order, lang)
        context.user_data["delay_min_data"]["start_msg"] = await start_msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=(await form_courier_action_kb(order_id, lang)))

        if context.user_data["delay_min_data"].get("trash"):
            for msg in context.user_data["delay_min_data"].get("trash"):
                try:
                    await msg.delete()
                except:
                    pass

        shift = session.query(Shift).filter(Shift.status==ShiftStatus.opened).first()

        if shift:
            try:
                operator_lang = get_user_lang(shift.operator_id)
                await context.bot.send_message(shift.operator_id, (await form_notif_delay_short(order, operator_lang)), parse_mode=ParseMode.HTML)
            except Exception as e:
                print(repr(e))
    except Exception:
        traceback.print_exc()

    session.close()
    del context.user_data["delay_min_data"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["delay_min_data"]["lang"]
    msg: Message = context.user_data["delay_min_data"]["start_msg"]
    order_id: int = context.user_data["delay_min_data"]["order_id"]
    markup = await form_courier_action_kb(order_id, lang)
    await msg.edit_reply_markup(markup)
    del context.user_data["delay_min_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["delay_min_data"]["lang"]
    msg: Message = context.user_data["delay_min_data"]["start_msg"]
    order_id: int = context.user_data["delay_min_data"]["order_id"]
    markup = await form_courier_action_kb(order_id, lang)
    await msg.edit_reply_markup(markup)
    await msg.reply_text(t("timeout_error", lang))
    del context.user_data["delay_min_data"]

    return ConversationHandler.END


states = {
    DelayMinStates.WRITE_REASON: [
        MessageHandler(filters.Regex('^.+$'), write_delay_reason),
        MessageHandler(filters.VOICE, write_delay_reason),
    ],
    DelayMinStates.CHOOSE_MIN: [
        CallbackQueryHandler(delay_minutes_courier_end, pattern="^\d+$"),
        CallbackQueryHandler(write_delay_minutes_courier, pattern="^my$"),
    ],
    DelayMinStates.WRITE_MY: [
        MessageHandler(filters.Regex('^\d+$'), write_delay_minutes_courier_end),
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


DELAY_MINUTES_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(choose_minutes_courier, pattern="delay_min_*[0-9]")
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    conversation_timeout=120,
)