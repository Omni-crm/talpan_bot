from telegram.ext import CallbackQueryHandler, TypeHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram import Message as TgMessage
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
        print(f"🔍 NEW_ORDER: handle_update called")
        print(f"🔍 NEW_ORDER: Check result: {check_result}")
        
        result = await super().handle_update(update, application, check_result, context)
        
        print(f"🔍 NEW_ORDER: After handling, result: {result}")
        
        return result
    
    def check_update(self, update):
        """Override to add logging"""
        print(f"🔍 NEW_ORDER: check_update called")
        
        # Try to see current conversations
        try:
            conv_dict = getattr(self, '_conversations', {})
            print(f"🔍 NEW_ORDER: Active conversations: {list(conv_dict.keys())}")
        except Exception as e:
            print(f"🔍 NEW_ORDER: Could not access conversations: {e}")
        
        result = super().check_update(update)
        print(f"🔍 NEW_ORDER: Check result: {result}")
        return result

class CollectOrderDataStates:
    START = 0
    NAME = 1
    USERNAME = 2
    PHONE = 3
    ADDRESS = 4
    PRODUCT = 5
    QUANTITY = 6
    TOTAL_PRICE = 7
    CONFIRM_OR_NOT = 8

    NEW_PRODUCT_STOCK = 77
    SAVE_NEW_PRODUCT = 78

    ADD_MORE_PRODUCTS_OR_CONFIRM = 79

async def start_collect_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """START function of collecting data for new order."""
    print(f"🔧 start_collect_data called")
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    print(f"🔧 Language: {lang}")
    
    # ניקוי הודעה קודמת
    await clean_previous_message(update, context)

    # Using Supabase only
    from db.db import get_opened_shift
    shift = get_opened_shift()
    print(f"🔧 Shift found: {shift is not None}")

    if not shift:
        msg = await update.effective_message.reply_text(t("need_open_shift_for_order", lang))
        save_message_id(context, msg.message_id)
        print(f"🔧 No shift, returning END")
        return ConversationHandler.END

    start_msg = await send_message_with_cleanup(update, context, t("enter_client_name", lang), reply_markup=get_cancel_kb(lang))
    context.user_data["collect_order_data"] = {}
    context.user_data["collect_order_data"]["start_msg"] = start_msg
    context.user_data["collect_order_data"]["products"] = []
    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.START
    context.user_data["collect_order_data"]["lang"] = lang
    
    # שמירת ID לניקוי עתידי
    save_message_id(context, start_msg.message_id)

    print(f"🔧 Returning state: {CollectOrderDataStates.NAME}")
    return CollectOrderDataStates.NAME

async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting name and go to next step @username."""
    print(f"🔧 collect_name called")
    lang = context.user_data["collect_order_data"]["lang"]
    
    if update.callback_query:
        await update.callback_query.answer()
        # אם זה callback query, זה כנראה כפתור "חזור" או "ביטול"
        return CollectOrderDataStates.NAME
    else:
        try:
            await update.effective_message.delete()
            print(f"🔧 Deleted user message")
        except Exception as e:
            print(f"⚠️ Could not delete message: {e}")
            pass

        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.NAME
        name = update.message.text[:100]
        context.user_data["collect_order_data"]["name"] = name
        print(f"🔧 Name collected: {name}")

        # Edit the bot's message, not the user's message
        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        from funcs.utils import edit_conversation_message
        context.user_data["collect_order_data"]["start_msg"] = await edit_conversation_message(
            msg,
            t("enter_client_username", lang), 
            reply_markup=get_username_kb(lang)
        )
        print(f"🔧 Edited bot message to ask for username")

        return CollectOrderDataStates.USERNAME

async def collect_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting @username or skip."""
    try:
        print(f"🔧 collect_username called")
        lang = context.user_data["collect_order_data"]["lang"]
        print(f"🔧 Language: {lang}")
        
        if update.callback_query:
            print(f"🔧 Callback query detected")
            await update.callback_query.answer()
            
            if update.callback_query.data == "skip_username":
                print(f"🔧 Skip username clicked")
                # דילוג על username
                context.user_data["collect_order_data"]["username"] = ""
                context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.USERNAME
                
                msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
                context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("enter_client_phone", lang), reply_markup=get_back_cancel_kb(lang))
                print(f"🔧 Updated message to phone input")
                
                return CollectOrderDataStates.PHONE
        
        else:
            # User typed username
            try:
                await update.effective_message.delete()
            except:
                pass
            
            context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.USERNAME
            username = update.message.text[:36]
            context.user_data["collect_order_data"]["username"] = username

            msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
            context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("enter_client_phone", lang), reply_markup=get_back_cancel_kb(lang))
            print(f"🔧 Updated message to phone input (with username)")

            return CollectOrderDataStates.PHONE
    except Exception as e:
        print(f"❌ ERROR in collect_username: {e}")
        import traceback
        traceback.print_exc()
        return ConversationHandler.END

