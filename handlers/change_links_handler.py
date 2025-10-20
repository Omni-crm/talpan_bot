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

class EditGroupLinkStates:
    GET_NEW_LINK = 0


async def start_edit_group_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """START function of collecting data for new order."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    group_type = 'admin' if 'admin' in update.callback_query.data else 'courier'
    tip = 'группы админов' if group_type == 'admin' else 'группы курьеров'
    tip_he = 'קבוצת מנהלים' if group_type == 'admin' else 'קבוצת שליחים'
    
    tip_text = tip if lang == 'ru' else tip_he
    prompt = "Напишите боту новую ссылку для" if lang == 'ru' else "כתוב קישור חדש עבור"
    format_text = "в формате @username:" if lang == 'ru' else "בפורמט @username:"

    start_msg = await update.effective_message.edit_text(f"{prompt} <b>{tip_text}</b> {format_text}", reply_markup=get_cancel_kb(lang), parse_mode=ParseMode.HTML)
    context.user_data["edit_group_link_data"] = {}
    context.user_data["edit_group_link_data"]["start_msg"] = start_msg
    context.user_data["edit_group_link_data"]["group_type"] = group_type
    context.user_data["edit_group_link_data"]["lang"] = lang

    return EditGroupLinkStates.GET_NEW_LINK


async def change_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.delete()
    lang = context.user_data["edit_group_link_data"]["lang"]

    new_link = update.effective_message.text
    
    group_type = context.user_data["edit_group_link_data"]["group_type"]

    if group_type == 'admin':
        with open('.env', 'r') as f:
            env_text = f.read()
        
        env_text = env_text.replace(f"ADMIN_CHAT={links.ADMIN_CHAT}", f"ADMIN_CHAT={new_link}")

        with open('.env', 'w') as f:
            f.write(env_text)
        
        links.ADMIN_CHAT = new_link
    else:
        with open('.env', 'r') as f:
            env_text = f.read()

        env_text = env_text.replace(f"ORDER_CHAT={links.ORDER_CHAT}", f"ORDER_CHAT={new_link}")

        with open('.env', 'w') as f:
            f.write(env_text)
        
        links.ORDER_CHAT = new_link

    msg: Message = context.user_data["edit_group_link_data"]["start_msg"]
    
    success_text = "Успешно. Новые ссылки на группы" if lang == 'ru' else "הצלחה. קישורים חדשים לקבוצות"
    admin_text = "Группа админов" if lang == 'ru' else "קבוצת מנהלים"
    courier_text = "Группа курьеров" if lang == 'ru' else "קבוצת שליחים"

    await msg.edit_text(f"<b>{success_text}:</b>\n\n<b>{admin_text}:</b> {links.ADMIN_CHAT}\n<b>{courier_text}:</b> {links.ORDER_CHAT}", parse_mode=ParseMode.HTML)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["edit_group_link_data"]["lang"]
    msg: Message = context.user_data["edit_group_link_data"]["start_msg"]
    await msg.delete()
    del context.user_data["edit_group_link_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["edit_group_link_data"]["lang"]
    msg: Message = context.user_data["edit_group_link_data"]["start_msg"]
    await msg.reply_text(t("timeout_error", lang))
    del context.user_data["edit_group_link_data"]

    return ConversationHandler.END


states = {
    EditGroupLinkStates.GET_NEW_LINK: [
        MessageHandler(filters.Regex('^@.+$'), change_link)
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


CHANGE_LINK_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_edit_group_link, 'change_admin_group_link|change_courier_group_link$'),
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    conversation_timeout=120,
)