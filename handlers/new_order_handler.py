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
from uuid import uuid4
from typing import Dict, Any, Optional

# Constants לפי המפרט החדש
SESSION_KEY = "collect_order_data"
ST_PRODUCT = "product_selection"
ST_QUANTITY = "quantity_selection"
ST_PRICE = "price_selection"
ST_SUMMARY = "summary"

def get_session(context) -> Dict[str, Any]:
    """Get session data according to the new spec"""
    return context.user_data.get(SESSION_KEY, {})

def current_item(session) -> Optional[Dict[str, Any]]:
    """Get current item being edited"""
    cid = session.get("current_item_id")
    for it in session.get("order_items", []):
        if it.get("id") == cid:
            return it
    return None

def ensure_item(session) -> Dict[str, Any]:
    """Ensure we have a current item, create if needed"""
    it = current_item(session)
    if not it:
        it = {"id": str(uuid4())}
        session["order_items"].append(it)
        session["current_item_id"] = it["id"]
    return it

def remove_current_item(session):
    """Remove current item from order_items"""
    cid = session.get("current_item_id")
    if cid:
        session["order_items"] = [it for it in session.get("order_items", []) if it.get("id") != cid]
        session["current_item_id"] = None

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

    # הגבל לגודל מקסימלי - מנע דליפת זיכרון
    MAX_STACK_SIZE = 20
    if len(stack) > MAX_STACK_SIZE:
        # הסר את הערך הישן ביותר
        removed = stack.pop(0)
        logger.warning(f"🔄 Navigation stack exceeded max size ({MAX_STACK_SIZE}), removed oldest entry: {removed.get('type', 'unknown')}")

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

    # אתחול מבנה הנתונים לפי המפרט החדש
    context.user_data["collect_order_data"] = {
        # נתוני לקוח בסיסיים
        "customer": {
            "name": None,
            "username": None,
            "phone": None,
            "address": None
        },

        # לפי המפרט החדש
        "current_step": "product_selection",  # התחלה עם בחירת מוצר
        "order_items": [],  # רשימת הפריטים
        "current_item_id": None,  # הפריט הנוכחי

        # נתונים נוספים
        "start_msg": start_msg,
        "lang": lang,
        "meta": {
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
            "ttl_sec": 3600
        }
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
    logger = logging.getLogger(__name__)
    print(f"🔧 collect_name called")

    # בדיקת אבטחה - וודא שיש נתוני שיחה
    if "collect_order_data" not in context.user_data:
        logger.error("❌ collect_name: No collect_order_data in context")
        return ConversationHandler.END

    try:
        lang = context.user_data["collect_order_data"]["lang"]
    except KeyError:
        logger.error("❌ collect_name: No lang in collect_order_data")
        return ConversationHandler.END

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

        # אימות קלט בסיסי
        if not update.message or not update.message.text:
            logger.warning("⚠️ collect_name: No message text")
            return CollectOrderDataStates.NAME

        # שמור את השם במבנה החדש
        try:
            context.user_data["collect_order_data"]["customer"]["name"] = update.message.text[:100]
            context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.USERNAME
        except KeyError as e:
            logger.error(f"❌ collect_name: Missing key in context: {e}")
            return ConversationHandler.END

        # הוסף ל-navigation stack
        push_navigation_state(context, "order", {
            "state": CollectOrderDataStates.USERNAME,
            "action": f'enter_client_username (name: {update.message.text[:100]})'
        })

        logger.info(f"📝 Customer name collected: {update.message.text[:100]}")

        # Edit the bot's message, not the user's message
        try:
            msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
            from funcs.utils import edit_conversation_message
            context.user_data["collect_order_data"]["start_msg"] = await edit_conversation_message(
                msg,
                t("enter_client_username", lang),
                reply_markup=get_username_kb(lang)
            )
            print(f"🔧 Edited bot message to ask for username")
        except Exception as e:
            logger.error(f"❌ collect_name: Failed to edit message: {e}")
            # נסה לשלוח הודעה חדשה כגיבוי
            try:
                new_msg = await update.effective_chat.send_message(
                    t("enter_client_username", lang),
                    reply_markup=get_username_kb(lang)
                )
                context.user_data["collect_order_data"]["start_msg"] = new_msg
            except Exception as e2:
                logger.error(f"❌ collect_name: Failed to send new message: {e2}")
                return ConversationHandler.END

        return CollectOrderDataStates.USERNAME

async def collect_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting @username or skip (empty string)."""
    logger = logging.getLogger(__name__)
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
        try:
            msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
            context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
                t("enter_client_phone", lang),
                reply_markup=get_back_cancel_kb(lang)
            )
        except Exception as e:
            logger.error(f"❌ collect_username: Failed to edit message: {e}")
            try:
                new_msg = await update.effective_chat.send_message(
                    t("enter_client_phone", lang),
                    reply_markup=get_back_cancel_kb(lang)
                )
                context.user_data["collect_order_data"]["start_msg"] = new_msg
            except Exception as e2:
                logger.error(f"❌ collect_username: Failed to send new message: {e2}")
                return ConversationHandler.END
        
        return CollectOrderDataStates.PHONE
    except Exception as e:
        print(f"❌ ERROR in collect_username: {e}")
        import traceback
        traceback.print_exc()
        return ConversationHandler.END

async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting phone."""
    logger = logging.getLogger(__name__)
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
    logger = logging.getLogger(__name__)
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
        import copy
        context.user_data["order_state_before_product_creation"] = {
            "collect_order_data": copy.deepcopy(context.user_data["collect_order_data"]),
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
    """Collect product selection according to new spec"""
    session = get_session(context)
    await update.callback_query.answer()

    _, value = update.callback_query.data.split(":", 1)
    product_id = int(value)

    # Get product from DB
    from db.db import get_product_by_id
    product = get_product_by_id(product_id)

    if product:
        # Create new item
        it = ensure_item(session)
        # Reset quantity/price if changing product
        if it.get("product") and it["product"] != product['name']:
            it.pop("quantity", None)
            it.pop("price", None)
        it["product"] = product['name']

        session["current_step"] = ST_QUANTITY
        return await show_quantity(update, context)
    else:
        logger.error(f"❌ Product not found: ID {product_id}")
        return await show_product(update, context)

async def collect_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect quantity according to new spec"""
    session = get_session(context)
    _, value = update.callback_query.data.split(":", 1)
    qty = int(value)

    it = ensure_item(session)
    it["quantity"] = qty
    session["current_step"] = ST_PRICE
    return await show_price(update, context)
async def collect_total_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect price according to new spec"""
    session = get_session(context)
    _, value = update.callback_query.data.split(":", 1)
    price = int(value)

    it = ensure_item(session)
    it["price"] = price
    session["current_step"] = ST_SUMMARY
    return await show_summary(update, context)
async def add_more_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add more products - Phase 3: Product Addition"""
    logger = logging.getLogger(__name__)
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()

    # עדכן מצב נוכחי
    context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.PRODUCT_LIST

    # הוסף ל-navigation stack
    push_navigation_state(context, "order", {
        "state": CollectOrderDataStates.PRODUCT_LIST,
        "action": "add_more_products_selected"
    })

    logger.info("➕ User chose to add more products")

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
        t("choose_product", lang),
        reply_markup=get_products_markup(update.effective_user)
    )

    return CollectOrderDataStates.PRODUCT_LIST


async def start_edit_product_by_index(update, context, product_index: int) -> int:
    """Start editing a product by index (for back navigation) - Phase 4: Product Editing"""
    logger = logging.getLogger(__name__)
    lang = context.user_data["collect_order_data"]["lang"]

    # בדוק שיש מוצרים ושהאינדקס תקין
    products = context.user_data["collect_order_data"].get("products", [])
    if product_index >= len(products) or product_index < 0:
        logger.error(f"❌ Product index out of range: {product_index}, products count: {len(products)}")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "product_index_out_of_range"
        })

    product = products[product_index]

    # יצור active_product לעריכה עם התחלה ממחיר (השלב האחרון)
    context.user_data["collect_order_data"]["active_product"] = {
        "index": product_index,
        "state": ProductStates.ENTER_PRICE,  # התחל ממחיר
        "edit_mode": False,  # זה overwrite, לא עריכה רגילה
        "original_data": product.copy(),  # שמור את הנתונים המקוריים
        "temp_data": product.copy()  # התחל עם הנתונים הקיימים
    }

    # עדכן מצב נוכחי
    context.user_data["collect_order_data"]["current_state"] = ProductStates.ENTER_PRICE

    # הוסף ל-navigation stack
    push_navigation_state(context, "product", {
        "product_index": product_index,
        "state": ProductStates.ENTER_PRICE,
        "action": f'editing_existing_product_{product.get("name", "unknown")}'
    })

    logger.info(f"🔄 Started back-editing product: {product.get('name', 'unknown')} at index {product_index}")

    # הצג הזנת מחיר חדש
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    prompt = t("choose_or_enter_total_price", lang)
    if product.get("name"):
        prompt = f"{t('enter_price_for', lang)} {product['name']}"

    from config.kb import get_select_price_kb
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
        prompt,
        reply_markup=get_select_price_kb(lang)
    )

    return ProductStates.ENTER_PRICE

async def show_quantity_for_existing_product(update, context, product_index: int) -> int:
    """Show quantity selection for existing product (back navigation)"""
    logger = logging.getLogger(__name__)
    lang = context.user_data["collect_order_data"]["lang"]

    # עדכן את active_product לכמות
    context.user_data["collect_order_data"]["active_product"]["state"] = ProductStates.ENTER_QUANTITY

    # עדכן מצב נוכחי
    context.user_data["collect_order_data"]["current_state"] = ProductStates.ENTER_QUANTITY

    # הוסף ל-navigation stack
    push_navigation_state(context, "product", {
        "product_index": product_index,
        "state": ProductStates.ENTER_QUANTITY,
        "action": "back_to_quantity"
    })

    # הצג בחירת כמות
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    products = context.user_data["collect_order_data"].get("products", [])
    product = products[product_index] if product_index < len(products) else {}

    prompt = t("choose_or_enter_quantity", lang)
    if product.get("name"):
        prompt = f"{t('choose_quantity_for', lang)} {product['name']}"

    from config.kb import get_select_quantity_kb
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
        prompt,
        reply_markup=get_select_quantity_kb(lang)
    )

    return ProductStates.ENTER_QUANTITY

async def edit_product_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Edit product quantity - Phase 4: Product Editing"""
    logger = logging.getLogger(__name__)
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()

    # בדוק שיש active_product במצב עריכה
    if "active_product" not in context.user_data["collect_order_data"]:
        logger.error("❌ No active_product for quantity edit")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "no_active_product_for_quantity_edit"
        })

    active_product = context.user_data["collect_order_data"]["active_product"]
    if not active_product.get("edit_mode", False):
        logger.error("❌ active_product not in edit mode")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "not_in_edit_mode"
        })

    # עדכן מצב
    active_product["state"] = EditStates.EDIT_QUANTITY
    context.user_data["collect_order_data"]["current_state"] = EditStates.EDIT_QUANTITY

    # הוסף ל-navigation stack
    push_navigation_state(context, "edit", {
        "product_index": active_product["index"],
        "state": EditStates.EDIT_QUANTITY,
        "action": "chose_to_edit_quantity"
    })

    logger.info(f"📝 Starting quantity edit for product at index {active_product['index']}")

    # הצג הזנת כמות חדשה
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    product_name = active_product["temp_data"].get("name", "מוצר לא ידוע")
    current_quantity = active_product["temp_data"].get("quantity", 0)

    from config.kb import get_select_quantity_kb
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
        f"📝 {t('edit_quantity_for', lang)} {product_name}\n\n{t('current_quantity', lang)}: {current_quantity}\n{t('enter_new_quantity', lang)}",
        reply_markup=get_select_quantity_kb(lang)
    )

    return EditStates.EDIT_QUANTITY