async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting phone."""
    lang = context.user_data["collect_order_data"]["lang"]
    
    if update.callback_query:
        await update.callback_query.answer()
        # אם זה callback query, זה כנראה כפתור "חזור" או "ביטול"
        return CollectOrderDataStates.PHONE
    else:
        # מחיקת הודעת המשתמש
        try:
            await update.effective_message.delete()
        except:
            pass

        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.PHONE
        phone = update.message.text[:36]
        context.user_data["collect_order_data"]["phone"] = phone

        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        from funcs.utils import edit_conversation_message
        context.user_data["collect_order_data"]["start_msg"] = await edit_conversation_message(
            msg,
            t("enter_address", lang), 
            reply_markup=get_back_cancel_kb(lang)
        )

        return CollectOrderDataStates.ADDRESS

async def collect_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting address."""
    lang = context.user_data["collect_order_data"]["lang"]
    
    if not update.callback_query:
        await update.effective_message.delete()

    if not update.callback_query:
        if update.effective_message.location:
            latitude = update.effective_message.location.latitude
            longitude = update.effective_message.location.longitude
            geolocator = Nominatim(user_agent="mygeo")
            location = geolocator.reverse((latitude, longitude), language='ru')

            if location:
                address = location.address
            else:
                address = f"{latitude}, {longitude}"
        else:
            address = update.message.text[:100]

        context.user_data["collect_order_data"]["address"] = address

    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.ADDRESS

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_product", lang), reply_markup=get_products_markup(update.effective_user))

    return CollectOrderDataStates.PRODUCT


async def new_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start of creation of new product."""
    lang = context.user_data["collect_order_data"]["lang"]
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("enter_new_product_name", lang), reply_markup=get_cancel_kb(lang))

    return CollectOrderDataStates.NEW_PRODUCT_STOCK


async def new_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saving new prouct name and continue to adding stock for new product."""
    lang = context.user_data["collect_order_data"]["lang"]
    
    if not update.callback_query:
        await update.effective_message.delete()

    context.user_data["collect_order_data"]["new_product_name"] = update.message.text[:22]

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("enter_new_product_stock", lang), reply_markup=get_cancel_kb(lang))

    return CollectOrderDataStates.SAVE_NEW_PRODUCT

async def save_new_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saving new product. Returining choosing a product for new order."""
    lang = context.user_data["collect_order_data"]["lang"]
    
    if not update.callback_query:
        await update.effective_message.delete()

    stock = int(update.message.text[:10])

    # Using Supabase only
    from db.db import db_client
    
    product_data = {
        'name': context.user_data["collect_order_data"]["new_product_name"],
        'stock': stock,
        'price': 0,
        'crude': 0
    }
    result = db_client.insert('products', product_data)
    print(f"Created product: {result}")

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_product", lang), reply_markup=get_products_markup(update.effective_user))

    return CollectOrderDataStates.PRODUCT

async def collect_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting product."""
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()
    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.PRODUCT

    if update.callback_query.data.isdigit():
        # Using Supabase only
        from db.db import get_product_by_id
        product = get_product_by_id(int(update.callback_query.data))

        if product:
            context.user_data["collect_order_data"]["product"] = product.get('name', '')
            context.user_data["collect_order_data"]["product_stock"] = product.get('stock', 0)

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_or_enter_quantity", lang), reply_markup=SELECT_QUANTITY_KB)

    return CollectOrderDataStates.QUANTITY

