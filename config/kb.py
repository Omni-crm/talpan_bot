from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from enum import Enum
from config.config import *
from config.translations import t, get_user_lang
from db.db import *

class Notifications(Enum):
    NOTIF_CLIENT_ORDER_ACTIVE = "Курьер в пути, пожалуйста, спуститесь"


async def get_all_active_orders_to_msg_kb():
    session = Session()

    orders = session.query(Order).filter(Order.status.in_([Status.active, Status.delay, Status.pending])).all()

    if orders:
        mrkp = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(f"#{order.id}|{order.client_username}", callback_data=f"msg_{order.id}")] for order in orders]
        )
        session.close()

        return mrkp


def get_shift_end_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_end_shift', lang), callback_data="ending")],
        ]
    )

SHIFT_END_KB = get_shift_end_kb('ru')

async def build_start_menu(user_id):
    session = Session()
    user = session.query(User).filter(User.user_id==user_id).first()
    shift = session.query(Shift).filter(Shift.status==ShiftStatus.opened).first()
    
    # Get user's language
    lang = user.lang if user and user.lang else 'ru'
    
    inline_keyboard=[
        [InlineKeyboardButton(t('btn_new_order', lang), callback_data="new")],
        [InlineKeyboardButton(t('btn_start_shift', lang), callback_data="beginning")],
        [InlineKeyboardButton(t('btn_current_stock', lang), callback_data="rest")],
        [InlineKeyboardButton(t('btn_msg_client', lang), callback_data="msg_client")],
        [InlineKeyboardButton(t('btn_admin', lang), callback_data="show_admin_menu")],
        [InlineKeyboardButton(t('btn_crude_manage', lang), callback_data="crude_manage")],
        [InlineKeyboardButton(t('btn_change_language', lang), callback_data="change_language")],
    ]

    if shift:
        inline_keyboard[1] = [InlineKeyboardButton(t('btn_end_shift', lang), callback_data="end_shift")]

    if user and user.role != Role.GUEST:
        if user.role == Role.ADMIN:
            inline_keyboard = inline_keyboard[:]
        elif user.role == Role.OPERATOR:
            inline_keyboard = inline_keyboard[:-2]
        elif user.role == Role.STOCKMAN:
            inline_keyboard = inline_keyboard[-1:]
        elif user.role == Role.RUNNER:
            inline_keyboard=[
                [InlineKeyboardButton(t('btn_couriers_group', lang), url=f"https://t.me/{links.ORDER_CHAT.replace('@', '')}")],
            ]

        START_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    else:
        START_KEYBOARD = None

    session.close()

    return START_KEYBOARD
    

# Keyboards שדורשים שפה - יהפכו לפונקציות
def get_cancel_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
        ],
    )

def get_back_cancel_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_back', lang), callback_data="back")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
        ],
    )

def get_add_more_or_confirm_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_back', lang), callback_data="back")],
            [InlineKeyboardButton(t('btn_confirm_order', lang), callback_data="to_confirm")],
            [InlineKeyboardButton(t('btn_add', lang), callback_data="add")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
        ],
    )

# Backward compatibility - ישארו כקיצור דרך
CANCEL_KB = get_cancel_kb('ru')
BACK_CANCEL_KB = get_back_cancel_kb('ru')
ADD_MORE_PRODUCTS_OR_CONFIRM_KB = get_add_more_or_confirm_kb('ru')

def get_products_markup(user):
    session = Session()
    products = session.query(Product).all()

    inline_keyboard = []
    delimiter = []
    for product in products:
        print(len(delimiter))
        if len(delimiter) and len(delimiter) % 3 == 0:
            inline_keyboard.append(delimiter)
            delimiter = []
            delimiter.append(InlineKeyboardButton(f"{product.name[:12]} ({product.stock})", callback_data=str(product.id)))
        else:
            delimiter.append(InlineKeyboardButton(f"{product.name[:12]} ({product.stock})", callback_data=str(product.id)))
    
    if delimiter:
        inline_keyboard.append(delimiter)
        delimiter = []

    # += [InlineKeyboardButton('⬅️Назад', callback_data="back")], 
    inline_keyboard += [[InlineKeyboardButton('❌Отмена', callback_data="cancel")]]

    # if user.id in ADMINS:
    inline_keyboard = [[InlineKeyboardButton('⏬Создать', callback_data="create")]] + inline_keyboard
    inline_keyboard = [[InlineKeyboardButton('⬅️Назад', callback_data="back")]] + inline_keyboard

    reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    return reply_markup

