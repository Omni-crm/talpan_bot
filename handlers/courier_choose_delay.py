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
    import logging
    logger = logging.getLogger(__name__)

    # Using Supabase only
    from db.db import db_client
    
    # CRITICAL: Validate user role
    users = db_client.select('users', {'user_id': update.effective_user.id})
    # CRITICAL FIX: Use 'courier' (Role.RUNNER.value) not 'runner'!
    # Role.RUNNER = "courier" in db/db.py
    if not users or users[0].get('role') not in ['courier', 'admin']:
        logger.warning(f"⚠️ choose_minutes_courier (delay): User {update.effective_user.id} does not have courier role")
        await update.effective_message.reply_text(t('need_courier_role', lang))
        return ConversationHandler.END

    # CRITICAL: Validate and parse order_id
    try:
        callback_data = update.callback_query.data
        if not callback_data or not callback_data.startswith("delay_min_"):
            raise ValueError(f"Invalid callback data: {callback_data}")
        
        order_id_str = callback_data.replace("delay_min_", "").strip()
        if not order_id_str:
            raise ValueError("Empty order ID")
        
        order_id = int(order_id_str)
        if order_id <= 0:
            raise ValueError(f"Invalid order ID: {order_id} (must be > 0)")
    except (ValueError, AttributeError, TypeError) as e:
        logger.error(f"❌ choose_minutes_courier (delay): Invalid order ID parsing: {repr(e)}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Invalid order ID format"
        )
        return ConversationHandler.END
    
    # CRITICAL: Verify order exists before proceeding
    orders = db_client.select('orders', {'id': order_id})
    if not orders:
        logger.error(f"❌ choose_minutes_courier (delay): Order {order_id} not found in database")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Order #{order_id} not found"
        )
        return ConversationHandler.END

    try:
        start_msg_2 = await update.effective_message.reply_text(t('enter_delay_reason', lang))
        start_msg = await update.effective_message.edit_reply_markup(reply_markup=get_cancel_kb(lang))
    except Exception as e:
        logger.error(f"❌ choose_minutes_courier (delay): Failed to edit/send message: {repr(e)}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Failed to start delay process"
        )
        return ConversationHandler.END
    
    context.user_data["delay_min_data"] = {}
    context.user_data["delay_min_data"]["start_msg"] = start_msg
    context.user_data["delay_min_data"]["start_msg_2"] = start_msg_2
    context.user_data["delay_min_data"]["lang"] = lang
    context.user_data["delay_min_data"]["order_id"] = order_id

    logger.info(f"✅ choose_minutes_courier (delay): Started for order {order_id}")
    return DelayMinStates.WRITE_REASON


async def write_delay_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    import logging
    logger = logging.getLogger(__name__)
    
    # CRITICAL: Validate context.user_data exists
    if "delay_min_data" not in context.user_data:
        logger.error("❌ write_delay_reason: delay_min_data not in context.user_data")
        if update.effective_message:
            await update.effective_message.reply_text(
                f"⚠️ {t('error', 'ru')}: Session expired. Please try again."
            )
        return ConversationHandler.END
    
    # CRITICAL: Validate required keys exist
    start_msg = context.user_data["delay_min_data"].get("start_msg")
    start_msg_2 = context.user_data["delay_min_data"].get("start_msg_2")
    lang = context.user_data["delay_min_data"].get("lang", "ru")
    
    if not start_msg or not start_msg_2:
        logger.error("❌ write_delay_reason: Missing start_msg or start_msg_2")
        if update.effective_message:
            await update.effective_message.reply_text(
                f"⚠️ {t('error', lang)}: Session data corrupted. Please try again."
            )
        return ConversationHandler.END
    
    # SECURITY FIX: Sanitize delay_reason to prevent HTML injection
    if update.effective_message and update.effective_message.voice:
        chat_id = str(update.effective_chat.id).replace('-100', '')
        link_to_message = f'https://t.me/c/{chat_id}/{update.effective_message.id}'
        # Safe HTML link - Telegram URL format is safe
        delay_reason = f"<a href='{link_to_message}'>Ссылка на голосовое</a>"
        context.user_data["delay_min_data"]["delay_reason"] = delay_reason
    else:
        # SECURITY: Escape HTML special characters to prevent XSS
        import html
        raw_text = update.effective_message.text if update.effective_message and update.effective_message.text else ""
        # Escape HTML entities but allow safe formatting if needed
        delay_reason = html.escape(raw_text) if raw_text else ""
        context.user_data["delay_min_data"]["delay_reason"] = delay_reason

    from config.kb import get_delay_minutes_kb
    try:
        context.user_data["delay_min_data"]["start_msg"] = await start_msg.edit_reply_markup(reply_markup=get_delay_minutes_kb(lang))
    except Exception as e:
        logger.error(f"❌ write_delay_reason: Failed to edit markup: {repr(e)}")
        return ConversationHandler.END

    try:
        await start_msg_2.delete()
        await asyncio.sleep(0.1)
        await update.effective_message.delete()
    except: pass

    return DelayMinStates.CHOOSE_MIN