async def collect_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting quantity."""
    lang = context.user_data["collect_order_data"]["lang"]
    
    if not update.callback_query:
        await update.effective_message.delete()

    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.QUANTITY

    if not update.callback_query:
        quantity = int(update.message.text[:100])

        if context.user_data["collect_order_data"]["product_stock"] < int(quantity):
            msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
            await msg.edit_text(t("not_enough_stock", lang))

            return CollectOrderDataStates.QUANTITY

        context.user_data["collect_order_data"]["quantity"] = quantity
    else:
        await update.callback_query.answer()

        if update.callback_query.data.isdigit():
            quantity = int(update.callback_query.data)

            if context.user_data["collect_order_data"]["product_stock"] < int(quantity):
                msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
                await msg.edit_text(t("not_enough_stock", lang))

                return CollectOrderDataStates.QUANTITY

            context.user_data["collect_order_data"]["quantity"] = quantity


    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]

    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_or_enter_total_price", lang), reply_markup=SELECT_PRICE_KB)

    return CollectOrderDataStates.TOTAL_PRICE

async def collect_total_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting total_price."""
    lang = context.user_data["collect_order_data"]["lang"]
    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.TOTAL_PRICE

    if update.callback_query:
        await update.callback_query.answer()

        if update.callback_query.data.isdigit():
            total_price = int(update.callback_query.data[:11])
            context.user_data["collect_order_data"]["total_price"] = total_price

            context.user_data["collect_order_data"]["products"].append(
                {
                    "name": context.user_data["collect_order_data"]["product"],
                    "quantity": context.user_data["collect_order_data"]["quantity"],
                    "total_price": context.user_data["collect_order_data"]["total_price"],
                }
            )

            if len(context.user_data["collect_order_data"]["products"]) > 1:
                for product in context.user_data["collect_order_data"]["products"][:-1]:
                    if context.user_data["collect_order_data"]["products"][-1]['name'] == product['name']:
                        context.user_data["collect_order_data"]["products"].remove(product)
    else:
        await update.effective_message.delete()
        total_price = int(update.effective_message.text[:11])
        context.user_data["collect_order_data"]["total_price"] = total_price

        context.user_data["collect_order_data"]["products"].append(
            {
                "name": context.user_data["collect_order_data"]["product"],
                "quantity": context.user_data["collect_order_data"]["quantity"],
                "total_price": context.user_data["collect_order_data"]["total_price"],
            }
        )
        if len(context.user_data["collect_order_data"]["products"]) > 1:
            for product in context.user_data["collect_order_data"]["products"][:-1]:
                if context.user_data["collect_order_data"]["products"][-1]['name'] == product['name']:
                    context.user_data["collect_order_data"]["products"].remove(product)

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("add_more_or_confirm", lang), reply_markup=get_add_more_or_confirm_kb(lang), parse_mode=ParseMode.HTML)

    return CollectOrderDataStates.ADD_MORE_PRODUCTS_OR_CONFIRM

async def add_more_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()
    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.PRODUCT

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_product", lang), reply_markup=get_products_markup(update.effective_user))

    return CollectOrderDataStates.PRODUCT