def get_products_markup_left_edit_stock():
    session = Session()
    products = session.query(Product).all()

    inline_keyboard = []
    delimiter = []
    for product in products:
        print(len(delimiter))
        if len(delimiter) and len(delimiter) % 3 == 0:
            inline_keyboard.append(delimiter)
            delimiter = []
            delimiter.append(InlineKeyboardButton(product.name[:12], callback_data=f"edit_{product.id}"))
        else:
            delimiter.append(InlineKeyboardButton(f"{product.name[:6]} ({product.stock})", callback_data=f"edit_{product.id}"))

    if delimiter:
        inline_keyboard.append(delimiter)
        delimiter = []

    reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    return reply_markup


def get_products_markup_left_edit_stock_crude():
    session = Session()
    products = session.query(Product).all()

    inline_keyboard = []
    delimiter = []
    for product in products:
        print(len(delimiter))
        if len(delimiter) and len(delimiter) % 3 == 0:
            inline_keyboard.append(delimiter)
            delimiter = []
            delimiter.append(InlineKeyboardButton(product.name[:12], callback_data=f"edit_crude_{product.id}"))
        else:
            delimiter.append(InlineKeyboardButton(f"{product.name[:6]} ({product.crude}) ({product.stock})", callback_data=f"edit_crude_{product.id}"))

    if delimiter:
        inline_keyboard.append(delimiter)
        delimiter = []

    reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    return reply_markup


def get_confirm_order_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_confirm', lang), callback_data="confirm")],
            [InlineKeyboardButton(t('btn_back', lang), callback_data="back")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
        ],
    )

def get_edit_product_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_edit_stock', lang), callback_data="edit_stock")],
            [InlineKeyboardButton(t('btn_delete', lang), callback_data="delete")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
        ],
    )

def get_edit_product_crude_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_edit_crude', lang), callback_data="edit_crude")],
            [InlineKeyboardButton(t('btn_edit_stock', lang), callback_data="edit_stock")],
            [InlineKeyboardButton(t('btn_delete', lang), callback_data="delete")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
        ],
    )

# Backward compatibility
CONFIRM_ORDER_KB = get_confirm_order_kb('ru')
EDIT_PRODUCT_KB = get_edit_product_kb('ru')
EDIT_PRODUCT_W_CRUDE_KB = get_edit_product_crude_kb('ru')

SELECT_PRICE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton('250', callback_data="250"),
            InlineKeyboardButton('350', callback_data="350"),
            InlineKeyboardButton('400', callback_data="400"),
            InlineKeyboardButton('450', callback_data="450"),
            InlineKeyboardButton('500', callback_data="500"),
            InlineKeyboardButton('550', callback_data="550"),
        ],
        [InlineKeyboardButton('⬅️Назад', callback_data="back")],
        [InlineKeyboardButton('❌Отмена', callback_data="cancel")],
    ],
)

SELECT_QUANTITY_KB = InlineKeyboardMarkup(
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
        [InlineKeyboardButton('⬅️Назад', callback_data="back")],
        [InlineKeyboardButton('❌Отмена', callback_data="cancel")],
    ],
)


def show_tg_session_action_kb(sess_id: str):
    SESS_ACT_KB = InlineKeyboardMarkup([
        [InlineKeyboardButton('⬅️ Назад', callback_data='back_session_kb')],
        [InlineKeyboardButton('✅ Сделать рабочим', callback_data=f'worker_{sess_id}')],
        [InlineKeyboardButton('❌ Удалить', callback_data=f'del_sess_{sess_id}')],
    ])

    return SESS_ACT_KB

def create_tg_sessions_kb():
    session_db = Session()

    tgsessions = session_db.query(TgSession).filter_by(is_worker=False).all()
    worker_session = session_db.query(TgSession).filter_by(is_worker=True).first()

    if not tgsessions and not worker_session:
        session_db.close()
        inline_keyboard = [[InlineKeyboardButton('➕ Добавить аккаунт', callback_data='make_tg_session')]]

        return InlineKeyboardMarkup(inline_keyboard=inline_keyboard,)

    inline_keyboard = [[InlineKeyboardButton(f'{tgsess.name[:10]} {tgsess.username[:10]}', callback_data=f'sess_{tgsess.id}')] for tgsess in tgsessions]

    if worker_session:
        inline_keyboard = [[InlineKeyboardButton(f'✅ {worker_session.name[:10]} {worker_session.username[:10]}', callback_data=f'sess_{worker_session.id}')]] + inline_keyboard

    inline_keyboard = [[InlineKeyboardButton('➕ Добавить', callback_data='make_tg_session')]] + inline_keyboard

    session_db.close()

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard,)


TWO_STEP_ASK_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton('Yes', callback_data='two_step_yes'), InlineKeyboardButton('No', callback_data='two_step_no')],
    [InlineKeyboardButton("Cancel", callback_data="cancel")]
])