async def edit_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Edit product price - Phase 4: Product Editing"""
    logger = logging.getLogger(__name__)
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()

    # בדוק שיש active_product במצב עריכה
    if "active_product" not in context.user_data["collect_order_data"]:
        logger.error("❌ No active_product for price edit")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "no_active_product_for_price_edit"
        })

    active_product = context.user_data["collect_order_data"]["active_product"]
    if not active_product.get("edit_mode", False):
        logger.error("❌ active_product not in edit mode")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "not_in_edit_mode"
        })

    # עדכן מצב
    active_product["state"] = EditStates.EDIT_PRICE
    context.user_data["collect_order_data"]["current_state"] = EditStates.EDIT_PRICE

    # הוסף ל-navigation stack
    push_navigation_state(context, "edit", {
        "product_index": active_product["index"],
        "state": EditStates.EDIT_PRICE,
        "action": "chose_to_edit_price"
    })

    logger.info(f"💰 Starting price edit for product at index {active_product['index']}")

    # הצג הזנת מחיר חדש
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    product_name = active_product["temp_data"].get("name", "מוצר לא ידוע")
    current_price = active_product["temp_data"].get("unit_price", 0)

    from config.kb import get_select_price_kb
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
        f"💰 {t('edit_price_for', lang)} {product_name}\n\n{t('current_price', lang)}: ₪{current_price}\n{t('enter_new_price', lang)}",
        reply_markup=get_select_price_kb(lang)
    )

    return EditStates.EDIT_PRICE


async def delete_product_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Delete product from order - Phase 4: Product Editing"""
    logger = logging.getLogger(__name__)
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()

    # בדוק שיש active_product במצב עריכה
    if "active_product" not in context.user_data["collect_order_data"]:
        logger.error("❌ No active_product for delete")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "no_active_product_for_delete"
        })

    active_product = context.user_data["collect_order_data"]["active_product"]
    product_index = active_product["index"]
    product_name = active_product["temp_data"].get("name", "מוצר לא ידוע")

    # מחק את המוצר מהרשימה
    products = context.user_data["collect_order_data"].get("products", [])
    if 0 <= product_index < len(products):
        deleted_product = products.pop(product_index)
        logger.info(f"🗑️ Deleted product: {deleted_product.get('name', 'unknown')}")

        # נקה active_product
        del context.user_data["collect_order_data"]["active_product"]

        # עדכן מצב נוכחי
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.PRODUCT_LIST

        # הוסף ל-navigation stack
        push_navigation_state(context, "order", {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": f"deleted_product_{product_name}"
        })

        # הצג רשימת מוצרים מעודכנת
        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        if products:
            from funcs.utils import create_product_list_text
            product_list_text = create_product_list_text(products, lang)

            from config.kb import get_product_management_kb
            context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
                f"🗑️ {t('product_deleted', lang)}: {product_name}\n\n{product_list_text}",
                reply_markup=get_product_management_kb(lang),
                parse_mode=ParseMode.HTML
            )
        else:
            # אין יותר מוצרים - חזור לבחירת מוצר ראשון
            context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
                f"🗑️ {t('product_deleted', lang)}: {product_name}\n\n{t('no_products_in_order', lang)}\n\n{t('choose_product', lang)}",
                reply_markup=get_products_markup(update.effective_user)
            )

        return CollectOrderDataStates.PRODUCT_LIST
    else:
        logger.error(f"❌ Cannot delete product at index {product_index}, products count: {len(products)}")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "cannot_delete_product"
        })


