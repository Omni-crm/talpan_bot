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

class DelayMinStates:
    WRITE_REASON = 0
    CHOOSE_MIN = 1
    WRITE_MY = 2


async def choose_minutes_courier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выбрать минуты нажатием по кнопке для курьера для выбора задержки.
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Using Supabase only
    from db.db import db_client
    
    users = db_client.select('users', {'user_id': update.effective_user.id})
    if not users or users[0].get('role') not in ['runner', 'admin']:
        await update.effective_message.reply_text(t('need_courier_role', lang))
        return ConversationHandler.END

    start_msg_2 = await update.effective_message.reply_text(t('enter_delay_reason', lang))
    context.user_data["delay_min_data"] = {}
    context.user_data["delay_min_data"]["start_msg"] = await update.effective_message.edit_reply_markup(reply_markup=get_cancel_kb(lang))
    context.user_data["delay_min_data"]["start_msg_2"] = start_msg_2
    context.user_data["delay_min_data"]["lang"] = lang

    order_id = int(update.callback_query.data.replace("delay_min_", ""))

    context.user_data["delay_min_data"]["order_id"] = order_id

    return DelayMinStates.WRITE_REASON


async def write_delay_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

async def delay_minutes_courier_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["delay_min_data"]["lang"]

    delay_minutes = int(update.callback_query.data)

    order_id = context.user_data["delay_min_data"]["order_id"]

    # Using Supabase only
    from db.db import db_client
    
    # Update order
    db_client.update('orders', {
        'courier_id': update.effective_user.id,
        'courier_name': f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip(),
        'courier_username': f"@{update.effective_user.username}" if update.effective_user.username else "",
        'delay_minutes': delay_minutes,
        'delay_reason': context.user_data["delay_min_data"]["delay_reason"],
        'status': 'delay'
    }, {'id': order_id})

    # Get updated order for compatibility
    orders = db_client.select('orders', {'id': order_id})
    order_dict = orders[0] if orders else {}
    
    class OrderObj:
        def __init__(self, data):
            self.id = data.get('id')
            for k, v in data.items():
                if k == 'status':
                    setattr(self, k, type('Status', (), {'value': v})())
                else:
                    setattr(self, k, v)
    
    order = OrderObj(order_dict)

    msg: Message = context.user_data["delay_min_data"]["start_msg"]

    try:
        text = await form_confirm_order_courier(order, lang)
        context.user_data["delay_min_data"]["start_msg"] = await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=(await form_courier_action_kb(order_id, lang)))

        status_text = t("order_status", lang)
        changed_text = t("changed_to", lang)
        from db.db import get_bot_setting
        admin_chat = get_bot_setting('admin_chat') or links.ADMIN_CHAT
        if admin_chat:
            info_text = f"<b>{status_text}</b> <i>#{order_id}</i> {changed_text} <i>{order.status.value}</i>"
            await context.bot.send_message(admin_chat, info_text, parse_mode=ParseMode.HTML)

            text = await form_confirm_order_courier_info(order, 'ru')  # לקבוצת אדמינים תמיד ברוסית
            await context.bot.send_message(admin_chat, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"Error: {e}")
    del context.user_data["delay_min_data"]

    return ConversationHandler.END

async def write_delay_minutes_courier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Написать текстом количество минут
    """
    await update.callback_query.answer()
    lang = context.user_data["delay_min_data"]["lang"]

    context.user_data["delay_min_data"]["trash"] = []
    context.user_data["delay_min_data"]["trash"].append(await update.effective_message.reply_text(t('enter_minutes', lang)))
    context.user_data["delay_min_data"]["start_msg"] = await update.effective_message.edit_reply_markup(reply_markup=get_cancel_kb(lang))

    return DelayMinStates.WRITE_MY

async def write_delay_minutes_courier_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    minutes = int(update.effective_message.text)
    lang = context.user_data["delay_min_data"]["lang"]

    order_id = context.user_data["delay_min_data"]["order_id"]

    # Using Supabase only
    from db.db import db_client, get_opened_shift
    
    # Update order
    db_client.update('orders', {
        'courier_id': update.effective_user.id,
        'courier_name': f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip(),
        'courier_username': f"@{update.effective_user.username}" if update.effective_user.username else "",
        'delay_minutes': minutes,
        'delay_reason': context.user_data["delay_min_data"]["delay_reason"],
        'status': 'delay'
    }, {'id': order_id})

    # Get updated order for compatibility
    orders = db_client.select('orders', {'id': order_id})
    order_dict = orders[0] if orders else {}
    
    class OrderObj:
        def __init__(self, data):
            self.id = data.get('id')
            for k, v in data.items():
                if k == 'status':
                    setattr(self, k, type('Status', (), {'value': v})())
                else:
                    setattr(self, k, v)
    
    order = OrderObj(order_dict)

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

        shift = get_opened_shift()

        if shift:
            try:
                operator_lang = get_user_lang(shift['operator_id'])
                await context.bot.send_message(shift['operator_id'], (await form_notif_delay_short(order, operator_lang)), parse_mode=ParseMode.HTML)
            except Exception as e:
                print(repr(e))
    except Exception as e:
        print(f"Error: {e}")
    del context.user_data["delay_min_data"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["delay_min_data"]["lang"]
    msg: Message = context.user_data["delay_min_data"]["start_msg"]
    order_id: int = context.user_data["delay_min_data"]["order_id"]
    markup = await form_courier_action_kb(order_id, lang)
    await msg.edit_reply_markup(markup)
    del context.user_data["delay_min_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        CallbackQueryHandler(delay_minutes_courier_end, pattern=r"^\d+$"),
        CallbackQueryHandler(write_delay_minutes_courier, pattern="^my$"),
    ],
    DelayMinStates.WRITE_MY: [
        MessageHandler(filters.Regex(r'^\d+$'), write_delay_minutes_courier_end),
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
        CallbackQueryHandler(cancel, '^back$'),  # Terminate conversation on back
        CallbackQueryHandler(cancel, '^home$'),  # Terminate conversation on home
    ],
    conversation_timeout=120,
)