async def delay_minutes_courier_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    import logging
    logger = logging.getLogger(__name__)
    
    # CRITICAL: Validate context.user_data exists
    if "delay_min_data" not in context.user_data:
        logger.error("❌ delay_minutes_courier_end: delay_min_data not in context.user_data")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', 'ru')}: Session expired. Please try again."
        )
        return ConversationHandler.END
    
    lang = context.user_data["delay_min_data"].get("lang", "ru")
    order_id = context.user_data["delay_min_data"].get("order_id")
    delay_reason = context.user_data["delay_min_data"].get("delay_reason", "")
    
    # CRITICAL: Validate order_id exists
    if not order_id or not isinstance(order_id, int) or order_id <= 0:
        logger.error(f"❌ delay_minutes_courier_end: Invalid order_id in context: {order_id}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Invalid session data. Please try again."
        )
        return ConversationHandler.END
    
    # CRITICAL: Validate delay_reason exists
    if not delay_reason or not delay_reason.strip():
        logger.error(f"❌ delay_minutes_courier_end: Missing delay_reason for order {order_id}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Delay reason is missing. Please start over."
        )
        return ConversationHandler.END

    # CRITICAL: Validate delay minutes input (1-9999 range)
    try:
        delay_minutes = int(update.callback_query.data)
        if not (1 <= delay_minutes <= 9999):
            logger.warning(f"⚠️ delay_minutes_courier_end: Delay minutes out of range: {delay_minutes}")
            await update.effective_message.reply_text(
                t('invalid_minutes_range', lang) if hasattr(t, 'invalid_minutes_range') else 
                f"⚠️ {t('error', lang)}: Delay minutes must be between 1 and 9999"
            )
            return ConversationHandler.END
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"❌ delay_minutes_courier_end: Invalid delay minutes format: {repr(e)}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Invalid delay minutes format"
        )
        return ConversationHandler.END

    # Using Supabase only
    from db.db import db_client
    import logging
    logger = logging.getLogger(__name__)
    
    # Update order with error handling
    update_result = db_client.update('orders', {
        'courier_id': update.effective_user.id,
        'courier_name': f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip(),
        'courier_username': f"@{update.effective_user.username}" if update.effective_user.username else "",
        'delay_minutes': delay_minutes,
        'delay_reason': context.user_data["delay_min_data"].get("delay_reason", ""),
        'status': 'delay'
    }, {'id': order_id})
    
    # CRITICAL: Verify update succeeded
    if not update_result:
        logger.error(f"❌ delay_minutes_courier_end: Failed to update order {order_id}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Failed to update order. Please try again."
        )
        return ConversationHandler.END

    # Get updated order for compatibility
    orders = db_client.select('orders', {'id': order_id})
    if not orders:
        logger.error(f"❌ delay_minutes_courier_end: Order {order_id} not found after update")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Order not found after update"
        )
        return ConversationHandler.END
    
    order_dict = orders[0]
    
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
            # Send BILINGUAL status update (RU + HE)
            status_ru = t("order_status", 'ru')
            status_he = t("order_status", 'he')
            changed_ru = t("changed_to", 'ru')
            changed_he = t("changed_to", 'he')
            info_text = f"<b>{status_ru} | {status_he}</b> <i>#{order_id}</i> {changed_ru} | {changed_he} <i>{order.status.value}</i>"
            await context.bot.send_message(admin_chat, info_text, parse_mode=ParseMode.HTML)

            text = await form_confirm_order_courier_info(order, 'ru')  # Send BILINGUAL message to admin group (RU + HE)
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
    import logging
    logger = logging.getLogger(__name__)
    
    # CRITICAL: Validate context.user_data exists
    if "delay_min_data" not in context.user_data:
        logger.error("❌ write_delay_minutes_courier: delay_min_data not in context.user_data")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', 'ru')}: Session expired. Please try again."
        )
        return ConversationHandler.END
    
    lang = context.user_data["delay_min_data"].get("lang", "ru")
    start_msg = context.user_data["delay_min_data"].get("start_msg")
    
    if not start_msg:
        logger.error("❌ write_delay_minutes_courier: Missing start_msg")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Session data corrupted. Please try again."
        )
        return ConversationHandler.END

    try:
        if "trash" not in context.user_data["delay_min_data"]:
            context.user_data["delay_min_data"]["trash"] = []
        context.user_data["delay_min_data"]["trash"].append(await update.effective_message.reply_text(t('enter_minutes', lang)))
        context.user_data["delay_min_data"]["start_msg"] = await start_msg.edit_reply_markup(reply_markup=get_cancel_kb(lang))
    except Exception as e:
        logger.error(f"❌ write_delay_minutes_courier: Failed to update messages: {repr(e)}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Failed to load input prompt"
        )
        return ConversationHandler.END

    return DelayMinStates.WRITE_MY