async def apply_edit_changes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Apply edit changes and return to product list - Phase 4: Product Editing"""
    logger = logging.getLogger(__name__)
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()

    # בדוק שיש active_product במצב עריכה
    if "active_product" not in context.user_data["collect_order_data"]:
        logger.error("❌ No active_product to apply changes")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "no_active_product_to_apply"
        })

    active_product = context.user_data["collect_order_data"]["active_product"]
    if not active_product.get("edit_mode", False):
        logger.error("❌ active_product not in edit mode")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "not_in_edit_mode_for_apply"
        })

    product_index = active_product["index"]
    temp_data = active_product["temp_data"]

    # עדכן את המוצר ברשימה עם הנתונים הזמניים
    products = context.user_data["collect_order_data"].get("products", [])
    if 0 <= product_index < len(products):
        # חשב מחיר כולל חדש
        temp_data["total_price"] = temp_data["quantity"] * temp_data["unit_price"]

        products[product_index] = temp_data.copy()
        logger.info(f"✅ Applied changes to product at index {product_index}: {temp_data.get('name', 'unknown')}")

        # נקה active_product
        del context.user_data["collect_order_data"]["active_product"]

        # עדכן מצב נוכחי
        context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.PRODUCT_LIST

        # הוסף ל-navigation stack
        push_navigation_state(context, "order", {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": f"applied_changes_to_{temp_data.get('name', 'unknown')}"
        })

        # הצג רשימת מוצרים מעודכנת
        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        from funcs.utils import create_product_list_text
        product_list_text = create_product_list_text(products, lang)

        from config.kb import get_product_management_kb
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            f"✅ {t('changes_applied', lang)}\n\n{product_list_text}",
            reply_markup=get_product_management_kb(products, lang),
            parse_mode=ParseMode.HTML
        )

        return CollectOrderDataStates.PRODUCT_LIST
    else:
        logger.error(f"❌ Cannot apply changes to product at index {product_index}")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "cannot_apply_changes"
        })


async def cancel_edit_changes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel edit changes and return to product list - Phase 4: Product Editing"""
    logger = logging.getLogger(__name__)
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()

    # בדוק שיש active_product במצב עריכה
    if "active_product" not in context.user_data["collect_order_data"]:
        logger.warning("⚠️ No active_product to cancel - already clean")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "no_active_product_to_cancel"
        })

    active_product = context.user_data["collect_order_data"]["active_product"]
    if not active_product.get("edit_mode", False):
        logger.warning("⚠️ active_product not in edit mode")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "not_in_edit_mode_for_cancel"
        })

    product_name = active_product["temp_data"].get("name", "מוצר לא ידוע")
    logger.info(f"❌ Cancelled editing of product: {product_name}")

    # נקה active_product - השינויים לא נשמרו
    del context.user_data["collect_order_data"]["active_product"]

    # עדכן מצב נוכחי
    context.user_data["collect_order_data"]["current_state"] = CollectOrderDataStates.PRODUCT_LIST

    # הוסף ל-navigation stack
    push_navigation_state(context, "order", {
        "state": CollectOrderDataStates.PRODUCT_LIST,
        "action": f"cancelled_editing_{product_name}"
    })

    # הצג רשימת מוצרים (ללא שינויים)
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    products = context.user_data["collect_order_data"].get("products", [])

    if products:
        from funcs.utils import create_product_list_text
        product_list_text = create_product_list_text(products, lang)

        from config.kb import get_product_management_kb
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            f"❌ {t('changes_cancelled', lang)}\n\n{product_list_text}",
            reply_markup=get_product_management_kb(products, lang),
            parse_mode=ParseMode.HTML
        )
    else:
        # אין מוצרים
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            f"❌ {t('changes_cancelled', lang)}\n\n{t('no_products_in_order', lang)}",
            reply_markup=get_products_markup(update.effective_user)
        )

    return CollectOrderDataStates.PRODUCT_LIST