DIGITS_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton('1', callback_data='1'), InlineKeyboardButton('2', callback_data='2'), InlineKeyboardButton('3', callback_data='3')],
    [InlineKeyboardButton('4', callback_data='4'), InlineKeyboardButton('5', callback_data='5'), InlineKeyboardButton('6', callback_data='6')],
    [InlineKeyboardButton('7', callback_data='7'), InlineKeyboardButton('8', callback_data='8'), InlineKeyboardButton('9', callback_data='9')],
    [InlineKeyboardButton('0', callback_data='0'), InlineKeyboardButton('cancel', callback_data='cancel')]
])


async def form_courier_action_kb(order_id: int, lang: str = 'ru'):
    COURIER_ACTION_KB = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_choose_minutes', lang), callback_data=f"choose_min_{order_id}")],
            [InlineKeyboardButton(t('btn_write_minutes', lang), callback_data=f"write_min_{order_id}")],
            [InlineKeyboardButton(t('btn_delay', lang), callback_data=f"delay_min_{order_id}")],
            [InlineKeyboardButton(t('btn_delivered', lang), callback_data=f"ready_{order_id}")],
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
        ],
    )

    return OPERATOR_ACTION_KB

def get_operator_shift_start_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("confirm_stock", lang), callback_data="confirm_stock_shift")],
            [InlineKeyboardButton(t("manual_edit", lang), callback_data="rest")],
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
        ]
    )


FILTER_ORDERS_BY_STATUS_KB = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(status, callback_data=status)] for status in (Status.completed.value,Status.active.value,Status.pending.value,Status.cancelled.value,Status.delay.value,)]
)


def get_fetch_excel_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_export_excel", lang), callback_data="orders_xl")],
        ]
    )

ORDERS_FILTER_MENU_KB = get_orders_filter_kb('ru')
FETCH_EXCEL_ORDERS = get_fetch_excel_kb('ru')


def get_security_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_manage_links", lang), callback_data="links")],
            [InlineKeyboardButton(t("btn_cleanup_old_data", lang), callback_data="cleanup")],
            [InlineKeyboardButton(t("btn_backup_db", lang), callback_data="dump")],
        ]
    )


def get_db_format_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_excel", lang), callback_data="xlsx")],
            [InlineKeyboardButton(t("btn_json", lang), callback_data="json")],
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
            [InlineKeyboardButton(t("report_by_days", lang), callback_data='report_by_days')]
        ]
    )

# Backward compatibility
QUICK_REPORTS_KB = get_quick_reports_kb('ru')


def get_change_links_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_change_admin_link", lang), callback_data="change_admin_group_link")],
            [InlineKeyboardButton(t("btn_change_courier_link", lang), callback_data="change_courier_group_link")],
        ]
    )

CHANGE_GROUPS_LINK_KB = get_change_links_kb('ru')


def get_manage_roles_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t("btn_add_operator", lang), callback_data="add_o"), InlineKeyboardButton(t("btn_remove_operator", lang), callback_data="del_o")],
            [InlineKeyboardButton(t("btn_add_courier", lang), callback_data="add_c"), InlineKeyboardButton(t("btn_remove_courier", lang), callback_data="del_c")],
            [InlineKeyboardButton(t("btn_add_stockman", lang), callback_data="add_s"), InlineKeyboardButton(t("btn_remove_stockman", lang), callback_data="del_s")],
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
            [InlineKeyboardButton(t("btn_security", lang), callback_data="security_menu")],
        ]
    )

MANAGE_ROLES_KB = get_manage_roles_kb('ru')
ADMIN_ACTION_KB = get_admin_action_kb('ru')

async def form_operator_templates_kb(order: Order, lang: str = 'ru'):
    session = Session()
    templates = session.query(Template).all()

    inline_keyboard=[
        [InlineKeyboardButton(t('btn_add_template', lang), callback_data="new_shab")],
    ]

    for template in templates:
        inline_keyboard.append(
            [InlineKeyboardButton(f'{template.id}. {template.name}', callback_data=f"shab_{template.id}_{order.id}")]
        )

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
        ]
    )

def get_actions_template_kb(lang='ru'):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(t('btn_send_to_client', lang), callback_data="send")],
            [InlineKeyboardButton(t('btn_edit_template', lang), callback_data="edit")],
            [InlineKeyboardButton(t('btn_delete_template', lang), callback_data="delete")],
            [InlineKeyboardButton(t('btn_cancel', lang), callback_data="cancel")],
        ]
    )

EDIT_TEMPLATE_KB = get_edit_template_kb('ru')
ACTIONS_TEMPLATE_KB = get_actions_template_kb('ru')

COURIER_MINUTES_KB = InlineKeyboardMarkup(
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
    ],
)

DELAY_MINUTES_KB = InlineKeyboardMarkup(
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
        [InlineKeyboardButton('🕒 Свое время', callback_data="my")],
        [InlineKeyboardButton('❌Отмена', callback_data="cancel")],
    ],
)
