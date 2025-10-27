from telegram.ext import CallbackQueryHandler, TypeHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram import Message, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.constants import ParseMode
from geopy.geocoders import Nominatim
from db.db import *
from config.config import *
from config.translations import t, get_user_lang
from funcs.utils import *
from funcs.bot_funcs import *
import asyncio

class EndShiftStates:
    OPERATOR_PAID = 0
    RUNNER_PAID = 1
    PETROL_PAID = 2
    CONFIRM = 3


async def start_end_shift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Начало процесса завершения смены.
    """
    print(f"🔧 start_end_shift called")
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)
    print(f"DEBUG: User {update.effective_user.id} language: {lang}")  # Debug log
    
    # Using Supabase only
    from db.db import get_opened_shift
    shift = get_opened_shift()

    if not shift:
        await update.effective_message.edit_text(t("no_open_shifts", lang))
        return

    # Convert dict to object-like
    class ShiftObj:
        def __init__(self, data):
            import datetime
            for k, v in data.items():
                if isinstance(v, str) and 'T' in v and '-' in v:  # ISO datetime
                    try:
                        v = datetime.datetime.fromisoformat(v)
                    except:
                        pass
                setattr(self, k, v)
    
    shift_obj = ShiftObj(shift) if isinstance(shift, dict) else shift

    # Initialize end_shift_data for confirm_end_shift
    context.user_data["end_shift_data"] = {
        "lang": lang,
        "shift_id": shift['id'],
        "start_msg": update.effective_message
    }
    print(f"🔧 Initialized end_shift_data with shift_id: {shift['id']}")

    # הצגת דיאלוג אישור
    from funcs.utils import show_confirmation_dialog
    import datetime
    opened_time_str = shift['opened_time'] if isinstance(shift, dict) else shift.opened_time
    if isinstance(opened_time_str, str):
        opened_time = datetime.datetime.fromisoformat(opened_time_str)
    else:
        opened_time = opened_time_str
    shift_details = f"סיום משמרת - {opened_time.strftime('%d.%m.%Y %H:%M')}"
    await show_confirmation_dialog(
        update, context, 
        t("end_shift_action", lang), 
        shift_details, 
        lang
    )

    return ConversationHandler.END


async def collect_operator_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.delete()
    lang = context.user_data["end_shift_data"]["lang"]

    context.user_data["end_shift_data"]["operator_paid"] = int(update.effective_message.text)
    start_msg: Message = context.user_data["end_shift_data"]["start_msg"]
    context.user_data["end_shift_data"]["start_msg"] = await start_msg.edit_text(t("enter_courier_payment", lang), reply_markup=get_cancel_kb(lang), parse_mode=ParseMode.HTML)

    return EndShiftStates.RUNNER_PAID

async def collect_runner_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.delete()
    lang = context.user_data["end_shift_data"]["lang"]

    context.user_data["end_shift_data"]["runner_paid"] = int(update.effective_message.text)
    start_msg: Message = context.user_data["end_shift_data"]["start_msg"]
    context.user_data["end_shift_data"]["start_msg"] = await start_msg.edit_text(t("enter_petrol_payment", lang), reply_markup=get_cancel_kb(lang), parse_mode=ParseMode.HTML)

    return EndShiftStates.PETROL_PAID


async def collect_petrol_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.delete()
    lang = context.user_data["end_shift_data"]["lang"]
    context.user_data["end_shift_data"]["petrol_paid"] = int(update.effective_message.text)

    # Using Supabase only
    from db.db import get_opened_shift, get_all_orders
    
    shift = get_opened_shift()
    
    # Convert datetime
    import datetime
    if isinstance(shift['opened_time'], str):
        opened_time = datetime.datetime.fromisoformat(shift['opened_time'])
    else:
        opened_time = shift['opened_time']
    
    shift_start_date = opened_time.strftime("%d.%m.%Y, %H:%M:%S")

    # Get all completed orders and filter by time range
    all_orders = get_all_orders()
    orders = []
    for o in all_orders:
        if o.get('status') == 'completed' and o.get('delivered'):
            delivered_time = datetime.datetime.fromisoformat(o['delivered']) if isinstance(o['delivered'], str) else o['delivered']
            if opened_time <= delivered_time <= datetime.datetime.now():
                orders.append(o)

    # Extract all products from orders
    all_products = []
    for order in orders:
        products = json.loads(order.get('products', '[]'))
        all_products.extend(products)

    print(all_products)

    summary = {}
    total_sum = 0  # Variable to store total sum

    # Iterate through all products
    for product in all_products:
        name = product["name"]
        quantity = product["quantity"]
        total_price = product["total_price"]

        # Calculate sum for current product
        current_product_total = total_price
        total_sum += current_product_total  # Add to total sum

        # If product already exists in dictionary, update quantity and sum
        if name in summary:
            summary[name]["total_quantity"] += quantity
            summary[name]["total_price"] += current_product_total
        else:
            # If product doesn't exist, add it to dictionary
            summary[name] = {
                "total_quantity": quantity,
                "total_price": current_product_total
            }

    samples = []
    qty_text = t("units", lang)

    for name, data in summary.items():
        sample_text = f"{name} - {data['total_quantity']} {qty_text} - {data['total_price']} ₪"
        samples.append(sample_text)
    
    context.user_data["end_shift_data"]["summary"] = summary

    products_fetched_text = '\n'.join(samples)

    context.user_data["end_shift_data"]["products_fetched_text"] = products_fetched_text

    total_sum_text = t("total_sum_delivered_products", lang)
    products_fetched_text += f'\n\n{total_sum_text}: {total_sum} ₪'

    context.user_data["end_shift_data"]["brutto"] = total_sum
    context.user_data["end_shift_data"]["netto"] = total_sum - context.user_data["end_shift_data"]["operator_paid"] - context.user_data["end_shift_data"]["runner_paid"] - context.user_data["end_shift_data"]["petrol_paid"]

    text = f"""
{t("check_shift_data", lang)}

