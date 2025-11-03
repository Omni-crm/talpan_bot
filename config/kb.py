from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from enum import Enum
from config.config import *
from config.translations import t, get_user_lang
from db.db import *

class Notifications(Enum):
    NOTIF_CLIENT_ORDER_ACTIVE = "Курьер в пути, пожалуйста, спуститесь"


async def get_all_active_orders_to_msg_kb():
    # Using Supabase only
    from db.db import db_client
    
    all_orders = db_client.select('orders')
    orders = [o for o in all_orders if o.get('status') in ['active', 'delay', 'pending']]

    if orders:
        mrkp = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(f"#{o['id']}|{o.get('client_username', '')}", callback_data=f"msg_{o['id']}")] for o in orders]
        )
        return mrkp


def get_shift_end_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_end_shift', lang), callback_data="ending")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )

SHIFT_END_KB = get_shift_end_kb('ru')

async def build_start_menu(user_id):
    """Build main menu keyboard for user"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"🔧 build_start_menu() called for user {user_id}")

    # Using Supabase only
    from db.db import db_client, get_opened_shift

    users = db_client.select('users', {'user_id': user_id})
    user = users[0] if users else None
    logger.info(f"👤 User data loaded: {user}")

    # Check for open shift using the centralized function
    shift = get_opened_shift()
    logger.info(f"🔧 Shift check result: {shift is not None}")

    # Get user's language
    lang = user.get('lang', 'ru') if user else 'ru'
    logger.info(f"🌍 Menu language: {lang}")
    
    inline_keyboard=[
        [InlineKeyboardButton(t('btn_new_order', lang), callback_data="new")],
        [InlineKeyboardButton(t('btn_start_shift', lang), callback_data="beginning")],
        [InlineKeyboardButton(t('btn_current_stock', lang), callback_data="rest")],
        [InlineKeyboardButton(t('btn_manage_stock', lang), callback_data="manage_stock")],
        [InlineKeyboardButton(t('btn_msg_client', lang), callback_data="msg_client")],
        [InlineKeyboardButton(t('btn_admin', lang), callback_data="show_admin_menu")],
        [InlineKeyboardButton(t('btn_change_language', lang), callback_data="change_language")],
    ]

    if shift:
        inline_keyboard[1] = [InlineKeyboardButton(t('btn_end_shift', lang), callback_data="end_shift")]

    if user and user.get('role', 'guest') != 'guest':
        user_role = user.get('role', 'guest')
        logger.info(f"👤 User role: {user_role}")

        if user_role == 'admin':
            inline_keyboard = inline_keyboard[:]
        elif user_role == 'operator':
            inline_keyboard = inline_keyboard[:-2]
        elif user_role == 'stockman':
            inline_keyboard = inline_keyboard[-1:]
        elif user_role == 'courier':  # CRITICAL FIX: Use 'courier' (Role.RUNNER.value) not 'runner'!
            from db.db import get_bot_setting
            order_chat = get_bot_setting('order_chat') or links.ORDER_CHAT
            logger.info(f"🚚 Courier order_chat: {order_chat}")
            if order_chat:
                inline_keyboard=[
                    [InlineKeyboardButton(t('btn_couriers_group', lang), url=f"https://t.me/{order_chat.replace('@', '')}")],
                ]

        START_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
        logger.info(f"✅ Main menu keyboard created with {len(inline_keyboard)} buttons")
    else:
        START_KEYBOARD = None
        logger.warning(f"⚠️ No keyboard created - user not found or guest role")

    logger.info(f"🎯 build_start_menu() completed for user {user_id}")
    return START_KEYBOARD
    

# Keyboards שדורשים שפה - יהפכו לפונקציות
def get_cancel_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )

def get_back_cancel_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_back', lang), callback_data="back")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )

def get_add_more_or_confirm_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_back', lang), callback_data="back")],
            [InlineKeyboardButton(t('btn_confirm_order', lang), callback_data="to_confirm")],
            [InlineKeyboardButton(t('btn_add', lang), callback_data="add")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )

# Backward compatibility - ישארו כקיצור דרך
CANCEL_KB = get_cancel_kb('ru')
BACK_CANCEL_KB = get_back_cancel_kb('ru')
ADD_MORE_PRODUCTS_OR_CONFIRM_KB = get_add_more_or_confirm_kb('ru')

def get_products_markup(user):
    # Using Supabase only
    from db.db import db_client
    
    products = db_client.select('products')
    
    inline_keyboard = []
    delimiter = []
    for product in products:
        product_name = product.get('name', '')
        product_stock = product.get('stock', 0)
        product_id = product.get('id')
        
        # Add button with name and stock
        delimiter.append(InlineKeyboardButton(
            f"{product_name[:12]} ({product_stock})", 
            callback_data=str(product_id)
        ))
        
        # If we have 3 buttons, start a new row
        if len(delimiter) == 3:
            inline_keyboard.append(delimiter)
            delimiter = []
    
    # Add last row if there are remaining buttons
    if delimiter:
        inline_keyboard.append(delimiter)

    # += [InlineKeyboardButton('⬅️Back', callback_data="back")], 
    inline_keyboard += [[InlineKeyboardButton('❌Cancel', callback_data="cancel")]]

    # if user.id in ADMINS:
    inline_keyboard = [[InlineKeyboardButton('⏬Create', callback_data="create")]] + inline_keyboard
    inline_keyboard = [[InlineKeyboardButton('⬅️Back', callback_data="back")]] + inline_keyboard

    reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    return reply_markup

def get_products_markup_left_edit_stock(lang='ru'):
    # Using Supabase only
    from db.db import db_client
    from config.translations import t
    
    products = db_client.select('products')
    
    inline_keyboard = []
    delimiter = []
    for product in products:
        product_name = product.get('name', '')
        product_stock = product.get('stock', 0)
        product_id = product.get('id')
        
        # Add button with name and stock
        delimiter.append(InlineKeyboardButton(
            f"{product_name[:8]} ({product_stock})", 
            callback_data=f"edit_{product_id}"
        ))
        
        # If we have 3 buttons, start a new row
        if len(delimiter) == 3:
            inline_keyboard.append(delimiter)
            delimiter = []

    # Add last row if there are remaining buttons
    if delimiter:
        inline_keyboard.append(delimiter)
    
    # Add navigation buttons - home button
    inline_keyboard.append([
        InlineKeyboardButton(t("btn_home", lang), callback_data="home")
    ])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    return reply_markup


def get_products_markup_left_edit_stock_crude(lang='ru'):
    # Using Supabase only
    from db.db import db_client
    
    products = db_client.select('products')
    
    inline_keyboard = []
    delimiter = []
    
    for product in products:
        # תיקון הלוגיקה: אם יש 3 כפתורים בשורה, התחל שורה חדשה
        if len(delimiter) == 3:
            inline_keyboard.append(delimiter)
            delimiter = []
        
        product_name = product.get('name', '')
        product_crude = product.get('crude', 0)
        product_stock = product.get('stock', 0)
        product_price = product.get('price', 0)
        product_id = product.get('id')
        
        # הוספת כפתור עם מלאי ומחיר
        delimiter.append(InlineKeyboardButton(
            f"{product_name[:6]} ({product_crude}) ({product_stock}) - {product_price}₪", 
            callback_data=f"edit_crude_{product_id}"
        ))

    # הוספת השורה האחרונה אם יש כפתורים
    if delimiter:
        inline_keyboard.append(delimiter)

    # הוספת כפתור הוספת מלאי ידנית
    inline_keyboard.append([InlineKeyboardButton(t('btn_add_manual_stock', lang), callback_data="add_manual_stock")])
    
    # הוספת כפתורי ניווט
    inline_keyboard.append([
        InlineKeyboardButton(t('btn_back', lang), callback_data="back"),
        InlineKeyboardButton(t('btn_home', lang), callback_data="home")
    ])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    return reply_markup


def get_confirm_order_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_confirm', lang), callback_data="confirm")],
            [InlineKeyboardButton(t('btn_back', lang), callback_data="back")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )

def get_edit_product_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_edit_name', lang), callback_data="edit_name")],
            [InlineKeyboardButton(t('btn_edit_stock', lang), callback_data="edit_stock")],
            [InlineKeyboardButton(t('btn_edit_price', lang), callback_data="edit_price")],
            [InlineKeyboardButton(t('btn_delete', lang), callback_data="delete")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )

def get_edit_product_crude_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_edit_crude', lang), callback_data="edit_crude")],
            [InlineKeyboardButton(t('btn_edit_stock', lang), callback_data="edit_stock")],
            [InlineKeyboardButton(t('btn_delete', lang), callback_data="delete")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )

# Backward compatibility
CONFIRM_ORDER_KB = get_confirm_order_kb('ru')
EDIT_PRODUCT_KB = get_edit_product_kb('ru')
EDIT_PRODUCT_W_CRUDE_KB = get_edit_product_crude_kb('ru')

def get_select_price_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton('250', callback_data="250"),
                InlineKeyboardButton('350', callback_data="350"),
                InlineKeyboardButton('400', callback_data="400"),
                InlineKeyboardButton('450', callback_data="450"),
                InlineKeyboardButton('500', callback_data="500"),
                InlineKeyboardButton('550', callback_data="550"),
            ],
            [InlineKeyboardButton('⬅️Back', callback_data="back")],
            [InlineKeyboardButton('❌Cancel', callback_data="cancel")],
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )

def get_select_quantity_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton('5', callback_data="5"),
                InlineKeyboardButton('10', callback_data="10"),
                InlineKeyboardButton('15', callback_data="15"),
                InlineKeyboardButton('20', callback_data="20"),
                InlineKeyboardButton('30', callback_data="30"),
                InlineKeyboardButton('40', callback_data="40"),
                InlineKeyboardButton('50', callback_data="50"),
                InlineKeyboardButton('60', callback_data="60"),
            ],
            [InlineKeyboardButton('⬅️Back', callback_data="back")],
            [InlineKeyboardButton('❌Cancel', callback_data="cancel")],
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )


def show_tg_session_action_kb(sess_id: str, lang='ru'):
    SESS_ACT_KB = InlineKeyboardMarkup([
        [InlineKeyboardButton('⬅️ Back', callback_data='back_session_kb')],
        [InlineKeyboardButton('✅ Make Active', callback_data=f'worker_{sess_id}')],
        [InlineKeyboardButton('❌ Delete', callback_data=f'del_sess_{sess_id}')],
        [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
    ])

    return SESS_ACT_KB

def create_tg_sessions_kb(lang='ru'):
    # Using Supabase only
    from db.db import db_client
    
    tgsessions = db_client.select('tgsessions', {'is_worker': False})
    worker_sessions = db_client.select('tgsessions', {'is_worker': True})
    worker_session = worker_sessions[0] if worker_sessions else None

    if not tgsessions and not worker_session:
        inline_keyboard = [
            [InlineKeyboardButton(t('btn_add_account', lang), callback_data='make_tg_session')],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=inline_keyboard,)

    inline_keyboard = [[InlineKeyboardButton(f'{sess.get("name", "")[:10]} {sess.get("username", "")[:10]}', callback_data=f'sess_{sess.get("id")}')] for sess in tgsessions]

    if worker_session:
        inline_keyboard = [[InlineKeyboardButton(f'✅ {worker_session.get("name", "")[:10]} {worker_session.get("username", "")[:10]}', callback_data=f'sess_{worker_session.get("id")}')]] + inline_keyboard

    inline_keyboard = [[InlineKeyboardButton(t('btn_add', lang), callback_data='make_tg_session')]] + inline_keyboard
    inline_keyboard.append([InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard,)


def get_two_step_ask_kb(lang='ru'):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Yes', callback_data='two_step_yes'), InlineKeyboardButton('No', callback_data='two_step_no')],
        [InlineKeyboardButton("Cancel", callback_data="cancel")],
        [InlineKeyboardButton(t("btn_home", lang), callback_data="home")]
    ])


def get_digits_kb(lang='ru'):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('1', callback_data='1'), InlineKeyboardButton('2', callback_data='2'), InlineKeyboardButton('3', callback_data='3')],
        [InlineKeyboardButton('4', callback_data='4'), InlineKeyboardButton('5', callback_data='5'), InlineKeyboardButton('6', callback_data='6')],
        [InlineKeyboardButton('7', callback_data='7'), InlineKeyboardButton('8', callback_data='8'), InlineKeyboardButton('9', callback_data='9')],
        [InlineKeyboardButton('0', callback_data='0'), InlineKeyboardButton('cancel', callback_data='cancel')],
        [InlineKeyboardButton(t("btn_home", lang), callback_data="home")]
    ])


async def form_courier_action_kb(order_id: int, lang: str = 'ru'):
    """
    Create BILINGUAL keyboard for courier actions (RU + HE)
    Used ONLY in courier group messages - so buttons are bilingual
    
    Note: This keyboard is sent to GROUP CHAT, so needs bilingual text
    """
    # For group messages - create bilingual buttons (RU + HE)
    # Other buttons already have bilingual format in translations
    back_ru = t('btn_back', 'ru')
    back_he = t('btn_back', 'he')
    home_ru = t('btn_home', 'ru')
    home_he = t('btn_home', 'he')
    
    COURIER_ACTION_KB = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_choose_minutes', 'ru'), callback_data=f"choose_min_{order_id}")],
            [InlineKeyboardButton(t('btn_write_minutes', 'ru'), callback_data=f"write_min_{order_id}")],
            [InlineKeyboardButton(t('btn_delay', 'ru'), callback_data=f"delay_min_{order_id}")],
            [InlineKeyboardButton(t('btn_delivered', 'ru'), callback_data=f"ready_{order_id}")],
            [InlineKeyboardButton(f"{back_ru} ({back_he})", callback_data="back"), 
             InlineKeyboardButton(f"{home_ru} ({home_he})", callback_data="home")],
        ],
    )

    return COURIER_ACTION_KB

async def form_operator_action_kb(order: Order, lang: str = 'ru'):
    """
    [🔔 Отправить уведомление клиенту]
    [📞 Позвонить клиенту]
    [📤 Отправить другое сообщение]
    """
    OPERATOR_ACTION_KB = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_notify_client', lang), callback_data=f"notif_{order.client_username.replace('@', '')}")],
            [InlineKeyboardButton(t('btn_call_client', lang), url=f"tg://resolve?domain={order.client_username.replace('@', '')}")],
            [InlineKeyboardButton(t('btn_send_other_msg', lang), callback_data=f"msg_{order.id}")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )

    return OPERATOR_ACTION_KB

def get_operator_shift_start_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("confirm_stock", lang), callback_data="confirm_stock_shift")],
            [InlineKeyboardButton(t("manual_edit", lang), callback_data="rest")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )

OPERATOR_SHIFT_START_ACTION_KB = get_operator_shift_start_kb('ru')

def get_orders_filter_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_filter_date", lang), callback_data="fdate")],
            [InlineKeyboardButton(t("btn_filter_product", lang), callback_data="fproduct")],
            [InlineKeyboardButton(t("btn_filter_client", lang), callback_data="fclient")],
            [InlineKeyboardButton(t("btn_filter_status", lang), callback_data="fstatus")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )


def get_filter_orders_by_status_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(status, callback_data=status)] for status in (Status.completed.value,Status.active.value,Status.pending.value,Status.cancelled.value,Status.delay.value,)
        ] + [
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")]
        ]
    )


# Excel export removed - now using text messages

ORDERS_FILTER_MENU_KB = get_orders_filter_kb('ru')
# FETCH_EXCEL_ORDERS removed - now using text messages


def get_security_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_manage_links", lang), callback_data="links")],
            [InlineKeyboardButton(t("btn_cleanup_old_data", lang), callback_data="cleanup")],
            [InlineKeyboardButton(t("btn_backup_db", lang), callback_data="dump")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )


def get_db_format_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_excel", lang), callback_data="xlsx")],
            [InlineKeyboardButton(t("btn_json", lang), callback_data="json")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )

SECURITY_KB = get_security_kb('ru')
DB_FORMAT_KB = get_db_format_kb('ru')


def get_quick_reports_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard = [
            [InlineKeyboardButton(t("daily_profit_report", lang), callback_data='daily_profit')],
            [InlineKeyboardButton(t("report_by_product", lang), callback_data='report_by_product')],
            [InlineKeyboardButton(t("report_by_area", lang), callback_data='report_by_area')],
            [InlineKeyboardButton(t("report_by_client", lang), callback_data='report_by_client')],
            [InlineKeyboardButton(t("report_by_price", lang), callback_data='report_by_price')],
            [InlineKeyboardButton(t("report_by_days", lang), callback_data='report_by_days')],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )

# Backward compatibility
QUICK_REPORTS_KB = get_quick_reports_kb('ru')


def get_filter_instruction_kb(lang='ru'):
    """Keyboard for filter instruction messages with navigation buttons"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), 
             InlineKeyboardButton(t("btn_home", lang), callback_data="home")]
        ]
    )


