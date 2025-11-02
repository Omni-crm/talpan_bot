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

class CreateTemplateStates:
    WRITE_NAME = 0
    WRITE_TEXT = 1


async def start_template_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    start_msg = await update.effective_message.edit_text(
        text=t("enter_template_name", lang),
        reply_markup=get_cancel_kb(lang),
    )
    context.user_data["create_new_shab_data"] = {}
    context.user_data["create_new_shab_data"]["start_msg"] = start_msg
    context.user_data["create_new_shab_data"]["lang"] = lang

    return CreateTemplateStates.WRITE_NAME

async def collecting_new_template_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.delete()
    lang = context.user_data["create_new_shab_data"]["lang"]

    name = update.effective_message.text[:22]
    context.user_data["create_new_shab_data"]["name"] = name

    start_msg: Message = context.user_data["create_new_shab_data"]["start_msg"]

    await start_msg.edit_text(
        text=t("enter_template_text", lang),
        reply_markup=get_cancel_kb(lang),
    )

    return CreateTemplateStates.WRITE_TEXT


async def collecting_new_template_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.delete()
    lang = context.user_data["create_new_shab_data"]["lang"]

    text = update.effective_message.text
    context.user_data["create_new_shab_data"]["text"] = text

    # Using Supabase only
    from db.db import db_client
    
    template_data = {
        'name': context.user_data["create_new_shab_data"]["name"],
        'text': text
    }
    
    result = db_client.insert('templates', template_data)
    print(f"Created template: {result}")

    start_msg: Message = context.user_data["create_new_shab_data"]["start_msg"]

    await start_msg.edit_text(
        text=t("template_created", lang).format(template_data['name'], text),
        parse_mode=ParseMode.HTML,
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["create_new_shab_data"]["lang"]
    msg: Message = context.user_data["create_new_shab_data"]["start_msg"]
    await msg.delete()  # Delete instead of edit
    del context.user_data["create_new_shab_data"]
    
    # Return to main menu
    from funcs.bot_funcs import start
    await start(update, context)

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data["create_new_shab_data"]["lang"]
    msg: Message = context.user_data["create_new_shab_data"]["start_msg"]
    await msg.reply_text(t("timeout_error", lang))
    del context.user_data["create_new_shab_data"]

    return ConversationHandler.END


states = {
    CreateTemplateStates.WRITE_NAME: [
        MessageHandler(filters.Regex('^.+$'), collecting_new_template_name),
    ],
    CreateTemplateStates.WRITE_TEXT: [
        MessageHandler(filters.Regex('^.+$'), collecting_new_template_text),
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


CREATE_NEW_TEMPLATE = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_template_creation, pattern="new_shab")
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
        CallbackQueryHandler(cancel, '^back$'),  # Terminate conversation on back
        CallbackQueryHandler(cancel, '^home$'),  # Terminate conversation on home
    ],
    conversation_timeout=120,
)