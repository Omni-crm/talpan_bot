from telegram.ext import CallbackQueryHandler, TypeHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram import Message, InlineKeyboardMarkup, InlineKeyboardButton
from telegram import Update
from geopy.geocoders import Nominatim
from pyrogram import Client
from db.db import *
from config.config import *
from config.translations import t, get_user_lang
from funcs.utils import *
from funcs.bot_funcs import *
import asyncio

class DealTemplateStates:
    CHOOSE_ACTION = 0
    EDIT_ACTIONS = 1

    EDIT_NAME = 2
    EDIT_TEXT = 3


async def start_dealing_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Using Supabase only
    from db.db import db_client
    
    _, template_id, order_id = update.callback_query.data.split('_')
    print(_, template_id, order_id)
    template_id = int(template_id)
    order_id = int(order_id)

    templates = db_client.select('templates', {'id': template_id})
    orders = db_client.select('orders', {'id': order_id})
    
    template = templates[0] if templates else None
    order = orders[0] if orders else None

    start_msg = await update.effective_message.edit_text(
        text=t("template_info", lang).format(template.get('name'), template.get('text')),
        reply_markup=get_actions_template_kb(lang),
        parse_mode=ParseMode.HTML,
    )
    context.user_data["dealing_template_data"] = {}
    context.user_data["dealing_template_data"]["start_msg"] = start_msg
    context.user_data["dealing_template_data"]["template"] = template
    context.user_data["dealing_template_data"]["order"] = order
    context.user_data["dealing_template_data"]["lang"] = lang

    return DealTemplateStates.CHOOSE_ACTION

async def send_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["dealing_template_data"]["lang"]

    template = context.user_data["dealing_template_data"]["template"]
    order = context.user_data["dealing_template_data"]["order"]
    msg: Message = context.user_data["dealing_template_data"]["start_msg"]

    # Using Supabase only
    from db.db import db_client
    
    # Get fresh data from Supabase
    orders = db_client.select('orders', {'id': order['id']})
    templates = db_client.select('templates', {'id': template['id']})
    tgsessions_list = db_client.select('tgsessions', {'is_worker': True})

    if not tgsessions_list:
        await msg.reply_text(t('no_worker_account', lang))
        return ConversationHandler.END

    tgsession = tgsessions_list[0]
    
    # Get fresh data
    order = orders[0] if orders else order
    template = templates[0] if templates else template

    try:
        client = Client(name='default', api_id=tgsession['api_id'], api_hash=tgsession['api_hash'], session_string=tgsession['string'])

        async with client:
            await client.send_message(order['client_username'], template['text'])

        await msg.reply_text(t('template_sent', lang).format(template['id'], template['name']))
    except Exception as e:
        await update.effective_message.reply_text(t('send_message_error', lang).format(repr(e)))
    finally:
        await msg.delete()

        return ConversationHandler.END

async def delete_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["dealing_template_data"]["lang"]

    template = context.user_data["dealing_template_data"]["template"]

    # Using Supabase only
    from db.db import db_client
    
    db_client.delete('templates', {'id': template['id']})

    msg: Message = context.user_data["dealing_template_data"]["start_msg"]

    await msg.edit_text(t('template_deleted', lang).format(template['name']))

    del context.user_data["dealing_template_data"]

    return ConversationHandler.END

async def editing_template_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["dealing_template_data"]["lang"]

    msg: Message = context.user_data["dealing_template_data"]["start_msg"]

    await msg.edit_reply_markup(get_edit_template_kb(lang))

    return DealTemplateStates.EDIT_ACTIONS

async def editing_template_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data["dealing_template_data"]["lang"]
    await update.callback_query.answer(t('btn_edit_name', lang))
    await update.effective_message.edit_reply_markup(get_cancel_kb(lang))

    return DealTemplateStates.EDIT_NAME


async def editing_template_name_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.delete()
    lang = context.user_data["dealing_template_data"]["lang"]

    name = update.effective_message.text[:22]
    context.user_data["dealing_template_data"]["name"] = name

    # Using Supabase only
    from db.db import db_client
    
    template = context.user_data["dealing_template_data"]["template"]
    
    db_client.update('templates', {'name': name}, {'id': template['id']})
    
    # Update in context
    template['name'] = name
    print(f"Updated template: {template}")

    start_msg: Message = context.user_data["dealing_template_data"]["start_msg"]

    await start_msg.edit_text(
        text=t("template_updated", lang).format(template['name'], template['text']),
        parse_mode=ParseMode.HTML,
        reply_markup=get_actions_template_kb(lang),
    )

    return DealTemplateStates.CHOOSE_ACTION

async def editing_template_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data["dealing_template_data"]["lang"]
    await update.callback_query.answer(t('btn_edit_text', lang))

    await update.effective_message.edit_reply_markup(get_cancel_kb(lang))

    return DealTemplateStates.EDIT_TEXT

async def editing_template_text_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.delete()
    lang = context.user_data["dealing_template_data"]["lang"]

    text = update.effective_message.text
    context.user_data["dealing_template_data"]["text"] = text

    # Using Supabase only
    from db.db import db_client
    
    template = context.user_data["dealing_template_data"]["template"]
    
    db_client.update('templates', {'text': text}, {'id': template['id']})
    
    # Update in context
    template['text'] = text
    print(f"Updated template: {template}")

    start_msg: Message = context.user_data["dealing_template_data"]["start_msg"]

    await start_msg.edit_text(
        text=t("template_updated", lang).format(template['name'], template['text']),
        parse_mode=ParseMode.HTML,
        reply_markup=get_actions_template_kb(lang),
    )

    return DealTemplateStates.CHOOSE_ACTION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["dealing_template_data"]["lang"]
    msg: Message = context.user_data["dealing_template_data"]["start_msg"]
    await msg.delete()  # Delete instead of edit
    del context.user_data["dealing_template_data"]
    
    # Return to main menu
    from funcs.bot_funcs import start
    await start(update, context)

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data["dealing_template_data"]["lang"]
    msg: Message = context.user_data["dealing_template_data"]["start_msg"]
    await msg.reply_text(t("timeout_error", lang))
    del context.user_data["dealing_template_data"]

    return ConversationHandler.END


states = {
    DealTemplateStates.CHOOSE_ACTION: [
        CallbackQueryHandler(send_template, '^send$'),
        CallbackQueryHandler(editing_template_start, '^edit$'),
        CallbackQueryHandler(delete_template, '^delete$'),
    ],
    DealTemplateStates.EDIT_ACTIONS: [
        CallbackQueryHandler(editing_template_name_start, '^edit_name$'),
        CallbackQueryHandler(editing_template_text_start, '^edit_text$'),
    ],
    DealTemplateStates.EDIT_NAME: [
        MessageHandler(filters.Regex('^.+$'), editing_template_name_end)
    ],
    DealTemplateStates.EDIT_TEXT: [
        MessageHandler(filters.Regex('^.+$'), editing_template_text_end)
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


SEND_OR_EDIT_TEMPLATE = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_dealing_template, pattern="shab_*[0-9]_*[0-9]")
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
        CallbackQueryHandler(cancel, '^back$'),  # Terminate conversation on back
        CallbackQueryHandler(cancel, '^home$'),  # Terminate conversation on home
    ],
    conversation_timeout=120,
)