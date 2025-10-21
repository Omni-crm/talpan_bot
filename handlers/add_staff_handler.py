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

class AddStaffStates:
    ADD_STAFF = 0


async def add_staff_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    choices = {
        "add_o": (Role.OPERATOR, t("role_operator", lang)),
        "add_c": (Role.RUNNER, t("role_courier", lang)),
        "add_s": (Role.STOCKMAN, t("role_stockman", lang)),
    }

    start_msg = await update.effective_message.edit_text(t("enter_staff_username", lang), reply_markup=get_cancel_kb(lang))
    context.user_data["add_staff_data"] = {}
    context.user_data["add_staff_data"]["start_msg"] = start_msg
    context.user_data["add_staff_data"]["role_tup"] = choices[update.callback_query.data]
    context.user_data["add_staff_data"]["lang"] = lang

    return AddStaffStates.ADD_STAFF

async def add_staff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.delete()
    lang = context.user_data["add_staff_data"]["lang"]

    start_msg: Message = context.user_data["add_staff_data"]["start_msg"]

    text = update.effective_message.text
    if text.isdigit():
        user_id = int(update.effective_message.text)

        session = Session()

        user = session.query(User).filter(User.user_id==user_id).first()

        if user:
            user.role = context.user_data["add_staff_data"]["role_tup"][0]
            session.commit()
            await start_msg.edit_text(t("staff_added", lang).format(user.firstname, user.username, context.user_data["add_staff_data"]["role_tup"][1]), parse_mode=ParseMode.HTML)
        else:
            await start_msg.edit_text(t("user_not_found_id", lang).format(text), parse_mode=ParseMode.HTML)
    else:
        username = update.effective_message.text.replace('@', '')

        session = Session()

        user = session.query(User).filter(User.username==username).first()

        if user:
            user.role = context.user_data["add_staff_data"]["role_tup"][0]
            session.commit()
            await start_msg.edit_text(t("staff_added", lang).format(user.firstname, user.username, context.user_data["add_staff_data"]["role_tup"][1]), parse_mode=ParseMode.HTML)
        else:
            await start_msg.edit_text(t("user_not_found_username", lang).format(text), parse_mode=ParseMode.HTML)


    session.close()
    del context.user_data["add_staff_data"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["add_staff_data"]["lang"]
    await update.callback_query.answer(t('operation_cancelled', lang))
    msg: Message = context.user_data["add_staff_data"]["start_msg"]
    await msg.delete()
    del context.user_data["add_staff_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["add_staff_data"]["lang"]
    msg: Message = context.user_data["add_staff_data"]["start_msg"]
    await msg.edit_text(t("timeout_error", lang))
    del context.user_data["add_staff_data"]

    return ConversationHandler.END


states = {
    AddStaffStates.ADD_STAFF: [
        MessageHandler(filters.Regex('^@.+$'), add_staff),
        MessageHandler(filters.Regex(r'^\d+$'), add_staff),
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


ADD_STAFF_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_staff_start, pattern="add_o|add_c|add_s")
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    conversation_timeout=120,
)