async def apply_quantity_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Apply quantity edit changes - Phase 4: Product Editing"""
    logger = logging.getLogger(__name__)
    lang = context.user_data["collect_order_data"]["lang"]

    # בדוק שיש active_product במצב עריכה כמות
    if "active_product" not in context.user_data["collect_order_data"]:
        logger.error("❌ No active_product for quantity edit apply")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "no_active_product_for_quantity_apply"
        })

    active_product = context.user_data["collect_order_data"]["active_product"]
    if not active_product.get("edit_mode", False) or active_product["state"] != EditStates.EDIT_QUANTITY:
        logger.error("❌ Not in quantity edit mode")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "not_in_quantity_edit_mode"
        })

    if not update.callback_query:
        await update.effective_message.delete()

        try:
            new_quantity = int(update.message.text[:100])
        except ValueError:
            logger.warning("⚠️ Invalid quantity in edit")
            # הצג הודעת שגיאה וחזור להזנת כמות
            msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
            from config.kb import get_select_quantity_kb
            product_name = active_product["temp_data"].get("name", "מוצר לא ידוע")
            await msg.edit_text(
                f"📝 {t('edit_quantity_for', lang)} {product_name}\n\n{t('invalid_quantity', lang)}\n{t('enter_new_quantity', lang)}",
                reply_markup=get_select_quantity_kb(lang)
            )
            return EditStates.EDIT_QUANTITY

        # בדוק מלאי
        available_stock = active_product["temp_data"]["stock"]
        if available_stock < new_quantity:
            logger.warning(f"⚠️ Not enough stock in edit: requested {new_quantity}, available {available_stock}")
            msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
            from config.kb import get_back_cancel_kb
            await msg.edit_text(
                f"📝 {t('edit_quantity_for', lang)} {active_product['temp_data'].get('name', 'מוצר לא ידוע')}\n\n{t('not_enough_stock', lang)}\n{t('available_stock', lang)}: {available_stock}",
                reply_markup=get_back_cancel_kb(lang)
            )
            return EditStates.EDIT_QUANTITY

        # עדכן את הכמות ב-temp_data
        active_product["temp_data"]["quantity"] = new_quantity
        # חשב מחיר כולל חדש
        active_product["temp_data"]["total_price"] = new_quantity * active_product["temp_data"]["unit_price"]

        logger.info(f"📝 Updated quantity to {new_quantity} for product {active_product['temp_data']['name']}")

        # חזור לאפשרויות עריכה
        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        product_name = active_product["temp_data"].get("name", "מוצר לא ידוע")

        from config.kb import get_edit_product_options_kb
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            f"✅ {t('quantity_updated', lang)}: {new_quantity}\n\n✏️ {t('editing_product', lang)}: {product_name}\n\n{t('choose_edit_action', lang)}",
            reply_markup=get_edit_product_options_kb(lang)
        )

        # עדכן מצב
        active_product["state"] = EditStates.SELECT_EDIT_ACTION
        context.user_data["collect_order_data"]["current_state"] = EditStates.SELECT_EDIT_ACTION

        # הוסף ל-navigation stack
        push_navigation_state(context, "edit", {
            "product_index": active_product["index"],
            "state": EditStates.SELECT_EDIT_ACTION,
            "action": f"quantity_updated_to_{new_quantity}"
        })

        return EditStates.SELECT_EDIT_ACTION

    # אם זה callback query, זה אומר שהמשתמש לחץ על כפתור כמות מהמקלדת
    # נעביר את הערך לטיפול כהודעת טקסט
    return await apply_quantity_edit(update, context)


async def apply_price_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Apply price edit changes - Phase 4: Product Editing"""
    logger = logging.getLogger(__name__)
    lang = context.user_data["collect_order_data"]["lang"]

    # בדוק שיש active_product במצב עריכה מחיר
    if "active_product" not in context.user_data["collect_order_data"]:
        logger.error("❌ No active_product for price edit apply")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "no_active_product_for_price_apply"
        })

    active_product = context.user_data["collect_order_data"]["active_product"]
    if not active_product.get("edit_mode", False) or active_product["state"] != EditStates.EDIT_PRICE:
        logger.error("❌ Not in price edit mode")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "not_in_price_edit_mode"
        })

    if not update.callback_query:
        await update.effective_message.delete()

        try:
            new_price = float(update.message.text[:11])
        except ValueError:
            logger.warning("⚠️ Invalid price in edit")
            # הצג הודעת שגיאה וחזור להזנת מחיר
            msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
            from config.kb import get_select_price_kb
            product_name = active_product["temp_data"].get("name", "מוצר לא ידוע")
            await msg.edit_text(
                f"💰 {t('edit_price_for', lang)} {product_name}\n\n{t('invalid_price', lang)}\n{t('enter_new_price', lang)}",
                reply_markup=get_select_price_kb(lang)
            )
            return EditStates.EDIT_PRICE

        # עדכן את המחיר ב-temp_data
        active_product["temp_data"]["unit_price"] = new_price
        # חשב מחיר כולל חדש
        active_product["temp_data"]["total_price"] = active_product["temp_data"]["quantity"] * new_price

        logger.info(f"💰 Updated price to {new_price}₪ for product {active_product['temp_data']['name']}")

        # חזור לאפשרויות עריכה
        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        product_name = active_product["temp_data"].get("name", "מוצר לא ידוע")

        from config.kb import get_edit_product_options_kb
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            f"✅ {t('price_updated', lang)}: ₪{new_price}\n\n✏️ {t('editing_product', lang)}: {product_name}\n\n{t('choose_edit_action', lang)}",
            reply_markup=get_edit_product_options_kb(lang)
        )

        # עדכן מצב
        active_product["state"] = EditStates.SELECT_EDIT_ACTION
        context.user_data["collect_order_data"]["current_state"] = EditStates.SELECT_EDIT_ACTION

        # הוסף ל-navigation stack
        push_navigation_state(context, "edit", {
            "product_index": active_product["index"],
            "state": EditStates.SELECT_EDIT_ACTION,
            "action": f"price_updated_to_{new_price}"
        })

        return EditStates.SELECT_EDIT_ACTION

    # אם זה callback query, זה אומר שהמשתמש לחץ על כפתור מחיר מהמקלדת
    # נעביר את הערך לטיפול כהודעת טקסט
    return await apply_price_edit(update, context)


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
    """חזרה לפי חוקי המפרט החדש"""
    session = get_session(context)
    step = session.get("current_step")
    it = current_item(session)

    if step == ST_SUMMARY:
        # מסיכום → לבחירת מחיר (לא מוחקים כלום)
        session["current_step"] = ST_PRICE
        return await show_price(update, context)
    elif step == ST_PRICE and it:
        # ממחיר → לכמות (מוחקים מחיר)
        it.pop("price", None)
        session["current_step"] = ST_QUANTITY
        return await show_quantity(update, context)
    elif step == ST_QUANTITY and it:
        # מכמות → למוצר (מוחקים כמות)
        it.pop("quantity", None)
        session["current_step"] = ST_PRODUCT
        return await show_product(update, context)
    elif step == ST_PRODUCT:
        # ממוצר → מסיכום או להתחלה
        if it:
            remove_current_item(session)
        if session.get("order_items"):
            session["current_step"] = ST_SUMMARY
            return await show_summary(update, context)
        else:
            # חזרה לתחילת הזמנה
            await update.callback_query.edit_message_text("הזמנה בוטלה - חוזרים לתפריט הראשי")
            return ConversationHandler.END

    # fallback
    await update.callback_query.answer("אין שלב קודם")
    return session.get("current_step", ST_PRODUCT)

