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

    # בדיקה אם הגענו ממלאי נוכחי - חשוב לניווט חזרה נכון
    from funcs.utils import peek_navigation_history
    last_menu = peek_navigation_history(context)
    came_from_inventory = (last_menu and last_menu.get('menu') == 'stock_list_menu')

    if came_from_inventory:
        context.user_data['came_from_inventory'] = True
        print(f"🔍 Edit product: Came from inventory, setting navigation flag")

    # שינוי: שימוש ב-keyboard החדש עם כפתור חזור
    from config.kb import get_edit_product_kb_with_back
    start_msg = await update.effective_message.edit_text(
        t("product_info", lang).format(product.get('name'), product.get('stock')),
        reply_markup=get_edit_product_kb_with_back(lang),
        parse_mode=ParseMode.HTML
    )
    context.user_data["edit_product_data"] = {}
    context.user_data["edit_product_data"]["start_msg"] = start_msg
    context.user_data["edit_product_data"]["product"] = product
    context.user_data["edit_product_data"]["lang"] = lang

    return EditProductStates.CHOOSE_ACTION


async def edit_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data["edit_product_data"]["lang"]

    msg = context.user_data["edit_product_data"]["start_msg"]
    product = context.user_data["edit_product_data"]["product"]

    # הוספת כפתור חזרה להודעת הטקסט
    from config.kb import get_cancel_kb
    await msg.edit_text(
        t("enter_new_stock", lang).format(product.get('name')),
        reply_markup=get_cancel_kb(lang)
    )

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

    # פתיחה אוטומטית של תפריט
    import asyncio
    from funcs.utils import delayed_start
    asyncio.create_task(delayed_start(update, context))

    return ConversationHandler.END

async def edit_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start editing product name"""
    await update.callback_query.answer()
    lang = context.user_data["edit_product_data"]["lang"]

    msg = context.user_data["edit_product_data"]["start_msg"]
    product = context.user_data["edit_product_data"]["product"]

    # הוספת כפתור חזרה להודעת הטקסט
    from config.kb import get_cancel_kb
    await msg.edit_text(
        t("enter_new_name", lang).format(product.get('name')),
        reply_markup=get_cancel_kb(lang)
    )

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

    # פתיחה אוטומטית של תפריט
    import asyncio
    from funcs.utils import delayed_start
    asyncio.create_task(delayed_start(update, context))

    return ConversationHandler.END

async def edit_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start editing product price"""
    await update.callback_query.answer()
    lang = context.user_data["edit_product_data"]["lang"]

    msg = context.user_data["edit_product_data"]["start_msg"]
    product = context.user_data["edit_product_data"]["product"]

    # הוספת כפתור חזרה להודעת הטקסט
    from config.kb import get_cancel_kb
    await msg.edit_text(
        t("enter_new_price", lang).format(product.get('name'), product.get('price', 0)),
        reply_markup=get_cancel_kb(lang)
    )

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

        # פתיחה אוטומטית של תפריט
        import asyncio
        from funcs.utils import delayed_start
        asyncio.create_task(delayed_start(update, context))

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

    # פתיחה אוטומטית של תפריט
    import asyncio
    from funcs.utils import delayed_start
    asyncio.create_task(delayed_start(update, context))

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    msg: Message = context.user_data["edit_product_data"]["start_msg"]
    await msg.delete()
    del context.user_data["edit_product_data"]

    # פתרון: בדיקה מאיפה באנו וחזרה לשם
    if context.user_data.get('came_from_inventory'):
        # באנו ממלאי נוכחי - חזרה לשם
        from funcs.bot_funcs import show_rest_from_last_day
        await show_rest_from_last_day(update, context, from_back_button=True)
    else:
        # באנו ממקום אחר - חזרה לעמוד הבית
        from funcs.bot_funcs import start
        await start(update, context)

    # cancel כבר קורא ל-start() ישירות - אין צורך ב-delayed_start()

    return ConversationHandler.END

async def back_to_product_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """חזרה לרשימת המוצרים ללא שמירת שינויים"""
    await update.callback_query.answer()

    # מחיקת הודעה נוכחית
    msg = context.user_data["edit_product_data"]["start_msg"]
    await msg.delete()

    # ניקוי נתונים
    del context.user_data["edit_product_data"]

    # חזרה לרשימת מלאי נוכחי
    from funcs.bot_funcs import show_rest_from_last_day
    await show_rest_from_last_day(update, context, from_back_button=True)

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
        CallbackQueryHandler(back_to_product_list, '^back_to_product_list$'),  # הוספה
    ],
    EditProductStates.EDIT_STOCK_END: [
        MessageHandler(filters.Regex(r'^\d+$'), edit_product_stock_end),
        CallbackQueryHandler(cancel, '^cancel$'),  # כפתור ביטול
    ],
    EditProductStates.EDIT_NAME_END: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_name_end),
        CallbackQueryHandler(cancel, '^cancel$'),  # כפתור ביטול
    ],
    EditProductStates.EDIT_PRICE_END: [
        MessageHandler(filters.Regex(r'^\d+$'), edit_product_price_end),
        CallbackQueryHandler(cancel, '^cancel$'),  # כפתור ביטול
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


EDIT_PRODUCT_HANDLER = ConversationHandler(
    entry_points=[
        # When clicking on product from list (edit_7)
        CallbackQueryHandler(start_edit_product, '^edit_[0-9]+$'),
        # When clicking on specific action from edit menu (edit_stock_7, edit_price_7, etc.)
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