def get_change_links_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_change_admin_link", lang), callback_data="change_admin_group_link")],
            [InlineKeyboardButton(t("btn_change_courier_link", lang), callback_data="change_courier_group_link")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )

CHANGE_GROUPS_LINK_KB = get_change_links_kb('ru')


def get_manage_roles_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_add_operator", lang), callback_data="add_o"), InlineKeyboardButton(t("btn_remove_operator", lang), callback_data="del_o")],
            [InlineKeyboardButton(t("btn_add_courier", lang), callback_data="add_c"), InlineKeyboardButton(t("btn_remove_courier", lang), callback_data="del_c")],
            [InlineKeyboardButton(t("btn_add_stockman", lang), callback_data="add_s"), InlineKeyboardButton(t("btn_remove_stockman", lang), callback_data="del_s")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )


def get_admin_action_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_tg_accounts", lang), callback_data="show_tg_sessions")],
            [InlineKeyboardButton(t("btn_all_orders", lang), callback_data="all_orders")],
            [InlineKeyboardButton(t("btn_quick_reports", lang), callback_data="quick_reports")],
            [InlineKeyboardButton(t("btn_week_report", lang), callback_data="week_report")],
            [InlineKeyboardButton(t("btn_manage_users", lang), callback_data="manage_roles")],
            [InlineKeyboardButton(t("btn_view_staff", lang), callback_data="view_staff")],
            [InlineKeyboardButton(t("btn_security", lang), callback_data="security_menu")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )

MANAGE_ROLES_KB = get_manage_roles_kb('ru')
ADMIN_ACTION_KB = get_admin_action_kb('ru')

async def form_operator_templates_kb(order: Order, lang: str = 'ru'):
    # Using Supabase only
    from db.db import db_client
    
    templates = db_client.select('templates')

    inline_keyboard=[
        [InlineKeyboardButton(t('btn_add_template', lang), callback_data="new_shab")],
    ]

    for template in templates:
        inline_keyboard.append(
            [InlineKeyboardButton(f'{template.get("id")}. {template.get("name")}', callback_data=f"shab_{template.get("id")}_{order.id}")]
        )

    # Add navigation buttons
    inline_keyboard.append([InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")])

    TEMPLATE_ACTION_KB = InlineKeyboardMarkup(
        inline_keyboard=inline_keyboard,
    )

    return TEMPLATE_ACTION_KB

def get_edit_template_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_edit_name', lang), callback_data="edit_name")],
            [InlineKeyboardButton(t('btn_edit_text', lang), callback_data="edit_text")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )

def get_actions_template_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_send_to_client', lang), callback_data="send")],
            [InlineKeyboardButton(t('btn_edit_template', lang), callback_data="edit")],
            [InlineKeyboardButton(t('btn_delete_template', lang), callback_data="delete")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="back"), InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )

EDIT_TEMPLATE_KB = get_edit_template_kb('ru')
ACTIONS_TEMPLATE_KB = get_actions_template_kb('ru')

def get_courier_minutes_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton('5', callback_data="5"),
                InlineKeyboardButton('10', callback_data="10"),
                InlineKeyboardButton('15', callback_data="15"),
                InlineKeyboardButton('20', callback_data="20"),
                InlineKeyboardButton('25', callback_data="25"),
                InlineKeyboardButton('30', callback_data="30"),
            ],
            [
                InlineKeyboardButton('35', callback_data="35"),
                InlineKeyboardButton('40', callback_data="40"),
                InlineKeyboardButton('45', callback_data="45"),
                InlineKeyboardButton('50', callback_data="50"),
                InlineKeyboardButton('55', callback_data="55"),
                InlineKeyboardButton('60', callback_data="60"),
            ],
            [InlineKeyboardButton('❌Отмена', callback_data="cancel")],
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )

