from telegram.ext import CallbackQueryHandler, TypeHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram import Message as TgMessage
from telegram import Update
from geopy.geocoders import Nominatim
from db.db import *
from config.config import *
from config.translations import t, get_user_lang
from config.kb import get_skip_back_cancel_kb
from funcs.utils import *
from funcs.bot_funcs import *
import asyncio
import datetime
import logging

def push_navigation_state(context, state_type, state_data):
    """דוחף מצב חדש למחסנית הניווט"""
    import logging
    logger = logging.getLogger(__name__)

    if "collect_order_data" not in context.user_data:
        logger.warning("🔄 push_navigation_state: no collect_order_data")
        return

    if "navigation_stack" not in context.user_data["collect_order_data"]:
        context.user_data["collect_order_data"]["navigation_stack"] = []

    stack = context.user_data["collect_order_data"]["navigation_stack"]

    # דחוף את המצב הנוכחי
    new_state = {
        "type": state_type,
        "timestamp": datetime.datetime.now(),
        **state_data
    }
    stack.append(new_state)

    # הגבל לגודל מקסימלי
    if len(stack) > 20:  # יותר מ-20 שלבים אחורה
        stack.pop(0)

    logger.info(f"🔄 Pushed to navigation stack: {state_type} - {state_data}")

def add_order_step_to_history(context, step, action):
    """הוספת שלב ל-navigation history של הזמנה - DEPRECATED: השתמש ב-push_navigation_state"""
    push_navigation_state(context, "order", {"state": step, "action": action})

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
        
        # Safely try to access conversation state
        try:
            # For python-telegram-bot v20+, use self._conversation_key(update)
            # This is more reliable than trying to access internal attributes
            conv_key = self._conversation_key(update) if hasattr(self, '_conversation_key') else None
            if conv_key:
                print(f"🔍 NEW_ORDER: Conversation key: {conv_key}")
        except Exception as e:
            print(f"🔍 NEW_ORDER: Could not get conversation key: {e}")
        
        result = super().check_update(update)
        print(f"🔍 NEW_ORDER: Check result: {result}")
        return result

class CollectOrderDataStates:
    START = 0
    NAME = 1
    USERNAME = 2
    PHONE = 3
    ADDRESS = 4
    PRODUCT_LIST = 5   # רשימת מוצרים + אפשרות הוספה/עריכה
    CONFIRMATION = 6   # אישור סופי של ההזמנה

    # מצבים ישנים לתאימות
    PRODUCT = 5  # זהה ל-PRODUCT_LIST
    QUANTITY = 6
    TOTAL_PRICE = 7
    CONFIRM_OR_NOT = 8
    ADD_MORE_PRODUCTS_OR_CONFIRM = 79

class ProductStates:
    SELECT_PRODUCT = 10    # בחירת מוצר מהרשימה
    ENTER_QUANTITY = 11    # הזנת כמות
    ENTER_PRICE = 12       # הזנת מחיר ליחידה
    CONFIRM_PRODUCT = 13   # אישור המוצר להזמנה

