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

    session = Session()

    _, template_id, order_id = update.callback_query.data.split('_')
    print(_, template_id, order_id)
    template_id = int(template_id)
    order_id = int(order_id)

    template: Template = session.query(Template).get(template_id)
    order = session.query(Order).get(order_id)

    start_msg = await update.effective_message.edit_text(
        text=t("template_info", lang).format(template.name, template.text),
        reply_markup=get_actions_template_kb(lang),
        parse_mode=ParseMode.HTML,
    )
    context.user_data["dealing_template_data"] = {}
    context.user_data["dealing_template_data"]["start_msg"] = start_msg
    context.user_data["dealing_template_data"]["template"] = template
    context.user_data["dealing_template_data"]["order"] = order
    context.user_data["dealing_template_data"]["lang"] = lang

    return DealTemplateStates.CHOOSE_ACTION

async def send_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["dealing_template_data"]["lang"]

    template: Template = context.user_data["dealing_template_data"]["template"]
    order: Order = context.user_data["dealing_template_data"]["order"]
    msg: Message = context.user_data["dealing_template_data"]["start_msg"]

    session = Session()
    order = session.query(Order).get(order.id)
    template = session.query(Template).get(template.id)

    tgsession = session.query(TgSession).filter_by(is_worker=True).first()

    if not tgsession:
        await msg.reply_text(t('no_worker_account', lang))
        session.close()
        return ConversationHandler.END

    try:
        client = Client(name='default', api_id=tgsession.api_id, api_hash=tgsession.api_hash, session_string=tgsession.string)

        async with client:
            await client.send_message(order.client_username, template.text)

        await msg.reply_text(t('template_sent', lang).format(template.id, template.name))
    except Exception as e:
        await update.effective_message.reply_text(t('send_message_error', lang).format(repr(e)))
    finally:
        session.close()
        await msg.delete()

        return ConversationHandler.END

async def delete_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["dealing_template_data"]["lang"]

    template: Template = context.user_data["dealing_template_data"]["template"]

    session = Session()
    template = session.query(Template).get(template.id)


    session.delete(template)
    session.flush()
    session.commit()

    msg: Message = context.user_data["dealing_template_data"]["start_msg"]

    await msg.edit_text(t('template_deleted', lang).format(template.name))
    session.close()

    del context.user_data["dealing_template_data"]

    return ConversationHandler.END

async def editing_template_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["dealing_template_data"]["lang"]

    msg: Message = context.user_data["dealing_template_data"]["start_msg"]

    await msg.edit_reply_markup(get_edit_template_kb(lang))

    return DealTemplateStates.EDIT_ACTIONS

async def editing_template_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["dealing_template_data"]["lang"]
    await update.callback_query.answer(t('btn_edit_name', lang))
    await update.effective_message.edit_reply_markup(get_cancel_kb(lang))

    return DealTemplateStates.EDIT_NAME


async def editing_template_name_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.delete()
    lang = context.user_data["dealing_template_data"]["lang"]

    name = update.effective_message.text[:22]
    context.user_data["dealing_template_data"]["name"] = name

    session = Session()

    template: Template = context.user_data["dealing_template_data"]["template"]

    template = session.query(Template).get(template.id)
    template.name = name
    session.commit()
    print(template)

    start_msg: Message = context.user_data["dealing_template_data"]["start_msg"]

    await start_msg.edit_text(
        text=t("template_updated", lang).format(template.name, template.text),
        parse_mode=ParseMode.HTML,
        reply_markup=get_actions_template_kb(lang),
    )
    session.close()

    return DealTemplateStates.CHOOSE_ACTION

async def editing_template_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["dealing_template_data"]["lang"]
    await update.callback_query.answer(t('btn_edit_text', lang))

    await update.effective_message.edit_reply_markup(get_cancel_kb(lang))

    return DealTemplateStates.EDIT_TEXT

async def editing_template_text_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.delete()
    lang = context.user_data["dealing_template_data"]["lang"]

    text = update.effective_message.text
    context.user_data["dealing_template_data"]["text"] = text

    session = Session()

    template: Template = context.user_data["dealing_template_data"]["template"]
    template = session.query(Template).get(template.id)
    template.text = text
    session.commit()
    print(template)

    start_msg: Message = context.user_data["dealing_template_data"]["start_msg"]

    await start_msg.edit_text(
        text=t("template_updated", lang).format(template.name, template.text),
        parse_mode=ParseMode.HTML,
        reply_markup=get_actions_template_kb(lang),
    )
    session.close()

    return DealTemplateStates.CHOOSE_ACTION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["dealing_template_data"]["lang"]
    msg: Message = context.user_data["dealing_template_data"]["start_msg"]
    await msg.edit_text(t('cancelled', lang))
    del context.user_data["dealing_template_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    ],
    conversation_timeout=120,
)