{t("shift_start_time", lang).format(shift_start_date)}
{t("operator_payment", lang).format(context.user_data["end_shift_data"]["operator_paid"])}
{t("courier_payment", lang).format(context.user_data["end_shift_data"]["runner_paid"])}
{t("petrol_payment", lang).format(context.user_data["end_shift_data"]["petrol_paid"])}

{t("shift_products_summary", lang).format(products_fetched_text)}

"""
    context.user_data["end_shift_data"]["petrol_paid"] = int(update.effective_message.text)
    start_msg: Message = context.user_data["end_shift_data"]["start_msg"]
    context.user_data["end_shift_data"]["start_msg"] = await start_msg.edit_text(text, reply_markup=get_confirm_order_kb(lang), parse_mode=ParseMode.HTML)

    return EndShiftStates.CONFIRM


async def confirm_end_shift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"🔧 confirm_end_shift called")
    await update.callback_query.answer()
    
    # Get language first
    lang = get_user_lang(update.effective_user.id)
    
    # Get or initialize end_shift_data
    if "end_shift_data" not in context.user_data:
        print(f"⚠️ end_shift_data not found, initializing...")
        from db.db import get_opened_shift
        shift = get_opened_shift()
        context.user_data["end_shift_data"] = {
            "lang": lang,
            "shift_id": shift['id'],
            "start_msg": update.effective_message,
            "operator_paid": 0,
            "runner_paid": 0,
            "petrol_paid": 0,
            "brutto": 0,
            "netto": 0,
            "products_fetched_text": "",
            "summary": {}
        }
    else:
        # Use existing lang from context
        lang = context.user_data["end_shift_data"].get("lang", lang)
    
    print(f"🔧 Language: {lang}")
    
    # Using Supabase only
    from db.db import db_client, get_user_by_id
    
    shift_id = context.user_data["end_shift_data"].get("shift_id")
    if not shift_id:
        # Get the opened shift
        from db.db import get_opened_shift
        opened_shift = get_opened_shift()
        shift_id = opened_shift['id']
    print(f"🔧 Shift ID: {shift_id}")
    
    user = get_user_by_id(update.effective_user.id)

    # Update shift in Supabase
    import datetime
    from db.db import Shift
    
    # Get products
    shift = {'id': shift_id}
    products_list = Shift.set_products()
    
    update_data = {
        'operator_paid': context.user_data["end_shift_data"].get("operator_paid", 0),
        'runner_paid': context.user_data["end_shift_data"].get("runner_paid", 0),
        'petrol_paid': context.user_data["end_shift_data"].get("petrol_paid", 0),
        'brutto': context.user_data["end_shift_data"].get("brutto", 0),
        'netto': context.user_data["end_shift_data"].get("netto", 0),
        'products_fetched_text': context.user_data["end_shift_data"].get("products_fetched_text", ""),
        'operator_close_id': user.get('user_id'),
        'operator_close_username': user.get('username'),
        'summary': json.dumps(context.user_data["end_shift_data"].get("summary", {})),
        'products_end': json.dumps(products_list),
        'closed_time': datetime.datetime.now().isoformat(),
        'status': 'closed'
    }
    print(f"🔧 Updating shift in Supabase with data: {update_data}")
    db_client.update('shifts', update_data, {'id': shift_id})
    
    # Create object for report
    class ShiftObj:
        def __init__(self, data):
            for k, v in data.items():
                if isinstance(v, str) and 'T' in v and '-' in v:
                    try:
                        v = datetime.datetime.fromisoformat(v)
                    except:
                        pass
                setattr(self, k, v)
    
    shift_data = db_client.select('shifts', {'id': shift_id})[0]
    shift_obj = ShiftObj(shift_data)
    print(f"🔧 Shift object created for report")
    
    report = await form_end_shift_report(shift_obj, lang)
    print(f"🔧 Report generated")

    start_msg: Message = context.user_data["end_shift_data"].get("start_msg", update.effective_message)
    context.user_data["end_shift_data"]["start_msg"] = await start_msg.edit_text(report, parse_mode=ParseMode.HTML)
    await update.effective_message.reply_text(t("shift_closed_success", lang))
    print(f"🔧 Report sent to user")

    try:
        from db.db import get_bot_setting
        admin_chat = get_bot_setting('admin_chat') or links.ADMIN_CHAT
        if admin_chat:
            await context.bot.send_message(admin_chat, report, parse_mode=ParseMode.HTML)
            print(f"🔧 Report sent to admin chat: {admin_chat}")
    except Exception as e:
        error_msg = t("error_sending_report", lang)
        await update.effective_message.reply_text(f"{error_msg}: {repr(e)}")
        print(f"❌ Error sending report to admin: {e}")

    # שליחת דוח סיום משמרת לקבוצת מנהלים
    try:
        from funcs.utils import send_shift_end_report_to_admins
        await send_shift_end_report_to_admins(shift_obj, lang)
        print(f"🔧 Report sent to admins group")
    except Exception as e:
        print(f"❌ Error sending shift end report to admins: {e}")

    # החזרה למסך הראשי
    from config.kb import build_start_menu
    from funcs.utils import send_message_with_cleanup
    reply_markup = await build_start_menu(update.effective_user.id)
    await send_message_with_cleanup(update, context, t("main_menu", lang), reply_markup=reply_markup)
    print(f"🔧 Main menu sent")

    if "end_shift_data" in context.user_data:
        del context.user_data["end_shift_data"]
    
    print(f"✅ confirm_end_shift completed successfully")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["end_shift_data"]["lang"]
    await update.callback_query.answer(t('operation_cancelled', lang))
    msg: Message = context.user_data["end_shift_data"]["start_msg"]
    await msg.delete()
    del context.user_data["end_shift_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data["end_shift_data"]["lang"]
    msg: Message = context.user_data["end_shift_data"]["start_msg"]
    await msg.edit_text(t("timeout_error", lang))
    del context.user_data["end_shift_data"]

    return ConversationHandler.END


states = {
    EndShiftStates.OPERATOR_PAID: [
        MessageHandler(filters.Regex(r'^\d+$'), collect_operator_paid),
    ],
    EndShiftStates.RUNNER_PAID: [
        MessageHandler(filters.Regex(r'^\d+$'), collect_runner_paid),
    ],
    EndShiftStates.PETROL_PAID: [
        MessageHandler(filters.Regex(r'^\d+$'), collect_petrol_paid),
    ],
    EndShiftStates.CONFIRM: [
        CallbackQueryHandler(confirm_end_shift, pattern='confirm'),
    ],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}


END_SHIFT_HANDLER = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_end_shift, pattern="end_shift")
    ],
    states=states,
    fallbacks=[
        CallbackQueryHandler(cancel, '^cancel$'),
    ],
    conversation_timeout=120,
)