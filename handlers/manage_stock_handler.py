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
    ENTER_PRICE = 2
    EDIT_NAME = 3
    EDIT_STOCK = 4
    EDIT_PRICE_FIELD = 5

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
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start adding a new product"""
    print(f"🔧 add_product_start called")
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    print(f"🔧 Language: {lang}")
    
    context.user_data["add_product"] = {}
    context.user_data["add_product"]["msg"] = await update.effective_message.edit_text(
        t("enter_product_name", lang),
        reply_markup=get_cancel_kb(lang)
    )
    print(f"🔧 State set to ENTER_NAME: {StockManagementStates.ENTER_NAME}")
    print(f"🔧 Conversation will be active for state {StockManagementStates.ENTER_NAME}")
    
    return StockManagementStates.ENTER_NAME

async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process product name"""
    print(f"🔧🔧🔧 add_product_name CALLED! 🔧🔧🔧")
    print(f"🔧 Update type: {type(update)}")
    print(f"🔧 Update: {update}")
    print(f"🔧 Context user_data: {context.user_data}")
    
    if update.message:
        product_name = update.message.text[:50]  # Limit to 50 characters
        print(f"🔧 Product name: {product_name}")
        
        lang = get_user_lang(update.effective_user.id)
        print(f"🔧 Language: {lang}")
        
        await update.effective_message.delete()
        print(f"🔧 Message deleted")
        
        if "add_product" not in context.user_data:
            print(f"⚠️ add_product not in context.user_data! Initializing...")
            context.user_data["add_product"] = {}
        
        context.user_data["add_product"]["name"] = product_name
        
        msg = context.user_data.get("add_product", {}).get("msg")
        if msg:
            await msg.edit_text(
                t("enter_product_stock", lang).format(product_name),
                reply_markup=get_cancel_kb(lang)
            )
            print(f"🔧 Asking for stock, returning to state {StockManagementStates.ENTER_STOCK}")
            return StockManagementStates.ENTER_STOCK
        else:
            print(f"❌ ERROR: msg not found in context.user_data!")
    else:
        print(f"❌ ERROR: update.message is None!")
    
    print(f"🔧 Something went wrong - returning END")
    return ConversationHandler.END

async def add_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process product stock and ask for price"""
    lang = get_user_lang(update.effective_user.id)
    
    try:
        stock = int(update.message.text[:10])
        await update.effective_message.delete()
        
        context.user_data["add_product"]["stock"] = stock
        
        msg = context.user_data["add_product"]["msg"]
        await msg.edit_text(
            t("enter_product_price", lang),
            reply_markup=get_cancel_kb(lang)
        )
        
        return StockManagementStates.ENTER_PRICE
        
    except ValueError:
        await update.effective_message.reply_text(t("invalid_stock", lang))
        return StockManagementStates.ENTER_STOCK

async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process product price and save"""
    lang = get_user_lang(update.effective_user.id)
    
    try:
        price = int(update.message.text[:10])
        await update.effective_message.delete()
        
        product_name = context.user_data["add_product"]["name"]
        stock = context.user_data["add_product"]["stock"]
        
        # Using Supabase only
        from db.db import db_client
        
        product_data = {
            'name': product_name,
            'stock': stock,
            'price': price,
            'crude': 0
        }
        result = db_client.insert('products', product_data)
        
        msg = context.user_data["add_product"]["msg"]
        await msg.edit_text(
            t("product_added_full", lang).format(product_name, stock, price),
            reply_markup=get_cancel_kb(lang)
        )
        
        del context.user_data["add_product"]
        
        return ConversationHandler.END
        
    except ValueError:
        await update.effective_message.reply_text(t("invalid_price", lang))
        return StockManagementStates.ENTER_PRICE

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

@is_admin
async def edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start editing a product"""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    product_id = int(update.callback_query.data.replace('edit_', ''))
    
    from db.db import get_product_by_id
    product = get_product_by_id(product_id)
    
    if not product:
        await update.effective_message.reply_text(t("product_not_found", lang))
        return
    
    from config.kb import get_edit_product_actions_kb
    reply_markup = get_edit_product_actions_kb(lang, product_id)
    
    await update.effective_message.edit_text(
        t("edit_product_menu", lang).format(product.get('name'), product.get('stock'), product.get('price', 0)),
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

@is_admin
async def delete_product_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm product deletion"""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    product_id = int(update.callback_query.data.replace('delete_product_', ''))
    
    from db.db import get_product_by_id
    product = get_product_by_id(product_id)
    
    if not product:
        await update.effective_message.reply_text(t("product_not_found", lang))
        return
    
    # Store product ID for confirmation
    context.user_data["delete_product"] = product_id
    
    from config.kb import get_confirm_delete_kb
    reply_markup = get_confirm_delete_kb(lang, product_id)
    
    await update.effective_message.edit_text(
        t("confirm_delete_product", lang).format(product.get('name')),
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

@is_admin
async def delete_product_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute product deletion"""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    product_id = context.user_data.get("delete_product")
    
    if not product_id:
        await update.effective_message.edit_text(t("error", lang))
        return
    
    from db.db import db_client, get_product_by_id
    product = get_product_by_id(product_id)
    
    if product:
        db_client.delete('products', {'id': product_id})
        await update.effective_message.edit_text(
            t("product_deleted", lang).format(product.get('name')),
            parse_mode="HTML"
        )
    else:
        await update.effective_message.edit_text(t("product_not_found", lang))
    
    if "delete_product" in context.user_data:
        del context.user_data["delete_product"]

async def debug_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Debug handler to see what messages are received"""
    print(f"🚨🚨🚨 DEBUG_MESSAGE_HANDLER CALLED! 🚨🚨🚨")
    print(f"🔧 Update type: {type(update)}")
    print(f"🔧 Update: {update}")
    print(f"🔧 Context user_data: {context.user_data}")
    if update.message:
        print(f"🔧 Message text: {update.message.text}")
    if update.callback_query:
        print(f"🔧 Callback data: {update.callback_query.data}")
    current_state = context.user_data.get('stock_management_state')
    print(f"🔧 Current state: {current_state}")
    print(f"🚨 This means the message reached the fallback, not the state handler!")
    return ConversationHandler.END

async def cancel_stock_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel stock management"""
    if update.callback_query:
        await update.callback_query.answer()
    
    if "add_product" in context.user_data:
        msg = context.user_data["add_product"]["msg"]
        await msg.delete()
        del context.user_data["add_product"]
    
    if "delete_product" in context.user_data:
        del context.user_data["delete_product"]
    
    await update.effective_message.delete()

states = {
    StockManagementStates.ENTER_NAME: [
        MessageHandler(filters.ALL, add_product_name)
    ],
    StockManagementStates.ENTER_STOCK: [
        MessageHandler(filters.Regex(r'^\d+$'), add_product_stock),
        MessageHandler(~filters.Regex(r'^\d+$'), add_product_stock),
    ],
    StockManagementStates.ENTER_PRICE: [
        MessageHandler(filters.Regex(r'^\d+$'), add_product_price),
        MessageHandler(~filters.Regex(r'^\d+$'), add_product_price),
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
        CallbackQueryHandler(list_products, '^list_products$'),
        MessageHandler(filters.ALL, debug_message_handler),  # Debug handler to catch all unmatched messages
    ],
    conversation_timeout=120,
    per_chat=True,
    per_user=True
)

