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

class DebugConversationHandler(ConversationHandler):
    """ConversationHandler with debug logging"""
    
    async def handle_update(self, update, application, check_result, context):
        """Override to add logging"""
        print(f"🔍 ConversationHandler.handle_update called")
        print(f"🔍 Update ID: {update.update_id}")
        print(f"🔍 Check result: {check_result}")
        
        # Try to get conversation key safely
        try:
            key = self._get_key(update)
            current_state = self.conversations.get(key, 'NO STATE')
            print(f"🔍 Conversation key: {key}")
            print(f"🔍 Current conversation state: {current_state}")
        except Exception as e:
            print(f"🔍 Could not get conversation key: {e}")
        
        result = await super().handle_update(update, application, check_result, context)
        
        # Try to get state after handling
        try:
            key = self._get_key(update)
            new_state = self.conversations.get(key, 'NO STATE')
            print(f"🔍 After handling, conversation state: {new_state}")
        except Exception as e:
            print(f"🔍 Could not get conversation state after handling: {e}")
        
        print(f"🔍 Result: {result}")
        
        return result
    
    def check_update(self, update):
        """Override to add logging"""
        print(f"🔍 ConversationHandler.check_update called")
        print(f"🔍 Update type: {type(update).__name__}")
        
        # Extract user and chat info
        user_id = None
        chat_id = None
        if hasattr(update, 'effective_user') and update.effective_user:
            user_id = update.effective_user.id
        if hasattr(update, 'effective_chat') and update.effective_chat:
            chat_id = update.effective_chat.id
        
        print(f"🔍 User ID: {user_id}, Chat ID: {chat_id}")
        
        if hasattr(update, 'message') and update.message:
            print(f"🔍 Message text: {update.message.text if update.message.text else 'NO TEXT'}")
            print(f"🔍 Message chat ID: {update.message.chat.id}")
            print(f"🔍 Message user ID: {update.message.from_user.id}")
        if hasattr(update, 'callback_query') and update.callback_query:
            print(f"🔍 Callback data: {update.callback_query.data}")
            print(f"🔍 Callback chat ID: {update.callback_query.message.chat.id}")
            print(f"🔍 Callback user ID: {update.callback_query.from_user.id}")
        
        # Try to see current conversations
        try:
            # Access the conversation dict through the parent class
            conv_dict = getattr(self, '_conversations', {})
            print(f"🔍 Active conversations: {list(conv_dict.keys())}")
        except Exception as e:
            print(f"🔍 Could not access conversations: {e}")
        
        result = super().check_update(update)
        print(f"🔍 Check result: {result}")
        return result

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
    print(f"🔧 User ID: {update.effective_user.id}")
    print(f"🔧 Chat ID: {update.effective_chat.id}")
    
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    print(f"🔧 Language: {lang}")
    
    context.user_data["add_product"] = {}
    context.user_data["add_product"]["msg"] = await update.effective_message.edit_text(
        t("enter_product_name", lang),
        reply_markup=get_cancel_kb(lang)
    )
    
    # Explicitly store state in user_data for debugging
    context.user_data["conversation_state"] = "ENTER_NAME"
    
    print(f"🔧 State set to ENTER_NAME: {StockManagementStates.ENTER_NAME}")
    print(f"🔧 Conversation will be active for state {StockManagementStates.ENTER_NAME}")
    print(f"🔧 Returning state: {StockManagementStates.ENTER_NAME}")
    
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
        
        # Check if we're coming from order creation
        if "creating_product_from_order" in context.user_data:
            print(f"🔧 Product created from order flow: {product_name}")
            # Import the return function from new_order_handler
            from handlers.new_order_handler import return_to_order_after_product_creation
            
            # Clean up add_product data
            if "add_product" in context.user_data:
                del context.user_data["add_product"]
            
            # Return to order flow
            return await return_to_order_after_product_creation(update, context)
        
        # Normal flow - show success message
        success_message = t("product_added_full", lang).format(product_name, stock, price)
        
        try:
            # Try to edit the existing message if it exists
            if "add_product" in context.user_data and "msg" in context.user_data["add_product"]:
                msg = context.user_data["add_product"]["msg"]
                await msg.edit_text(success_message, reply_markup=get_cancel_kb(lang))
            else:
                # If message not found, send a new one
                await update.effective_chat.send_message(success_message, reply_markup=get_cancel_kb(lang))
        except Exception as e:
            print(f"🔧 Error editing message: {e}")
            # If editing fails, send a new message
            await update.effective_chat.send_message(success_message, reply_markup=get_cancel_kb(lang))
        
        # Clean up regardless of whether editing succeeded
        if "add_product" in context.user_data:
            del context.user_data["add_product"]
        
        return ConversationHandler.END
        
    except ValueError:
        await update.effective_message.reply_text(t("invalid_price", lang))
        return StockManagementStates.ENTER_PRICE

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all products"""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    # לא צריך clean_previous_message כי אנחנו עושים edit_text על ההודעה הקיימת

    from db.db import get_all_products
    products = get_all_products()

    if not products:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back")]
        ])
        await update.effective_message.edit_text(
            t("no_products", lang),
            reply_markup=keyboard
        )
        return

    # שינוי: שימוש בתרגום הקיים
    products_text = "\n".join([
        f"{i+1}. {p.get('name', '')} - {p.get('stock', 0)} {t('units', lang)}"
        for i, p in enumerate(products)
    ])

    # שינוי: רק כפתור חזור (לא ביטול + back + home)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_back", lang), callback_data="back")]
    ])

    await update.effective_message.edit_text(
        f"{t('all_products', lang)}:\n\n{products_text}",
        parse_mode="HTML",
        reply_markup=keyboard
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

    # הוספה: שמירת מידע על מוצר לעריכה
    context.user_data['editing_product_id'] = product_id
    context.user_data['came_from_inventory'] = True  # דגל חשוב

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

async def cancel_stock_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel stock management"""
    if update.callback_query:
        await update.callback_query.answer()
    
    if "add_product" in context.user_data:
        msg = context.user_data["add_product"]["msg"]
        await msg.delete()
        del context.user_data["add_product"]
    
    if "delete_product" in context.user_data:
        del context.user_data["delete_product"]
    
    # Check if we're coming from order creation
    if "creating_product_from_order" in context.user_data:
        print(f"🔧 Returning to order creation after product creation")
        # Import the return function from new_order_handler
        from handlers.new_order_handler import return_to_order_after_product_creation
        # Don't delete the message, we'll need it for the order flow
        return await return_to_order_after_product_creation(update, context)
    
    # Normal flow - delete the message and end
    await update.effective_message.delete()
    
    return ConversationHandler.END

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

MANAGE_STOCK_HANDLER = DebugConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_product_start, '^add_product$'),
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel_stock_management, '^cancel$'),
        CallbackQueryHandler(cancel_stock_management, '^back$'),  # Handle back button - cancel the conversation
        CallbackQueryHandler(cancel_stock_management, '^home$'),  # Handle home button - cancel the conversation
        CallbackQueryHandler(list_products, '^list_products$'),
        MessageHandler(filters.ALL, debug_message_handler),  # Debug handler to catch all unmatched messages
    ],
    conversation_timeout=120,
    per_chat=True,
    per_user=True,
    name="manage_stock_conversation"  # Add name for debugging
)

