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
    EDIT_NAME_END = 2
    EDIT_PRICE_END = 3

async def start_edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """START function of collecting data for new order."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # Extract product_id from callback_data (format: edit_stock_5, edit_name_5, etc.)
    callback_data = update.callback_query.data
    product_id = int(callback_data.split('_')[-1])  # Get last part after last underscore

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

async def edit_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start editing product name"""
    await update.callback_query.answer()
    lang = context.user_data["edit_product_data"]["lang"]

    msg = context.user_data["edit_product_data"]["start_msg"]
    product = context.user_data["edit_product_data"]["product"]

    await msg.edit_text(t("enter_new_name", lang).format(product.get('name')))

    return EditProductStates.EDIT_NAME_END

async def edit_product_name_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save new product name"""
    lang = context.user_data["edit_product_data"]["lang"]
    new_name = update.effective_message.text[:50]
    await update.effective_message.delete()

    product = context.user_data["edit_product_data"]["product"]

    # Using Supabase only
    from db.db import db_client
    
    db_client.update('products', {'name': new_name}, {'id': product['id']})

    msg = context.user_data["edit_product_data"]["start_msg"]

    await msg.edit_text(t("name_updated", lang).format(new_name))

    del context.user_data["edit_product_data"]

    return ConversationHandler.END

async def edit_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start editing product price"""
    await update.callback_query.answer()
    lang = context.user_data["edit_product_data"]["lang"]

    msg = context.user_data["edit_product_data"]["start_msg"]
    product = context.user_data["edit_product_data"]["product"]

    await msg.edit_text(t("enter_new_price", lang).format(product.get('name'), product.get('price', 0)))

    return EditProductStates.EDIT_PRICE_END

async def edit_product_price_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save new product price"""
    lang = context.user_data["edit_product_data"]["lang"]
    
    try:
        new_price = int(update.effective_message.text[:10])
        await update.effective_message.delete()

        product = context.user_data["edit_product_data"]["product"]

        # Using Supabase only
        from db.db import db_client
        
        db_client.update('products', {'price': new_price}, {'id': product['id']})

        msg = context.user_data["edit_product_data"]["start_msg"]

        await msg.edit_text(t("price_updated", lang).format(product.get('name'), new_price))

        del context.user_data["edit_product_data"]

        return ConversationHandler.END
    except ValueError:
        await update.effective_message.reply_text(t("invalid_price", lang))
        return EditProductStates.EDIT_PRICE_END

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
        CallbackQueryHandler(edit_product_name, '^edit_name$'),
        CallbackQueryHandler(edit_product_price, '^edit_price$'),
        CallbackQueryHandler(delete_product, '^delete$'),
    ],
    EditProductStates.EDIT_STOCK_END: [
        MessageHandler(filters.Regex(r'^\d+$'), edit_product_stock_end)
    ],
    EditProductStates.EDIT_NAME_END: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_name_end)
    ],
    EditProductStates.EDIT_PRICE_END: [
        MessageHandler(filters.Regex(r'^\d+$'), edit_product_price_end)
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


EDIT_PRODUCT_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_edit_product, '^edit_(stock|name|price|delete_product)_[0-9]+$'),
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
        CallbackQueryHandler(cancel, '^back$'),  # Terminate conversation on back
        CallbackQueryHandler(cancel, '^home$'),  # Terminate conversation on home
    ],
    conversation_timeout=120,
)