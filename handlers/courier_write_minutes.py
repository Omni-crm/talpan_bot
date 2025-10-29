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

class WriteMinStates:
    WRITE_MIN = 0


async def choose_minutes_courier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выбрать минуты нажатием по кнопке для курьера до выполнения заказа.
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Using Supabase only
    from db.db import db_client
    
    users = db_client.select('users', {'user_id': update.effective_user.id})
    if not users or users[0].get('role') not in ['runner', 'admin']:
        await update.effective_message.reply_text(t('need_courier_role', lang))
        return ConversationHandler.END

    start_msg = await update.effective_message.edit_reply_markup(reply_markup=get_cancel_kb(lang))
    context.user_data["choose_min_data"] = {}
    context.user_data["choose_min_data"]["start_msg"] = start_msg
    context.user_data["choose_min_data"]["lang"] = lang

    order_id = int(update.callback_query.data.replace("write_min_", ""))

    context.user_data["choose_min_data"]["order_id"] = order_id

    return WriteMinStates.WRITE_MIN

async def write_minutes_courier_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    minutes = int(update.effective_message.text)
    lang = context.user_data["choose_min_data"]["lang"]

    order_id = context.user_data["choose_min_data"]["order_id"]

    # Using Supabase only
    from db.db import db_client, get_opened_shift
    
    # Update order
    db_client.update('orders', {
        'courier_id': update.effective_user.id,
        'courier_name': f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip(),
        'courier_username': f"@{update.effective_user.username}" if update.effective_user.username else "",
        'courier_minutes': minutes,
        'status': 'active'
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

    msg: Message = context.user_data["choose_min_data"]["start_msg"]

    try:
        text = await form_confirm_order_courier(order, lang)
        context.user_data["choose_min_data"]["start_msg"] = await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=(await form_courier_action_kb(order.id, lang)))

        shift = get_opened_shift()

        if shift:
            try:
                operator_lang = get_user_lang(shift['operator_id'])
                await context.bot.send_message(shift['operator_id'], (await form_notif_ready_order_short(order, operator_lang)), reply_markup=(await form_operator_action_kb(order, operator_lang)), parse_mode=ParseMode.HTML)
            except Exception as e:
                print(repr(e))
    except Exception as e:
        print(f"Error: {e}")
    del context.user_data["choose_min_data"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["choose_min_data"]["lang"]
    msg: Message = context.user_data["choose_min_data"]["start_msg"]
    order_id: int = context.user_data["choose_min_data"]["order_id"]
    markup = await form_courier_action_kb(order_id, lang)
    await msg.edit_reply_markup(markup)
    del context.user_data["choose_min_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        MessageHandler(filters.Regex(r'^\d+$'), write_minutes_courier_end),
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
        CallbackQueryHandler(cancel, '^back$'),  # Terminate conversation on back
        CallbackQueryHandler(cancel, '^home$'),  # Terminate conversation on home
    ],
    conversation_timeout=120,
)