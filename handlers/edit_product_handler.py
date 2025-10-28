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

class EditProductStates:
    CHOOSE_ACTION = 0
    EDIT_STOCK_END = 1

async def start_edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """START function of collecting data for new order."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    product_id = int(update.callback_query.data.split('_')[1])

    # Using Supabase only
    from db.db import get_product_by_id
    
    product = get_product_by_id(product_id)

    start_msg = await update.effective_message.edit_text(t("product_info", lang).format(product.get('name'), product.get('stock')), reply_markup=get_edit_product_kb(lang), parse_mode=ParseMode.HTML)
    context.user_data["edit_product_data"] = {}
    context.user_data["edit_product_data"]["start_msg"] = start_msg
    context.user_data["edit_product_data"]["product"] = product
    context.user_data["edit_product_data"]["lang"] = lang

    return EditProductStates.CHOOSE_ACTION


async def edit_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["edit_product_data"]["lang"]

    msg = context.user_data["edit_product_data"]["start_msg"]
    product: Product = context.user_data["edit_product_data"]["product"]

    await msg.edit_text(t("enter_new_stock", lang).format(product.name))

    return EditProductStates.EDIT_STOCK_END

async def edit_product_stock_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data["edit_product_data"]["lang"]
    new_stock = int(update.effective_message.text[:20])
    await update.effective_message.delete()

    product = context.user_data["edit_product_data"]["product"]

    # Using Supabase only
    from db.db import db_client
    
    db_client.update('products', {'stock': new_stock}, {'id': product['id']})

    msg = context.user_data["edit_product_data"]["start_msg"]

    await msg.edit_text(t("stock_updated", lang).format(product.get('name'), new_stock))

    del context.user_data["edit_product_data"]

    return ConversationHandler.END

async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["edit_product_data"]["lang"]

    product = context.user_data["edit_product_data"]["product"]

    # Using Supabase only
    from db.db import db_client
    
    db_client.delete('products', {'id': product['id']})

    msg = context.user_data["edit_product_data"]["start_msg"]

    await msg.edit_text(t("product_deleted", lang).format(product.get('name')))
    del context.user_data["edit_product_data"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    msg: Message = context.user_data["edit_product_data"]["start_msg"]
    await msg.delete()
    del context.user_data["edit_product_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg: Message = context.user_data["edit_product_data"]["start_msg"]
    await msg.reply_text(t("timeout_error", get_user_lang(update.effective_user.id)))
    del context.user_data["edit_product_data"]

    return ConversationHandler.END


states = {
    EditProductStates.CHOOSE_ACTION: [
        CallbackQueryHandler(edit_product_stock, '^edit_stock$'),
        CallbackQueryHandler(delete_product, '^delete$'),
    ],
    EditProductStates.EDIT_STOCK_END: [
        MessageHandler(filters.Regex(r'^\d+$'), edit_product_stock_end)
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


EDIT_PRODUCT_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_edit_product, '^edit_*[0-9]$'),
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    conversation_timeout=120,
)