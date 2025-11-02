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

class TapMinStates:
    CHOOSE_MIN = 0


async def choose_minutes_courier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выбрать минуты нажатием по кнопке для курьера до выполнения заказа.
    """
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    import logging
    logger = logging.getLogger(__name__)

    # Using Supabase only
    from db.db import db_client
    
    # CRITICAL: Validate user role
    users = db_client.select('users', {'user_id': update.effective_user.id})
    # CRITICAL FIX: Use 'courier' (Role.RUNNER.value) not 'runner'!
    # Role.RUNNER = "courier" in db/db.py
    if not users or users[0].get('role') not in ['courier', 'admin']:
        logger.warning(f"⚠️ choose_minutes_courier: User {update.effective_user.id} does not have courier role")
        await update.effective_message.reply_text(t('need_courier_role', lang))
        return ConversationHandler.END

    # CRITICAL: Validate and parse order_id
    try:
        callback_data = update.callback_query.data
        if not callback_data or not callback_data.startswith("choose_min_"):
            raise ValueError(f"Invalid callback data: {callback_data}")
        
        order_id_str = callback_data.replace("choose_min_", "").strip()
        if not order_id_str:
            raise ValueError("Empty order ID")
        
        order_id = int(order_id_str)
        if order_id <= 0:
            raise ValueError(f"Invalid order ID: {order_id} (must be > 0)")
    except (ValueError, AttributeError, TypeError) as e:
        logger.error(f"❌ choose_minutes_courier: Invalid order ID parsing: {repr(e)}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Invalid order ID format"
        )
        return ConversationHandler.END
    
    # CRITICAL: Verify order exists before proceeding
    orders = db_client.select('orders', {'id': order_id})
    if not orders:
        logger.error(f"❌ choose_minutes_courier: Order {order_id} not found in database")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Order #{order_id} not found"
        )
        return ConversationHandler.END

    from config.kb import get_courier_minutes_kb
    try:
        start_msg = await update.effective_message.edit_reply_markup(reply_markup=get_courier_minutes_kb(lang))
    except Exception as e:
        logger.error(f"❌ choose_minutes_courier: Failed to edit message: {repr(e)}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Failed to load minutes selection"
        )
        return ConversationHandler.END
    
    context.user_data["choose_min_data"] = {}
    context.user_data["choose_min_data"]["start_msg"] = start_msg
    context.user_data["choose_min_data"]["lang"] = lang
    context.user_data["choose_min_data"]["order_id"] = order_id

    logger.info(f"✅ choose_minutes_courier: Started for order {order_id}")
    return TapMinStates.CHOOSE_MIN

async def choose_minutes_courier_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    import logging
    logger = logging.getLogger(__name__)
    
    # CRITICAL: Validate context.user_data exists
    if "choose_min_data" not in context.user_data:
        logger.error("❌ choose_minutes_courier_end: choose_min_data not in context.user_data")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', 'ru')}: Session expired. Please try again."
        )
        return
    
    lang = context.user_data["choose_min_data"].get("lang", "ru")
    order_id = context.user_data["choose_min_data"].get("order_id")
    
    # CRITICAL: Validate order_id exists
    if not order_id or not isinstance(order_id, int) or order_id <= 0:
        logger.error(f"❌ choose_minutes_courier_end: Invalid order_id in context: {order_id}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Invalid session data. Please try again."
        )
        return
    
    # CRITICAL: Validate minutes input (1-9999 range)
    try:
        minutes = int(update.callback_query.data)
        if not (1 <= minutes <= 9999):
            logger.warning(f"⚠️ choose_minutes_courier_end: Minutes out of range: {minutes}")
            await update.effective_message.reply_text(
                t('invalid_minutes_range', lang) if hasattr(t, 'invalid_minutes_range') else 
                f"⚠️ {t('error', lang)}: Minutes must be between 1 and 9999"
            )
            return
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"❌ choose_minutes_courier_end: Invalid minutes format: {repr(e)}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Invalid minutes format"
        )
        return

    # Using Supabase only
    from db.db import db_client, get_opened_shift
    
    # Update order with error handling
    update_result = db_client.update('orders', {
        'courier_id': update.effective_user.id,
        'courier_name': f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip(),
        'courier_username': f"@{update.effective_user.username}" if update.effective_user.username else "",
        'courier_minutes': minutes,
        'status': 'active'
    }, {'id': order_id})
    
    # CRITICAL: Verify update succeeded
    if not update_result:
        logger.error(f"❌ choose_minutes_courier_end: Failed to update order {order_id} - update returned empty")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Failed to update order. Please try again."
        )
        return

    # CRITICAL: Verify order was actually updated
    orders = db_client.select('orders', {'id': order_id})
    if not orders:
        logger.error(f"❌ choose_minutes_courier_end: Order {order_id} not found after update")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Order not found after update"
        )
        return
    
    order_dict = orders[0]
    
    # CRITICAL: Verify order status and courier_minutes were updated
    if order_dict.get('status') != 'active' or order_dict.get('courier_minutes') != minutes:
        logger.error(f"❌ choose_minutes_courier_end: Order {order_id} verification failed - status={order_dict.get('status')}, minutes={order_dict.get('courier_minutes')}, expected={minutes}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Order update verification failed. Please try again."
        )
        return
    
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
    import logging
    logger = logging.getLogger(__name__)
    
    # CRITICAL: Validate context.user_data exists
    if "choose_min_data" not in context.user_data:
        logger.warning("⚠️ cancel (choose_minutes): choose_min_data not in context.user_data")
        return ConversationHandler.END
    
    lang = context.user_data["choose_min_data"].get("lang", "ru")
    order_id = context.user_data["choose_min_data"].get("order_id")
    start_msg = context.user_data["choose_min_data"].get("start_msg")
    
    if not order_id or not start_msg:
        logger.warning(f"⚠️ cancel (choose_minutes): Missing order_id or start_msg")
        return ConversationHandler.END
    
    try:
        markup = await form_courier_action_kb(order_id, lang)
        await start_msg.edit_reply_markup(markup)
    except Exception as e:
        logger.error(f"❌ cancel (choose_minutes): Failed to restore markup: {repr(e)}")
    
    del context.user_data["choose_min_data"]
    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    import logging
    logger = logging.getLogger(__name__)
    
    # CRITICAL: Validate context.user_data exists
    if "choose_min_data" not in context.user_data:
        logger.warning("⚠️ timeout_reached (choose_minutes): choose_min_data not in context.user_data")
        return ConversationHandler.END
    
    lang = context.user_data["choose_min_data"].get("lang", "ru")
    order_id = context.user_data["choose_min_data"].get("order_id")
    start_msg = context.user_data["choose_min_data"].get("start_msg")
    
    if not order_id or not start_msg:
        logger.warning(f"⚠️ timeout_reached (choose_minutes): Missing order_id or start_msg")
        return ConversationHandler.END
    
    try:
        markup = await form_courier_action_kb(order_id, lang)
        await start_msg.edit_reply_markup(markup)
        await start_msg.reply_text(t("timeout_error", lang))
    except Exception as e:
        logger.error(f"❌ timeout_reached (choose_minutes): Failed to restore markup: {repr(e)}")
    
    del context.user_data["choose_min_data"]
    return ConversationHandler.END


states = {
    TapMinStates.CHOOSE_MIN: [
        CallbackQueryHandler(choose_minutes_courier_end, pattern=r"^\d+$"),
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


CHOOSE_MINUTES_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(choose_minutes_courier, pattern="choose_min_*[0-9]")
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
        CallbackQueryHandler(cancel, '^back$'),  # Terminate conversation on back
        CallbackQueryHandler(cancel, '^home$'),  # Terminate conversation on home
    ],
    conversation_timeout=120,
)