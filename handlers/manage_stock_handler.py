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

class StockManagementStates:
    ENTER_NAME = 0
    ENTER_STOCK = 1

@is_admin
async def manage_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show stock management menu"""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    from config.kb import get_stock_management_kb
    
    reply_markup = get_stock_management_kb(lang)
    await update.effective_message.edit_text(
        t("stock_management_menu", lang),
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

@is_admin
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start adding a new product"""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    context.user_data["add_product"] = {}
    context.user_data["add_product"]["msg"] = await update.effective_message.edit_text(
        t("enter_product_name", lang),
        reply_markup=get_cancel_kb(lang)
    )
    
    return StockManagementStates.ENTER_NAME

async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process product name"""
    lang = get_user_lang(update.effective_user.id)
    
    product_name = update.message.text[:50]  # Limit to 50 characters
    await update.effective_message.delete()
    
    context.user_data["add_product"]["name"] = product_name
    
    msg = context.user_data["add_product"]["msg"]
    await msg.edit_text(
        t("enter_product_stock", lang).format(product_name),
        reply_markup=get_cancel_kb(lang)
    )
    
    return StockManagementStates.ENTER_STOCK

async def add_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process product stock and save"""
    lang = get_user_lang(update.effective_user.id)
    
    try:
        stock = int(update.message.text[:10])
        await update.effective_message.delete()
        
        product_name = context.user_data["add_product"]["name"]
        
        # Using Supabase only
        from db.db import db_client
        
        product_data = {
            'name': product_name,
            'stock': stock,
            'price': 0,
            'crude': 0
        }
        result = db_client.insert('products', product_data)
        
        msg = context.user_data["add_product"]["msg"]
        await msg.edit_text(
            t("product_added", lang).format(product_name, stock),
            reply_markup=get_cancel_kb(lang)
        )
        
        del context.user_data["add_product"]
        
        return ConversationHandler.END
        
    except ValueError:
        await update.effective_message.reply_text(t("invalid_stock", lang))
        return StockManagementStates.ENTER_STOCK

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all products"""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    from db.db import get_all_products
    products = get_all_products()
    
    if not products:
        await update.effective_message.edit_text(
            t("no_products", lang),
            reply_markup=get_cancel_kb(lang)
        )
        return
    
    products_text = "\n".join([
        f"{i+1}. {p.get('name', '')} - {p.get('stock', 0)} шт."
        for i, p in enumerate(products)
    ])
    
    await update.effective_message.edit_text(
        f"{t('all_products', lang)}:\n\n{products_text}",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(lang)
    )

async def cancel_stock_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel stock management"""
    await update.callback_query.answer()
    
    if "add_product" in context.user_data:
        msg = context.user_data["add_product"]["msg"]
        await msg.delete()
        del context.user_data["add_product"]
    
    await update.effective_message.delete()

states = {
    StockManagementStates.ENTER_NAME: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)
    ],
    StockManagementStates.ENTER_STOCK: [
        MessageHandler(filters.Regex(r'^\d+$'), add_product_stock),
        MessageHandler(~filters.Regex(r'^\d+$'), add_product_stock),
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, cancel_stock_management)]
}

MANAGE_STOCK_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_product_start, '^add_product$'),
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel_stock_management, '^cancel$'),
    ],
    conversation_timeout=120,
)

