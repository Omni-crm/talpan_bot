from telegram.ext import CallbackQueryHandler, TypeHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram import Message, InlineKeyboardMarkup, InlineKeyboardButton
from telegram import Update
from sqlalchemy import or_
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

async def start_edit_crude_stock_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """START function of collecting data for new order."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    product_id = int(update.callback_query.data.split('_')[2])

    session = Session()

    stockman = session.query(User).filter(
        User.user_id == update.effective_user.id,
        or_(User.role == Role.STOCKMAN, User.role == Role.ADMIN)
    ).first()
    if not stockman:
        await update.effective_message.reply_text(t('need_stockman_role', lang))
        session.close()
        return ConversationHandler.END

    product = session.query(Product).filter(Product.id==product_id).first()
    session.close()

    start_msg = await update.effective_message.edit_text(t("product_crude_info", lang).format(product.name, product.crude, product.stock), reply_markup=get_edit_product_crude_kb(lang), parse_mode=ParseMode.HTML)
    context.user_data["edit_product_with_crude_data"] = {}
    context.user_data["edit_product_with_crude_data"]["start_msg"] = start_msg
    context.user_data["edit_product_with_crude_data"]["product"] = product
    context.user_data["edit_product_with_crude_data"]["lang"] = lang

    return EditCrudeStockStates.CHOOSE_ACTION


async def edit_product_crude(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["edit_product_with_crude_data"]["lang"]

    msg = context.user_data["edit_product_with_crude_data"]["start_msg"]
    product: Product = context.user_data["edit_product_with_crude_data"]["product"]

    await msg.edit_text(t("enter_new_crude", lang).format(product.name))

    return EditCrudeStockStates.EDIT_CRUDE_END

async def edit_product_crude_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["edit_product_with_crude_data"]["lang"]
    new_stock = int(update.effective_message.text[:20])
    await update.effective_message.delete()

    product: Product = context.user_data["edit_product_with_crude_data"]["product"]

    session = Session()
    product = session.query(Product).filter(Product.id==product.id).first()

    product.crude = new_stock
    session.commit()


    msg: Message = context.user_data["edit_product_with_crude_data"]["start_msg"]

    await msg.edit_text(t("crude_updated", lang).format(product.name, product.crude), reply_markup=get_products_markup_left_edit_stock_crude())
    session.close()

    del context.user_data["edit_product_with_crude_data"]

    return ConversationHandler.END


async def edit_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["edit_product_with_crude_data"]["lang"]

    msg = context.user_data["edit_product_with_crude_data"]["start_msg"]
    product: Product = context.user_data["edit_product_with_crude_data"]["product"]

    await msg.edit_text(t("enter_new_stock", lang).format(product.name))

    return EditCrudeStockStates.EDIT_STOCK_END

async def edit_product_stock_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["edit_product_with_crude_data"]["lang"]
    new_stock = int(update.effective_message.text[:20])
    await update.effective_message.delete()

    product: Product = context.user_data["edit_product_with_crude_data"]["product"]

    session = Session()
    product = session.query(Product).filter(Product.id==product.id).first()

    product.stock = new_stock
    session.commit()


    msg = context.user_data["edit_product_with_crude_data"]["start_msg"]

    await msg.edit_text(t("stock_updated", lang).format(product.name, product.stock))
    session.close()

    del context.user_data["edit_product_with_crude_data"]

    return ConversationHandler.END

async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["edit_product_with_crude_data"]["lang"]

    product: Product = context.user_data["edit_product_with_crude_data"]["product"]

    session = Session()

    session.delete(product)
    session.flush()
    session.commit()

    session.close()

    msg = context.user_data["edit_product_with_crude_data"]["start_msg"]

    await msg.edit_text(t("product_deleted", lang).format(product.name))
    del context.user_data["edit_product_with_crude_data"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    msg: Message = context.user_data["edit_product_with_crude_data"]["start_msg"]
    await msg.delete()
    del context.user_data["edit_product_with_crude_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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