# פונקציות תצוגה לפי המפרט החדש
async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצג בחירת מוצר"""
    session = get_session(context)
    lang = session.get("lang", "he")

    txt = t("choose_product", lang)
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=get_products_markup(update.effective_user))
    else:
        await update.message.reply_text(txt, reply_markup=get_products_markup(update.effective_user))

async def show_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצג בחירת כמות"""
    session = get_session(context)
    lang = session.get("lang", "he")

    txt = t("choose_or_enter_quantity", lang)
    await update.callback_query.edit_message_text(txt, reply_markup=get_select_quantity_kb(lang))

async def show_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצג בחירת מחיר"""
    session = get_session(context)
    lang = session.get("lang", "he")

    txt = t("choose_or_enter_total_price", lang)
    await update.callback_query.edit_message_text(txt, reply_markup=get_select_price_kb(lang))

def format_summary(session) -> str:
    """פורמט סיכום ההזמנה"""
    lang = session.get("lang", "he")
    lines = [t("order_summary", lang)]
    total = 0
    for it in session.get("order_items", []):
        p, q, r = it.get("product"), it.get("quantity"), it.get("price")
        if p and q and r:
            lines.append(f"• {p} × {q} = ₪{r}")
            total += r
    lines.append(f"{t('total', lang)}: ₪{total}")
    return "\n".join(lines)

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצג סיכום הזמנה"""
    session = get_session(context)
    txt = format_summary(session)
    lang = session.get("lang", "he")

    # יצירת כפתורים לסיכום
    from config.kb import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_confirm_order", lang), callback_data="confirm")],
        [InlineKeyboardButton(t("btn_add", lang), callback_data="add_new_after_selection")],
        [InlineKeyboardButton(t("btn_back", lang), callback_data="back")],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data="cancel")]
    ])

    await update.callback_query.edit_message_text(txt, reply_markup=kb)

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
    """שחזור מצב הוספת מוצר - Phase 3: Product Addition"""
    logger = logging.getLogger(__name__)
    logger.info(f"🔄 Restoring product state: {state_data}")

    lang = context.user_data["collect_order_data"]["lang"]
    state = state_data["state"]
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]

    # צור active_product אם לא קיים
    if "active_product" not in context.user_data["collect_order_data"]:
        logger.warning("⚠️ No active_product during restore, creating from state_data")
        # נסה ליצור active_product מהמידע ב-state_data
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "fallback_to_product_list"
        })

    active_product = context.user_data["collect_order_data"]["active_product"]
    temp_data = active_product["temp_data"]

    if state == ProductStates.SELECT_PRODUCT:
        # חזרה לבחירת מוצר
        context.user_data["collect_order_data"]["current_state"] = ProductStates.SELECT_PRODUCT
        active_product["state"] = ProductStates.SELECT_PRODUCT

        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            t("choose_product", lang),
            reply_markup=get_products_markup(update.effective_user)
        )
        return CollectOrderDataStates.PRODUCT_LIST

    elif state == ProductStates.ENTER_QUANTITY:
        # חזרה להזנת כמות
        context.user_data["collect_order_data"]["current_state"] = ProductStates.ENTER_QUANTITY
        active_product["state"] = ProductStates.ENTER_QUANTITY

        prompt = t("choose_or_enter_quantity", lang)
        if temp_data.get("name"):
            prompt = f"{t('choose_quantity_for', lang)} {temp_data['name']}"

        from config.kb import get_select_quantity_kb
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            prompt,
            reply_markup=get_select_quantity_kb(lang)
        )
        return CollectOrderDataStates.QUANTITY

    elif state == ProductStates.ENTER_PRICE:
        # חזרה להזנת מחיר
        context.user_data["collect_order_data"]["current_state"] = ProductStates.ENTER_PRICE
        active_product["state"] = ProductStates.ENTER_PRICE

        prompt = t("choose_or_enter_total_price", lang)
        if temp_data.get("name"):
            prompt = f"{t('enter_price_for', lang)} {temp_data['name']}"

        from config.kb import get_select_price_kb
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            prompt,
            reply_markup=get_select_price_kb(lang)
        )
        return CollectOrderDataStates.TOTAL_PRICE

    logger.error(f"🔄 Unknown product state: {state}")
    return await restore_order_state(update, context, {
        "state": CollectOrderDataStates.PRODUCT_LIST,
        "action": "unknown_product_state"
    })