async def go_to_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go to final confirming order."""
    print(f"🔧 go_to_confirm called")
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()

    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.ADD_MORE_PRODUCTS_OR_CONFIRM

    # Create an object-like structure for the order (not saved to DB yet)
    import json
    products_json = json.dumps(context.user_data["collect_order_data"]["products"])
    
    # Calculate total price
    total_price = sum([product['total_price'] for product in context.user_data["collect_order_data"]["products"]])
    
    # Create object-like dict
    order_data = {
        'id': None,  # Not saved yet
        'client_name': context.user_data["collect_order_data"]["name"],
        'client_username': context.user_data["collect_order_data"]["username"],
        'client_phone': context.user_data["collect_order_data"]["phone"],
        'address': context.user_data["collect_order_data"]["address"],
        'products': products_json,
        'total_order_price': total_price,
        'status': None  # Will be set when saved
    }
    
    # Convert to object-like for form_confirm_order
    class OrderPreview:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)
        
        def get_products(self):
            import json
            return json.loads(self.products) if isinstance(self.products, str) else self.products
    
    order = OrderPreview(order_data)
    print(f"🔧 Order preview created")

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    text = t("confirm_order_check", lang) + (await form_confirm_order(order, lang))
    from funcs.utils import edit_conversation_message
    context.user_data["collect_order_data"]["start_msg"] = await edit_conversation_message(
        msg,
        text, 
        reply_markup=get_confirm_order_kb(lang), 
        parse_mode=ParseMode.HTML
    )
    print(f"🔧 Confirmation message edited")

    return CollectOrderDataStates.CONFIRM_OR_NOT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    await msg.delete()
    del context.user_data["collect_order_data"]

    return ConversationHandler.END

async def step_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print(f"🔧 step_back called")
    await update.callback_query.answer()

    current_step = context.user_data["collect_order_data"]["step"]
    print(f"🔧 Current step: {current_step}")
    
    # If we're at the first step, end the conversation
    if current_step == CollectOrderDataStates.NAME:
        print(f"🔧 At first step, ending conversation")
        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        await msg.delete()
        del context.user_data["collect_order_data"]
        return ConversationHandler.END
    
    # Go back one step
    if current_step == CollectOrderDataStates.USERNAME:
        print(f"🔧 Going back to NAME")
        return await start_collect_data(update, context)
    elif current_step == CollectOrderDataStates.PHONE:
        print(f"🔧 Going back to USERNAME")
        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.NAME
        return await collect_name(update, context)
    elif current_step == CollectOrderDataStates.ADDRESS:
        print(f"🔧 Going back to PHONE")
        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.USERNAME
        return await collect_username(update, context)
    elif current_step == CollectOrderDataStates.PRODUCT:
        print(f"🔧 Going back to ADDRESS")
        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.PHONE
        return await collect_phone(update, context)
    elif current_step == CollectOrderDataStates.QUANTITY:
        print(f"🔧 Going back to PRODUCT")
        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.ADDRESS
        return await collect_address(update, context)
    elif current_step == CollectOrderDataStates.TOTAL_PRICE:
        print(f"🔧 Going back to QUANTITY")
        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.PRODUCT
        return await collect_product(update, context)
    elif current_step == CollectOrderDataStates.ADD_MORE_PRODUCTS_OR_CONFIRM:
        print(f"🔧 Going back to TOTAL_PRICE")
        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.QUANTITY
        return await collect_quantity(update, context)
    elif current_step == CollectOrderDataStates.CONFIRM_OR_NOT:
        print(f"🔧 Going back to ADD_MORE_PRODUCTS_OR_CONFIRM")
        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.TOTAL_PRICE
        return await collect_total_price(update, context)
    
    print(f"🔧 Unknown step: {current_step}, ending conversation")
    return ConversationHandler.END

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["collect_order_data"]["lang"]
    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.CONFIRM_OR_NOT

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]

    # Using Supabase only
    from db.db import db_client
    import json
    import datetime
    
    order_data = {
        'client_name': context.user_data["collect_order_data"]["name"],
        'client_username': context.user_data["collect_order_data"]["username"],
        'client_phone': context.user_data["collect_order_data"]["phone"],
        'address': context.user_data["collect_order_data"]["address"],
        'products': json.dumps(context.user_data["collect_order_data"]["products"]),
        'total_order_price': 0,
        'status': 'active',
        'created': datetime.datetime.now().isoformat()
    }
    
    result = db_client.insert('orders', order_data)
    context.user_data["collect_order_data"]["order_id"] = result.get('id')

    # Create object-like structure for compatibility
    class OrderObj:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)
    
    order_obj = OrderObj(result)
    new_text = await form_confirm_order(order_obj, lang)

    final_msg = await msg.edit_text(new_text, parse_mode=ParseMode.HTML)

    try:
        from db.db import get_bot_setting
        order_chat = get_bot_setting('order_chat') or links.ORDER_CHAT
        if order_chat:
            crourier_text = await form_confirm_order_courier(order, 'ru')  # לקבוצת קוריירים - ברוסית
            markup = await form_courier_action_kb(order.id, 'ru')  # לקבוצת קוריירים - ברוסית
            await context.bot.send_message(order_chat, crourier_text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception as e:
        traceback.print_exc()
        print(f'Failed to forward message about new order. Error: {e}')
    
    del context.user_data["collect_order_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    await msg.reply_text(t("timeout_error", get_user_lang(update.effective_user.id)))
    del context.user_data["collect_order_data"]

    return ConversationHandler.END


states = {
    CollectOrderDataStates.NAME: [
        MessageHandler(filters.Regex('^.+$'), collect_name)
    ],
    CollectOrderDataStates.USERNAME: [
        MessageHandler(filters.Regex('^@.+$'), collect_username)
    ],
    CollectOrderDataStates.PHONE: [
        MessageHandler(filters.Regex('^.+$'), collect_phone)
    ],
    CollectOrderDataStates.ADDRESS: [
        MessageHandler(filters.Regex('^.+$'), collect_address),
        MessageHandler(filters.LOCATION, collect_address),
    ],
    CollectOrderDataStates.PRODUCT: [
        CallbackQueryHandler(new_product_name, '^create$'),
        CallbackQueryHandler(collect_product, r'^\d+$'),
    ],
    CollectOrderDataStates.NEW_PRODUCT_STOCK: [
        # Extract new product name from message and ask for stock quantity.
        MessageHandler(filters.Regex('^.+$'), new_product_stock)
    ],
    CollectOrderDataStates.SAVE_NEW_PRODUCT: [
        # Incoming message - number of available stock quantity for new product, save product.
        MessageHandler(filters.Regex(r'^\d+$'), save_new_product)
    ],
    CollectOrderDataStates.QUANTITY: [
        CallbackQueryHandler(collect_quantity, r'^\d+$'),
        MessageHandler(filters.Regex(r'^\d+$'), collect_quantity)
    ],
    CollectOrderDataStates.TOTAL_PRICE: [
        MessageHandler(filters.Regex(r'^\d+$'), collect_total_price),
        CallbackQueryHandler(collect_total_price, r'^\d+$')
    ],
    CollectOrderDataStates.ADD_MORE_PRODUCTS_OR_CONFIRM: [
        CallbackQueryHandler(go_to_confirm, '^to_confirm$'),
        CallbackQueryHandler(add_more_products, '^add$'),
    ],
    CollectOrderDataStates.CONFIRM_OR_NOT: [
        CallbackQueryHandler(confirm_order, '^confirm$')
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


NEW_ORDER_HANDLER = DebugConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_collect_data, '^new$'),
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(step_back, '^back$'),
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    conversation_timeout=120
)