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

async def start_collect_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """START function of collecting data for new order."""
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    
    # ניקוי הודעה קודמת
    await clean_previous_message(update, context)

    session = Session()
    shift = session.query(Shift).filter(Shift.status==ShiftStatus.opened).first()
    session.close()

    if not shift:
        msg = await update.effective_message.reply_text(t("need_open_shift_for_order", lang))
        save_message_id(context, msg.message_id)
        return ConversationHandler.END

    start_msg = await send_message_with_cleanup(update, context, t("enter_client_name", lang), reply_markup=get_cancel_kb(lang))
    context.user_data["collect_order_data"] = {}
    context.user_data["collect_order_data"]["start_msg"] = start_msg
    context.user_data["collect_order_data"]["products"] = []
    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.START
    context.user_data["collect_order_data"]["lang"] = lang
    
    # שמירת ID לניקוי עתידי
    save_message_id(context, start_msg.message_id)

    return CollectOrderDataStates.NAME

async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting name and go to next step @username."""
    lang = context.user_data["collect_order_data"]["lang"]
    
    if update.callback_query:
        await update.callback_query.answer()
        # אם זה callback query, זה כנראה כפתור "חזור" או "ביטול"
        return CollectOrderDataStates.NAME
    else:
        try:
            await update.effective_message.delete()
        except:
            pass

        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.NAME
        name = update.message.text[:100]
        context.user_data["collect_order_data"]["name"] = name

        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        context.user_data["collect_order_data"]["start_msg"] = await edit_message_with_cleanup(update, context, t("enter_client_username", lang), reply_markup=get_username_kb(lang))

        return CollectOrderDataStates.USERNAME

async def collect_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collecting @username or skip."""
    lang = context.user_data["collect_order_data"]["lang"]
    
    if update.callback_query:
        await update.callback_query.answer()
        
        if update.callback_query.data == "skip_username":
            # דילוג על username
            context.user_data["collect_order_data"]["username"] = ""
            context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.USERNAME
            
            msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
            context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("enter_client_phone", lang), reply_markup=get_back_cancel_kb(lang))
            
            return CollectOrderDataStates.PHONE
    else:
        try:
            await update.effective_message.delete()
        except:
            pass
        context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.USERNAME
        
        username = update.message.text[:36]
        context.user_data["collect_order_data"]["username"] = username

        msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
        context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("enter_client_phone", lang), reply_markup=get_back_cancel_kb(lang))

        return CollectOrderDataStates.PHONE

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
        context.user_data["collect_order_data"]["start_msg"] = await edit_message_with_cleanup(update, context, t("enter_address", lang), reply_markup=get_back_cancel_kb(lang))

        return CollectOrderDataStates.ADDRESS

async def collect_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


async def new_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start of creation of new product."""
    lang = context.user_data["collect_order_data"]["lang"]
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("enter_new_product_name", lang), reply_markup=get_cancel_kb(lang))

    return CollectOrderDataStates.NEW_PRODUCT_STOCK


async def new_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saving new prouct name and continue to adding stock for new product."""
    lang = context.user_data["collect_order_data"]["lang"]
    
    if not update.callback_query:
        await update.effective_message.delete()

    context.user_data["collect_order_data"]["new_product_name"] = update.message.text[:22]

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("enter_new_product_stock", lang), reply_markup=get_cancel_kb(lang))

    return CollectOrderDataStates.SAVE_NEW_PRODUCT

async def save_new_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saving new product. Returining choosing a product for new order."""
    lang = context.user_data["collect_order_data"]["lang"]
    
    if not update.callback_query:
        await update.effective_message.delete()

    stock = int(update.message.text[:10])

    session = Session()
    product = Product(
        name=context.user_data["collect_order_data"]["new_product_name"],
        stock=stock,
    )
    session.add(product)
    session.commit()
    print(product)
    session.close()

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_product", lang), reply_markup=get_products_markup(update.effective_user))

    return CollectOrderDataStates.PRODUCT

async def collect_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Collecting product."""
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()
    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.PRODUCT

    if update.callback_query.data.isdigit():
        session = Session()
        product = session.query(Product).filter(Product.id==int(update.callback_query.data)).first()

        context.user_data["collect_order_data"]["product"] = product.name
        context.user_data["collect_order_data"]["product_stock"] = product.stock
        session.close()

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_or_enter_quantity", lang), reply_markup=SELECT_QUANTITY_KB)

    return CollectOrderDataStates.QUANTITY

async def collect_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

async def collect_total_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

async def add_more_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()
    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.PRODUCT

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(t("choose_product", lang), reply_markup=get_products_markup(update.effective_user))

    return CollectOrderDataStates.PRODUCT

async def go_to_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Go to final confirming order."""
    lang = context.user_data["collect_order_data"]["lang"]
    await update.callback_query.answer()

    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.ADD_MORE_PRODUCTS_OR_CONFIRM

    order = Order(
        client_name=context.user_data["collect_order_data"]["name"],
        client_username=context.user_data["collect_order_data"]["username"],
        client_phone=context.user_data["collect_order_data"]["phone"],
        address=context.user_data["collect_order_data"]["address"],
    )

    order.set_products(context.user_data["collect_order_data"]["products"])
    order.total_order_price = order.calculate_total_price()  # חישוב מחיר כולל

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    text = t("confirm_order_check", lang) + (await form_confirm_order(order, lang))
    context.user_data["collect_order_data"]["start_msg"] = await msg.edit_text(text, reply_markup=get_confirm_order_kb(lang), parse_mode=ParseMode.HTML)

    return CollectOrderDataStates.CONFIRM_OR_NOT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]
    await msg.delete()
    del context.user_data["collect_order_data"]

    return ConversationHandler.END

async def step_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()

    step = context.user_data["collect_order_data"]["step"] - 1

    if step == 0:
        await update.effective_message.delete()
        await start_collect_data(update,context,)
        return step + 1
    elif step == 1:
        await collect_name(update,context,)
        return step + 1
    elif step == 2:
        await collect_username(update,context,)
        return step + 1
    elif step == 3:
        await collect_phone(update,context,)
        return step + 1
    elif step == 4:
        await collect_address(update,context,)
        return step + 1
    elif step == 5:
        await collect_product(update,context,)
        return step + 1
    elif step == 6:
        await collect_quantity(update,context,)
        return step + 1
    elif step == 7 or step == 78:
        await collect_total_price(update,context,)
        return step + 1
    elif step == 8:
        await go_to_confirm(update,context,)
        return step + 1

    print(step)
    return step

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = context.user_data["collect_order_data"]["lang"]
    context.user_data["collect_order_data"]["step"] = CollectOrderDataStates.CONFIRM_OR_NOT

    msg: TgMessage = context.user_data["collect_order_data"]["start_msg"]

    session = Session()
    order = Order(
        client_name=context.user_data["collect_order_data"]["name"],
        client_username=context.user_data["collect_order_data"]["username"],
        client_phone=context.user_data["collect_order_data"]["phone"],
        address=context.user_data["collect_order_data"]["address"],
    )
    order.set_products(context.user_data["collect_order_data"]["products"])

    session.add(order)
    session.commit()

    context.user_data["collect_order_data"]["order_id"] = order.id
    session.close()

    new_text = await form_confirm_order(order, lang)

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

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


NEW_ORDER_HANDLER = ConversationHandler(
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