async def restore_edit_state(update, context, state_data):
    """שחזור מצב עריכת מוצר - Phase 4: Product Editing"""
    logger = logging.getLogger(__name__)
    logger.info(f"🔄 Restoring edit state: {state_data}")

    lang = context.user_data["collect_order_data"]["lang"]
    state = state_data["state"]
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]

    # צור active_product אם לא קיים
    if "active_product" not in context.user_data["collect_order_data"]:
        logger.warning("⚠️ No active_product during edit restore, creating from state_data")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "fallback_to_product_list_from_edit"
        })

    active_product = context.user_data["collect_order_data"]["active_product"]
    if not active_product.get("edit_mode", False):
        logger.warning("⚠️ active_product not in edit mode during restore")
        return await restore_order_state(update, context, {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "not_in_edit_mode_during_restore"
        })

    temp_data = active_product["temp_data"]

    if state == EditStates.SELECT_EDIT_ACTION:
        # חזרה לאפשרויות עריכה
        context.user_data["collect_order_data"]["current_state"] = EditStates.SELECT_EDIT_ACTION
        active_product["state"] = EditStates.SELECT_EDIT_ACTION

        product_name = temp_data.get("name", "מוצר לא ידוע")

        from config.kb import get_edit_product_options_kb
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            f"✏️ {t('editing_product', lang)}: {product_name}\n\n{t('choose_edit_action', lang)}",
            reply_markup=get_edit_product_options_kb(lang)
        )
        return EditStates.SELECT_EDIT_ACTION

    elif state == EditStates.EDIT_QUANTITY:
        # חזרה להזנת כמות
        context.user_data["collect_order_data"]["current_state"] = EditStates.EDIT_QUANTITY
        active_product["state"] = EditStates.EDIT_QUANTITY

        product_name = temp_data.get("name", "מוצר לא ידוע")
        current_quantity = temp_data.get("quantity", 0)

        from config.kb import get_select_quantity_kb
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            f"📝 {t('edit_quantity_for', lang)} {product_name}\n\n{t('current_quantity', lang)}: {current_quantity}\n{t('enter_new_quantity', lang)}",
            reply_markup=get_select_quantity_kb(lang)
        )
        return EditStates.EDIT_QUANTITY

    elif state == EditStates.EDIT_PRICE:
        # חזרה להזנת מחיר
        context.user_data["collect_order_data"]["current_state"] = EditStates.EDIT_PRICE
        active_product["state"] = EditStates.EDIT_PRICE

        product_name = temp_data.get("name", "מוצר לא ידוע")
        current_price = temp_data.get("unit_price", 0)

        from config.kb import get_select_price_kb
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(
            f"💰 {t('edit_price_for', lang)} {product_name}\n\n{t('current_price', lang)}: ₪{current_price}\n{t('enter_new_price', lang)}",
            reply_markup=get_select_price_kb(lang)
        )
        return EditStates.EDIT_PRICE

    logger.error(f"🔄 Unknown edit state: {state}")
    return await restore_order_state(update, context, {
        "state": CollectOrderDataStates.PRODUCT_LIST,
        "action": "unknown_edit_state"
    })


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger = logging.getLogger(__name__)
    await update.callback_query.answer()
    lang = context.user_data["collect_order_data"]["lang"]
    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.CONFIRM_OR_NOT

    # איפוס ה-flag כשמאשרים הזמנה סופית
    context.user_data["collect_order_data"]["last_action_was_product_addition"] = False

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]

    # Using Supabase only
    from db.db import db_client
    import json
    import datetime
    
    # שימוש במבנה הנתונים החדש
    customer = context.user_data["collect_order_data"]["customer"]

    order_data = {
        'client_name': customer.get("name"),
        'client_username': customer.get("username"),
        'client_phone': customer.get("phone"),
        'client_address': customer.get("address"),
        'products': json.dumps(context.user_data["collect_order_data"]["products"]),
        'total_order_price': sum(product.get('total_price', 0) for product in context.user_data["collect_order_data"]["products"]),
        'status': 'active',
        'created': datetime.datetime.now().isoformat()
    }
    
    result = db_client.insert('orders', order_data)
    context.user_data["collect_order_data"]["order_id"] = result.get('id')

    # Create object-like structure for compatibility
    from funcs.utils import create_order_obj
    order_obj = create_order_obj(result)
    new_text = await form_confirm_order(order_obj, lang)

    try:
        final_msg = await msg.edit_text(new_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"❌ confirm_order: Failed to edit final message: {e}")
        # נסה לשלוח הודעה חדשה
        try:
            final_msg = await update.effective_chat.send_message(new_text, parse_mode=ParseMode.HTML)
        except Exception as e2:
            logger.error(f"❌ confirm_order: Failed to send final message: {e2}")
            final_msg = None

    # שליחת הודעה לקבוצת השליחים
    try:
        from db.db import get_bot_setting
        order_chat = get_bot_setting('order_chat') or links.ORDER_CHAT
        if order_chat and order_obj and hasattr(order_obj, 'id') and order_obj.id:
            # Send BILINGUAL message to courier group (RU + HE)
            crourier_text = await form_confirm_order_courier(order_obj, 'ru')  # lang param ignored - now bilingual
            from config.kb import form_courier_action_kb
            markup = await form_courier_action_kb(order_obj.id, 'ru')  # lang param ignored - now bilingual
            await context.bot.send_message(order_chat, crourier_text, parse_mode=ParseMode.HTML, reply_markup=markup)
            logger.info(f"📨 Order notification sent to courier group: {order_chat}")
        else:
            logger.warning("⚠️ No order_chat configured or invalid order_obj - order notification not sent")
    except Exception as e:
        logger.error(f"❌ Failed to send order notification to courier group: {e}")
        traceback.print_exc()

    del context.user_data["collect_order_data"]

    # פתיחה אוטומטית של תפריט
    import asyncio
    from funcs.utils import delayed_start
    asyncio.create_task(delayed_start(update, context))

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger = logging.getLogger(__name__)

    # בדיקת אבטחה
    if "collect_order_data" not in context.user_data:
        logger.warning("⚠️ timeout_reached: No collect_order_data in context")
        return ConversationHandler.END

    try:
        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        lang = get_user_lang(update.effective_user.id) if update.effective_user else 'ru'
        await msg.reply_text(t("timeout_error", lang))
        logger.info("⏰ Conversation timed out - cleaned up user data")
    except Exception as e:
        logger.error(f"❌ timeout_reached: Failed to send timeout message: {e}")

    # נקה את הנתונים בכל מקרה
    if "collect_order_data" in context.user_data:
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
    ST_PRODUCT: [
        CallbackQueryHandler(collect_product, r'^SET_PRODUCT:.+'),
    ],
    ST_QUANTITY: [
        CallbackQueryHandler(collect_quantity, r'^SET_QTY:\d+'),
    ],
    ST_PRICE: [
        CallbackQueryHandler(collect_total_price, r'^SET_PRICE:\d+'),
    ],
    ST_SUMMARY: [
        CallbackQueryHandler(go_to_confirm, '^confirm$'),
        CallbackQueryHandler(add_more_products, '^add_new_after_selection$'),
        CallbackQueryHandler(step_back, '^back$'),
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    EditStates.SELECT_EDIT_ACTION: [
        CallbackQueryHandler(edit_product_quantity, '^edit_quantity$'),
        CallbackQueryHandler(edit_product_price, '^edit_price$'),
        CallbackQueryHandler(delete_product_confirm, '^delete_product$'),
        CallbackQueryHandler(apply_edit_changes, '^apply_edit$'),
        CallbackQueryHandler(cancel_edit_changes, '^cancel_edit$'),
    ],
    EditStates.EDIT_QUANTITY: [
        CallbackQueryHandler(apply_quantity_edit, r'^\d+$'),
        MessageHandler(filters.Regex(r'^\d+$'), apply_quantity_edit),
    ],
    EditStates.EDIT_PRICE: [
        MessageHandler(filters.Regex(r'^\d+(\.\d+)?$'), apply_price_edit),
        CallbackQueryHandler(apply_price_edit, r'^\d+$'),
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