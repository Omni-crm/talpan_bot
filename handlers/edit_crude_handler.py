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

class EditCrudeStockStates:
    CHOOSE_ACTION = 0
    EDIT_STOCK_END = 1
    EDIT_CRUDE_END = 2

async def start_edit_crude_stock_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """START function of collecting data for new order."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    product_id = int(update.callback_query.data.split('_')[2])

    # Using Supabase only
    from db.db import db_client, get_product_by_id
    
    # Check if user is stockman or admin
    users = db_client.select('users', {'user_id': update.effective_user.id})
    if not users or users[0].get('role') not in ['stockman', 'admin']:
        await update.effective_message.reply_text(t('need_stockman_role', lang))
        return ConversationHandler.END

    product = get_product_by_id(product_id)

    start_msg = await update.effective_message.edit_text(t("product_crude_info", lang).format(product.get('name'), product.get('crude'), product.get('stock')), reply_markup=get_edit_product_crude_kb(lang), parse_mode=ParseMode.HTML)
    context.user_data["edit_product_with_crude_data"] = {}
    context.user_data["edit_product_with_crude_data"]["start_msg"] = start_msg
    context.user_data["edit_product_with_crude_data"]["product"] = product
    context.user_data["edit_product_with_crude_data"]["lang"] = lang

    return EditCrudeStockStates.CHOOSE_ACTION


async def edit_product_crude(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["edit_product_with_crude_data"]["lang"]

    msg = context.user_data["edit_product_with_crude_data"]["start_msg"]
    product: Product = context.user_data["edit_product_with_crude_data"]["product"]

    await msg.edit_text(t("enter_new_crude", lang).format(product.name))

    return EditCrudeStockStates.EDIT_CRUDE_END

async def edit_product_crude_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data["edit_product_with_crude_data"]["lang"]
    new_stock = int(update.effective_message.text[:20])
    await update.effective_message.delete()

    product = context.user_data["edit_product_with_crude_data"]["product"]

    # Using Supabase only
    from db.db import db_client
    
    db_client.update('products', {'crude': new_stock}, {'id': product['id']})

    msg: Message = context.user_data["edit_product_with_crude_data"]["start_msg"]

    await msg.edit_text(t("crude_updated", lang).format(product.get('name'), new_stock), reply_markup=get_products_markup_left_edit_stock_crude())

    del context.user_data["edit_product_with_crude_data"]

    return ConversationHandler.END


async def edit_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["edit_product_with_crude_data"]["lang"]

    msg = context.user_data["edit_product_with_crude_data"]["start_msg"]
    product: Product = context.user_data["edit_product_with_crude_data"]["product"]

    await msg.edit_text(t("enter_new_stock", lang).format(product.name))

    return EditCrudeStockStates.EDIT_STOCK_END

async def edit_product_stock_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data["edit_product_with_crude_data"]["lang"]
    new_stock = int(update.effective_message.text[:20])
    await update.effective_message.delete()

    product = context.user_data["edit_product_with_crude_data"]["product"]

    # Using Supabase only
    from db.db import db_client
    
    db_client.update('products', {'stock': new_stock}, {'id': product['id']})

    msg = context.user_data["edit_product_with_crude_data"]["start_msg"]

    await msg.edit_text(t("stock_updated", lang).format(product.get('name'), new_stock))

    del context.user_data["edit_product_with_crude_data"]

    return ConversationHandler.END

async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["edit_product_with_crude_data"]["lang"]

    product = context.user_data["edit_product_with_crude_data"]["product"]

    # Using Supabase only
    from db.db import db_client
    
    db_client.delete('products', {'id': product['id']})

    msg = context.user_data["edit_product_with_crude_data"]["start_msg"]

    await msg.edit_text(t("product_deleted", lang).format(product.get('name')))
    del context.user_data["edit_product_with_crude_data"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    msg: Message = context.user_data["edit_product_with_crude_data"]["start_msg"]
    await msg.delete()
    del context.user_data["edit_product_with_crude_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg: Message = context.user_data["edit_product_with_crude_data"]["start_msg"]
    await msg.reply_text(t("timeout_error", get_user_lang(update.effective_user.id)))
    del context.user_data["edit_product_with_crude_data"]

    return ConversationHandler.END


states = {
    EditCrudeStockStates.CHOOSE_ACTION: [
        CallbackQueryHandler(edit_product_crude, '^edit_crude$'),
        CallbackQueryHandler(edit_product_stock, '^edit_stock$'),
        CallbackQueryHandler(delete_product, '^delete$'),
    ],
    EditCrudeStockStates.EDIT_CRUDE_END: [
        MessageHandler(filters.Regex(r'^\d+$'), edit_product_crude_end)
    ],
    EditCrudeStockStates.EDIT_STOCK_END: [
        MessageHandler(filters.Regex(r'^\d+$'), edit_product_stock_end)
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


EDIT_CRUDE_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_edit_crude_stock_product, '^edit_crude_*[0-9]$'),
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    conversation_timeout=120,
)