class EditStates:
    SELECT_EDIT_ACTION = 20   # בחירת מה לערוך (כמות/מחיר/מחיקה)
    EDIT_QUANTITY = 21        # עריכת כמות
    EDIT_PRICE = 22           # עריכת מחיר
    CONFIRM_EDIT = 23         # אישור השינויים

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

    # אתחול מבנה הנתונים לפי התכנית
    context.user_data["collect_order_data"] = {
        # נתוני לקוח בסיסיים
        "customer": {
            "name": None,
            "username": None,
            "phone": None,
            "address": None
        },

        # רשימת מוצרים
        "products": [],

        # מצב נוכחי של ההזמנה
        "current_state": CollectOrderDataStates.NAME,

        # מוצר שנמצא כרגע בעריכה/הוספה (אם קיים)
        "active_product": None,

        # היסטוריית ניווט
        "navigation_stack": [],

        # נתונים ישנים לתאימות (זמני)
        "start_msg": start_msg,
        "step": CollectOrderDataStates.START,
        "lang": lang
    }

    # הוספת השלב הראשון ל-navigation stack
    push_navigation_state(context, "order", {
        "state": CollectOrderDataStates.NAME,
        "action": "enter_client_name"
    })
    
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

        # שמור את השם במבנה החדש
        context.user_data["collect_order_data"]["customer"]["name"] = update.message.text[:100]
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.USERNAME

        # הוסף ל-navigation stack
        push_navigation_state(context, "order", {
            "state": CollectOrderDataStates.USERNAME,
            "action": f'enter_client_username (name: {update.message.text[:100]})'
        })

        logger.info(f"📝 Customer name collected: {update.message.text[:100]}")

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
    """Collecting @username or skip (empty string)."""
    try:
        print(f"🔧 collect_username called")
        lang = context.user_data["collect_order_data"]["lang"]
        
        # Check if this is skip button or text message
        if update.callback_query:
            # Skip button clicked
            await update.callback_query.answer()
            username = ""
            print(f"🔧 Username skipped via button")
        else:
            # Username typed
            try:
                await update.effective_message.delete()
            except:
                pass
            username = update.message.text[:36]
            print(f"🔧 Username collected: {username}")
        
        # שמור את ה-username במבנה החדש
        context.user_data["collect_order_data"]["customer"]["username"] = username
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.PHONE

        # הוסף ל-navigation stack
        push_navigation_state(context, "order", {
            "state": CollectOrderDataStates.PHONE,
            "action": f'enter_client_phone (username: {username})'
        })

        logger.info(f"📝 Customer username collected: {username}")

        # Update message to ask for phone
        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            t("enter_client_phone", lang),
            reply_markup=get_back_cancel_kb(lang)
        )
        
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

        # שמור את הטלפון במבנה החדש
        phone = update.message.text[:36]
        context.user_data["collect_order_data"]["customer"]["phone"] = phone
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.ADDRESS

        # הוסף ל-navigation stack
        push_navigation_state(context, "order", {
            "state": CollectOrderDataStates.ADDRESS,
            "action": f'enter_client_address (phone: {phone})'
        })

        logger.info(f"📝 Customer phone collected: {phone}")

        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        from funcs.utils import edit_conversation_message
        context.user_data["collect_order_data"]["start_msg"] = await edit_conversation_message(
            msg,
            t("enter_client_address", lang),
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

        # שמור את הכתובת במבנה החדש
        context.user_data["collect_order_data"]["customer"]["address"] = address
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.PRODUCT_LIST

        # הוסף ל-navigation stack
        push_navigation_state(context, "order", {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": f'choose_product (address: {address})'
        })

        logger.info(f"📝 Customer address collected: {address}")

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_product", lang), reply_markup=get_products_markup(update.effective_user))

    return CollectOrderDataStates.PRODUCT_LIST


async def new_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Redirect to the full product creation flow in manage_stock_handler.py."""
    lang = context.user_data["collect_order_data"]["lang"]
    
    # Save current order state to return to later
    if "order_state_before_product_creation" not in context.user_data:
        context.user_data["order_state_before_product_creation"] = {
            "collect_order_data": context.user_data["collect_order_data"].copy(),
            "return_to_state": CollectOrderDataStates.PRODUCT
        }
        print(f"🔧 Saved order state before product creation")
    
    # We need to modify context to include a flag that we're coming from order creation
    context.user_data["creating_product_from_order"] = True
    
    # End this conversation temporarily
    await update.callback_query.answer("מעביר ליצירת מוצר חדש...")
    
    # Create a button that will trigger the MANAGE_STOCK_HANDLER
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [InlineKeyboardButton("➕ הוסף מוצר", callback_data="add_product")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Update the message to show the add_product button
    msg = context.user_data["collect_order_data"]["start_msg"]
    await msg.edit_text(
        "לחץ על הכפתור להוספת מוצר חדש:",
        reply_markup=reply_markup
    )
    
    # End this conversation so the other one can take over
    return ConversationHandler.END


async def return_to_order_after_product_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to order creation after product creation is complete.
    
    This function:
    1. Restores the saved order state
    2. Sets the pending_order_with_data flag
    3. Shows the product selection menu
    4. Ends the MANAGE_STOCK conversation
    
    The next product selection will trigger resume_order_with_product entry point.
    """
    print(f"🔧 return_to_order_after_product_creation called")
    
    # Check if we have saved order state
    if "order_state_before_product_creation" not in context.user_data:
        print(f"🔧 No saved order state found - returning END")
        return ConversationHandler.END
    
    # Restore the order state
    saved_state = context.user_data["order_state_before_product_creation"]
    context.user_data["collect_order_data"] = saved_state["collect_order_data"]
    
    # Clean up
    del context.user_data["order_state_before_product_creation"]
    if "creating_product_from_order" in context.user_data:
        del context.user_data["creating_product_from_order"]
    
    # Get the language
    lang = context.user_data["collect_order_data"]["lang"]
    
    print(f"🔧 Product created successfully, now showing product selection")
    print(f"🔧 Restored order data: name={context.user_data['collect_order_data'].get('name')}, phone={context.user_data['collect_order_data'].get('phone')}")
    
    # CRITICAL: Set a flag to indicate we have a pending order
    # This flag will be checked by resume_order_with_product
    context.user_data["pending_order_with_data"] = True
    print(f"🔧 Set pending_order_with_data flag")
    
    try:
        # Try to get the original message from saved state
        original_msg = context.user_data["collect_order_data"].get("start_msg")
        
        if original_msg:
            # Try to edit the original message to show product selection
            try:
                msg = await original_msg.edit_text(
                    t("choose_product", lang), 
                    reply_markup=get_products_markup(update.effective_user)
                )
                # Update the message reference
                context.user_data["collect_order_data"]["start_msg"] = msg
                print(f"🔧 Successfully edited original message")
            except Exception as e:
                print(f"🔧 Error editing original message: {e}")
                # If editing fails, send a new message
                msg = await update.effective_chat.send_message(
                    t("choose_product", lang),
                    reply_markup=get_products_markup(update.effective_user)
                )
                context.user_data["collect_order_data"]["start_msg"] = msg
                print(f"🔧 Sent new message instead")
        else:
            # If no original message, send a new one
            msg = await update.effective_chat.send_message(
                t("choose_product", lang),
                reply_markup=get_products_markup(update.effective_user)
            )
            context.user_data["collect_order_data"]["start_msg"] = msg
            print(f"🔧 No original message, sent new one")
    except Exception as e:
        print(f"🔧 Error in return_to_order_after_product_creation: {e}")
        import traceback
        traceback.print_exc()
        # Last resort - send a completely new message
        try:
            msg = await update.effective_chat.send_message(
                t("choose_product", lang),
                reply_markup=get_products_markup(update.effective_user)
            )
            context.user_data["collect_order_data"]["start_msg"] = msg
            print(f"🔧 Last resort: sent new message")
        except Exception as e2:
            print(f"🔧 Critical error returning to order: {e2}")
            traceback.print_exc()
    
    print(f"🔧 Ending MANAGE_STOCK conversation - next product selection will resume NEW_ORDER")
    
    # End this conversation, but the entry point will catch the next product selection
    return ConversationHandler.END


async def resume_order_with_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resume order creation when a product is selected after product creation.
    
    Returns:
        int: The next conversation state if resuming
        None: If this update should not be handled by this entry point
    """
    print(f"🔧 resume_order_with_product called")
    print(f"🔧 User data keys: {list(context.user_data.keys())}")
    
    # CRITICAL: Only handle this if we have a pending order
    # This prevents conflicts with other handlers
    if "pending_order_with_data" not in context.user_data:
        print(f"🔧 No pending order found, NOT handling this update")
        # Return None to signal that this entry point should not handle this update
        # This allows other handlers or entry points to process it
        return None
    
    # We have a pending order - proceed with resumption
    if "collect_order_data" in context.user_data:
        print(f"🔧 Resuming order with existing data: {context.user_data['collect_order_data'].get('name')}")
        
        # Remove the pending flag
        del context.user_data["pending_order_with_data"]
        
        # Set the step to PRODUCT
        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.PRODUCT
        
        # Call collect_product to handle the product selection
        return await collect_product(update, context)
    else:
        # We have a pending flag but no order data - this is an error state
        print(f"🔧 ERROR: pending_order_with_data set but no collect_order_data found!")
        if "pending_order_with_data" in context.user_data:
            del context.user_data["pending_order_with_data"]
        return None


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
    from config.kb import get_select_quantity_kb
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_or_enter_quantity", lang), reply_markup=get_select_quantity_kb(lang))

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
            # הצג הודעת שגיאה עם כפתורים לחזרה או ביטול
            from config.kb import get_back_cancel_kb
            await msg.edit_text(
                t("not_enough_stock", lang) + "\n" + 
                t("available_stock", lang).format(context.user_data["collect_order_data"]["product_stock"]),
                reply_markup=get_back_cancel_kb(lang)
            )
            # נשאר באותו state כדי שהמשתמש יוכל לנסות שוב
            return CollectOrderDataStates.QUANTITY

        context.user_data["collect_order_data"]["quantity"] = quantity
    else:
        await update.callback_query.answer()

        if update.callback_query.data.isdigit():
            quantity = int(update.callback_query.data)

            if context.user_data["collect_order_data"]["product_stock"] < int(quantity):
                msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
                # הצג הודעת שגיאה עם כפתורים לחזרה או ביטול
                from config.kb import get_back_cancel_kb
                await msg.edit_text(
                    t("not_enough_stock", lang) + "\n" + 
                    t("available_stock", lang).format(context.user_data["collect_order_data"]["product_stock"]),
                    reply_markup=get_back_cancel_kb(lang)
                )
                # נשאר באותו state כדי שהמשתמש יוכל לנסות שוב
                return CollectOrderDataStates.QUANTITY

            context.user_data["collect_order_data"]["quantity"] = quantity


    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]

    from config.kb import get_select_price_kb
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_or_enter_total_price", lang), reply_markup=get_select_price_kb(lang))

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
    from funcs.utils import create_order_obj
    order = create_order_obj(order_data)
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
    
    # Check if conversation data exists
    if "collect_order_data" not in context.user_data:
        print(f"🔧 cancel: No conversation data")
        return ConversationHandler.END
    
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    await msg.delete()
    del context.user_data["collect_order_data"]

    # פתיחה אוטומטית של תפריט (cancel לא קורא ל-start() ישירות)
    import asyncio
    from funcs.utils import delayed_start
    asyncio.create_task(delayed_start(update, context))

    return ConversationHandler.END

async def step_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """חזרה חכמה עם טיפול בכל התרחישים"""
    logger = logging.getLogger(__name__)
    logger.info("🔄 step_back called - Advanced navigation")

    await update.callback_query.answer()

    # Check if conversation data exists
    if "collect_order_data" not in context.user_data:
        logger.warning("🔄 No conversation data - conversation already ended")
        return ConversationHandler.END

    stack = context.user_data["collect_order_data"]["navigation_stack"]

    if len(stack) <= 1:
        # אין אחורה - סגור הזמנה וחזור לתפריט ראשי
        logger.info("🔄 No more steps back - ending conversation")
        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        await msg.delete()
        del context.user_data["collect_order_data"]

        # Return to main menu
        from funcs.bot_funcs import start
        await start(update, context)

        return ConversationHandler.END

    # הוצא את המצב הנוכחי
    current_state = stack.pop()
    logger.info(f"🔄 Popped current state: {current_state}")

    # קבל את המצב הקודם
    previous_state = stack[-1]
    logger.info(f"🔄 Going back to: {previous_state}")

    # טפל לפי סוג המצב הקודם
    if previous_state["type"] == "order":
        return await restore_order_state(update, context, previous_state)

    elif previous_state["type"] == "product":
        return await restore_product_state(update, context, previous_state)

    elif previous_state["type"] == "edit":
        return await restore_edit_state(update, context, previous_state)

    # אם לא מצא סוג - סגור הזמנה
    logger.error(f"🔄 Unknown state type: {previous_state}")
    return ConversationHandler.END


async def restore_order_state(update, context, state_data):
    """שחזור מצב הזמנה כללי"""
    logger = logging.getLogger(__name__)
    logger.info(f"🔄 Restoring order state: {state_data}")

    lang = context.user_data["collect_order_data"]["lang"]
    state = state_data["state"]
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]

    if state == CollectOrderDataStates.NAME:
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            t("enter_client_name", lang),
            reply_markup=get_cancel_kb(lang)
        )
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.NAME
        return CollectOrderDataStates.NAME

    elif state == CollectOrderDataStates.USERNAME:
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            t("enter_client_username", lang),
            reply_markup=get_username_kb(lang)
        )
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.USERNAME
        return CollectOrderDataStates.USERNAME

    elif state == CollectOrderDataStates.PHONE:
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            t("enter_client_phone", lang),
            reply_markup=get_back_cancel_kb(lang)
        )
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.PHONE
        return CollectOrderDataStates.PHONE

    elif state == CollectOrderDataStates.ADDRESS:
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            t("enter_client_address", lang),
            reply_markup=get_back_cancel_kb(lang)
        )
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.ADDRESS
        return CollectOrderDataStates.ADDRESS

    elif state == CollectOrderDataStates.PRODUCT_LIST:
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            t("choose_product", lang),
            reply_markup=get_products_markup(update.effective_user)
        )
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.PRODUCT_LIST
        return CollectOrderDataStates.PRODUCT_LIST

    logger.error(f"🔄 Unknown order state: {state}")
    return ConversationHandler.END


async def restore_product_state(update, context, state_data):
    """שחזור מצב הוספת מוצר"""
    logger = logging.getLogger(__name__)
    logger.info(f"🔄 Restoring product state: {state_data}")

    # עדיין לא מיושם - יחזור לרשימת מוצרים
    return await restore_order_state(update, context, {
        "state": CollectOrderDataStates.PRODUCT_LIST,
        "action": "back_to_product_list"
    })


async def restore_edit_state(update, context, state_data):
    """שחזור מצב עריכת מוצר"""
    logger = logging.getLogger(__name__)
    logger.info(f"🔄 Restoring edit state: {state_data}")

    # עדיין לא מיושם - יחזור לרשימת מוצרים
    return await restore_order_state(update, context, {
        "state": CollectOrderDataStates.PRODUCT_LIST,
        "action": "back_to_product_list"
    })


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
    from funcs.utils import create_order_obj
    order_obj = create_order_obj(result)
    new_text = await form_confirm_order(order_obj, lang)

    final_msg = await msg.edit_text(new_text, parse_mode=ParseMode.HTML)

    try:
        from db.db import get_bot_setting
        order_chat = get_bot_setting('order_chat') or links.ORDER_CHAT
        if order_chat:
            # Send BILINGUAL message to courier group (RU + HE)
            crourier_text = await form_confirm_order_courier(order_obj, 'ru')  # lang param ignored - now bilingual
            markup = await form_courier_action_kb(order_obj.id, 'ru')  # lang param ignored - now bilingual
            await context.bot.send_message(order_chat, crourier_text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception as e:
        traceback.print_exc()
        print(f'Failed to forward message about new order. Error: {e}')

    del context.user_data["collect_order_data"]

    # פתיחה אוטומטית של תפריט
    import asyncio
    from funcs.utils import delayed_start
    asyncio.create_task(delayed_start(update, context))

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
        CallbackQueryHandler(collect_username, '^skip_username$'),  # כפתור דלג
        MessageHandler(filters.Regex('^@.+$'), collect_username)     # הודעה עם @
    ],
    CollectOrderDataStates.PHONE: [
        MessageHandler(filters.Regex('^.+$'), collect_phone)
    ],
    CollectOrderDataStates.ADDRESS: [
        MessageHandler(filters.Regex('^.+$'), collect_address),
        MessageHandler(filters.LOCATION, collect_address),
    ],
    CollectOrderDataStates.PRODUCT_LIST: [
        CallbackQueryHandler(new_product_name, '^create$'),
        CallbackQueryHandler(collect_product, r'^\d+$'),
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


def check_pending_order(update: Update) -> bool:
    """Check if there's a pending order with data."""
    # This is a filter function for the entry point
    return False  # We'll handle this differently

NEW_ORDER_HANDLER = DebugConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_collect_data, '^new$'),
        # Add entry point for resuming order after product creation
        CallbackQueryHandler(resume_order_with_product, r'^\d+$')
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(step_back, '^back$'),
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    conversation_timeout=120
)