async def write_delay_minutes_courier_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    import logging
    logger = logging.getLogger(__name__)
    
    # CRITICAL: Validate context.user_data exists
    if "delay_min_data" not in context.user_data:
        logger.error("❌ write_delay_minutes_courier_end: delay_min_data not in context.user_data")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', 'ru')}: Session expired. Please try again."
        )
        return ConversationHandler.END
    
    lang = context.user_data["delay_min_data"].get("lang", "ru")
    order_id = context.user_data["delay_min_data"].get("order_id")
    delay_reason = context.user_data["delay_min_data"].get("delay_reason", "")
    
    # CRITICAL: Validate order_id exists
    if not order_id or not isinstance(order_id, int) or order_id <= 0:
        logger.error(f"❌ write_delay_minutes_courier_end: Invalid order_id in context: {order_id}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Invalid session data. Please try again."
        )
        return ConversationHandler.END
    
    # CRITICAL: Validate delay_reason exists
    if not delay_reason or not delay_reason.strip():
        logger.error(f"❌ write_delay_minutes_courier_end: Missing delay_reason for order {order_id}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Delay reason is missing. Please start over."
        )
        return ConversationHandler.END
    
    # CRITICAL: Validate delay minutes input (1-9999 range)
    try:
        if not update.effective_message or not update.effective_message.text:
            raise ValueError("No message text")
        
        minutes = int(update.effective_message.text.strip())
        if not (1 <= minutes <= 9999):
            logger.warning(f"⚠️ write_delay_minutes_courier_end: Delay minutes out of range: {minutes}")
            await update.effective_message.reply_text(
                t('invalid_minutes_range', lang) if hasattr(t, 'invalid_minutes_range') else 
                f"⚠️ {t('error', lang)}: Delay minutes must be between 1 and 9999"
            )
            return ConversationHandler.END
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"❌ write_delay_minutes_courier_end: Invalid delay minutes format: {repr(e)}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Please enter a valid number between 1 and 9999"
        )
        return ConversationHandler.END

    # Using Supabase only
    from db.db import db_client, get_opened_shift
    
    # Update order with error handling
    update_result = db_client.update('orders', {
        'courier_id': update.effective_user.id,
        'courier_name': f"{update.effective_user.first_name} {update.effective_user.last_name if update.effective_user.last_name else ''}".strip(),
        'courier_username': f"@{update.effective_user.username}" if update.effective_user.username else "",
        'delay_minutes': minutes,
        'delay_reason': context.user_data["delay_min_data"].get("delay_reason", ""),
        'status': 'delay'
    }, {'id': order_id})
    
    # CRITICAL: Verify update succeeded
    if not update_result:
        logger.error(f"❌ write_delay_minutes_courier_end: Failed to update order {order_id}")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Failed to update order. Please try again."
        )
        return ConversationHandler.END

    # Get updated order for compatibility
    orders = db_client.select('orders', {'id': order_id})
    if not orders:
        logger.error(f"❌ write_delay_minutes_courier_end: Order {order_id} not found after update")
        await update.effective_message.reply_text(
            f"⚠️ {t('error', lang)}: Order not found after update"
        )
        return ConversationHandler.END
    
    order_dict = orders[0]
    
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
    import logging
    logger = logging.getLogger(__name__)
    
    # CRITICAL: Validate context.user_data exists
    if "delay_min_data" not in context.user_data:
        logger.warning("⚠️ cancel (delay): delay_min_data not in context.user_data")
        return ConversationHandler.END
    
    lang = context.user_data["delay_min_data"].get("lang", "ru")
    order_id = context.user_data["delay_min_data"].get("order_id")
    start_msg = context.user_data["delay_min_data"].get("start_msg")
    
    if not order_id or not start_msg:
        logger.warning(f"⚠️ cancel (delay): Missing order_id or start_msg")
        return ConversationHandler.END
    
    try:
        markup = await form_courier_action_kb(order_id, lang)
        await start_msg.edit_reply_markup(markup)
    except Exception as e:
        logger.error(f"❌ cancel (delay): Failed to restore markup: {repr(e)}")
    
    # Clean up delay_min_data
    if "delay_min_data" in context.user_data:
        if context.user_data["delay_min_data"].get("start_msg_2"):
            try:
                await context.user_data["delay_min_data"]["start_msg_2"].delete()
            except:
                pass
        if context.user_data["delay_min_data"].get("trash"):
            for msg in context.user_data["delay_min_data"]["trash"]:
                try:
                    await msg.delete()
                except:
                    pass
        del context.user_data["delay_min_data"]
    
    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    import logging
    logger = logging.getLogger(__name__)
    
    # CRITICAL: Validate context.user_data exists
    if "delay_min_data" not in context.user_data:
        logger.warning("⚠️ timeout_reached (delay): delay_min_data not in context.user_data")
        return ConversationHandler.END
    
    lang = context.user_data["delay_min_data"].get("lang", "ru")
    order_id = context.user_data["delay_min_data"].get("order_id")
    start_msg = context.user_data["delay_min_data"].get("start_msg")
    
    if not order_id or not start_msg:
        logger.warning(f"⚠️ timeout_reached (delay): Missing order_id or start_msg")
        return ConversationHandler.END
    
    try:
        markup = await form_courier_action_kb(order_id, lang)
        await start_msg.edit_reply_markup(markup)
        await start_msg.reply_text(t("timeout_error", lang))
    except Exception as e:
        logger.error(f"❌ timeout_reached (delay): Failed to restore markup: {repr(e)}")
    
    # Clean up delay_min_data
    if "delay_min_data" in context.user_data:
        if context.user_data["delay_min_data"].get("start_msg_2"):
            try:
                await context.user_data["delay_min_data"]["start_msg_2"].delete()
            except:
                pass
        if context.user_data["delay_min_data"].get("trash"):
            for msg in context.user_data["delay_min_data"]["trash"]:
                try:
                    await msg.delete()
                except:
                    pass
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