def get_delay_minutes_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton('5', callback_data="5"),
                InlineKeyboardButton('10', callback_data="10"),
                InlineKeyboardButton('15', callback_data="15"),
                InlineKeyboardButton('20', callback_data="20"),
                InlineKeyboardButton('30', callback_data="30"),
                InlineKeyboardButton('45', callback_data="45"),
                InlineKeyboardButton('60', callback_data="60"),
            ],
            [InlineKeyboardButton('🕒 Custom Time', callback_data="my")],
            [InlineKeyboardButton('❌Cancel', callback_data="cancel")],
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ],
    )

def get_username_kb(lang='ru'):
    """כפתורים לשלב הזנת username"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_skip_username', lang), callback_data="skip_username")],
            [InlineKeyboardButton(t('btn_back', lang), callback_data="back")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )

def get_skip_back_cancel_kb(lang='ru'):
    """כפתורים לשלב הזנת username עם כפתורי חזרה וביטול"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_skip_username', lang), callback_data="skip_username")],
            [InlineKeyboardButton(t('btn_back', lang), callback_data="back")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
            [InlineKeyboardButton(t("btn_home", lang), callback_data="home")],
        ]
    )

def get_stock_management_kb(lang='ru'):
    """כפתורים לניהול מלאי"""
    from db.db import get_all_products
    
    products = get_all_products()
    
    inline_keyboard = [
        [InlineKeyboardButton(t('btn_add_product', lang), callback_data="add_product")],
        [InlineKeyboardButton(t('btn_view_all_products', lang), callback_data="list_products")],
    ]
    
    # Add products list
    if products:
        for product in products[:10]:  # Show first 10 products
            product_text = f"{product.get('name', '')[:20]} - {product.get('stock', 0)}"
            inline_keyboard.append([
                InlineKeyboardButton(product_text, callback_data=f"edit_{product.get('id')}")
            ])
    
    # Add navigation buttons
    inline_keyboard.append([
        InlineKeyboardButton(t("btn_back", lang), callback_data="back"),
        InlineKeyboardButton(t("btn_home", lang), callback_data="home")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def get_edit_product_kb_with_back(lang):
    """יצירת keyboard לבחירת פעולת עריכה עם כפתור חזור"""
    keyboard = [
        [InlineKeyboardButton(t("btn_edit_name", lang), callback_data="edit_name")],
        [InlineKeyboardButton(t("btn_edit_stock", lang), callback_data="edit_stock")],
        [InlineKeyboardButton(t("btn_edit_price", lang), callback_data="edit_price")],
        [InlineKeyboardButton(t("btn_delete", lang), callback_data="delete")],
        [InlineKeyboardButton(t("btn_back", lang), callback_data="back_to_product_list")]  # כפתור חדש
    ]
    return InlineKeyboardMarkup(keyboard)

def get_edit_product_actions_kb(lang='ru', product_id=0):
    """כפתורים לעריכת מוצר"""
    inline_keyboard = [
        [InlineKeyboardButton(t('btn_edit_name', lang), callback_data=f"edit_name_{product_id}")],
        [InlineKeyboardButton(t('btn_edit_stock', lang), callback_data=f"edit_stock_{product_id}")],
        [InlineKeyboardButton(t('btn_edit_price', lang), callback_data=f"edit_price_{product_id}")],
        [InlineKeyboardButton(t('btn_delete_product', lang), callback_data=f"delete_product_{product_id}")],
        [
            InlineKeyboardButton(t("btn_back", lang), callback_data="back"),
            InlineKeyboardButton(t("btn_home", lang), callback_data="home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def get_confirm_delete_kb(lang='ru', product_id=0):
    """כפתורים לאישור מחיקת מוצר"""
    inline_keyboard = [
        [InlineKeyboardButton(t('btn_confirm_delete', lang), callback_data=f"confirm_delete_{product_id}")],
        [InlineKeyboardButton(t('btn_cancel', lang), callback_data=f"cancel_delete_{product_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
