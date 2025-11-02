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


async def add_staff_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

async def add_staff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.delete()
    lang = context.user_data["add_staff_data"]["lang"]

    start_msg: Message = context.user_data["add_staff_data"]["start_msg"]

    text = update.effective_message.text
    
    # Using Supabase only
    from db.db import db_client
    
    if text.isdigit():
        user_id = int(update.effective_message.text)
        users = db_client.select('users', {'user_id': user_id})
        
        if users:
            user = users[0]
            role_value = context.user_data["add_staff_data"]["role_tup"][0].value
            db_client.update('users', {'role': role_value}, {'user_id': user_id})
            await start_msg.edit_text(t("staff_added", lang).format(user['firstname'], user['username'], context.user_data["add_staff_data"]["role_tup"][1]), parse_mode=ParseMode.HTML)
        else:
            await start_msg.edit_text(t("user_not_found_id", lang).format(text), parse_mode=ParseMode.HTML)
    else:
        username = update.effective_message.text.replace('@', '')
        users = db_client.select('users', {'username': username})
        
        if users:
            user = users[0]
            role_value = context.user_data["add_staff_data"]["role_tup"][0].value
            db_client.update('users', {'role': role_value}, {'username': username})
            await start_msg.edit_text(t("staff_added", lang).format(user['firstname'], user['username'], context.user_data["add_staff_data"]["role_tup"][1]), parse_mode=ParseMode.HTML)
        else:
            await start_msg.edit_text(t("user_not_found_username", lang).format(text), parse_mode=ParseMode.HTML)
    
    del context.user_data["add_staff_data"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data["add_staff_data"]["lang"]
    await update.callback_query.answer(t('operation_cancelled', lang))
    msg: Message = context.user_data["add_staff_data"]["start_msg"]
    await msg.delete()
    del context.user_data["add_staff_data"]
    
    # Return to main menu
    from funcs.bot_funcs import start
    await start(update, context)

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        CallbackQueryHandler(cancel, '^back$'),  # Terminate conversation on back
        CallbackQueryHandler(cancel, '^home$'),  # Terminate conversation on home
    ],
    conversation_timeout=120,
)