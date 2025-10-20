import logging, os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, Defaults
from config.config import *
from funcs.bot_funcs import *
from funcs.admin_funcs import *
from db.db import if_table
from config.translations import t, get_user_lang
from handlers.new_order_handler import NEW_ORDER_HANDLER
from handlers.edit_product_handler import EDIT_PRODUCT_HANDLER
from handlers.courier_choose_minutes import CHOOSE_MINUTES_HANDLER
from handlers.courier_write_minutes import WRITE_MINUTES_HANDLER
from handlers.courier_choose_delay import DELAY_MINUTES_HANDLER
from handlers.create_new_shablon import CREATE_NEW_TEMPLATE
from handlers.send_or_edit_template import SEND_OR_EDIT_TEMPLATE
from handlers.add_staff_handler import ADD_STAFF_HANDLER
from handlers.end_shift_handler import END_SHIFT_HANDLER
from handlers.edit_crude_handler import EDIT_CRUDE_HANDLER
from handlers.change_links_handler import CHANGE_LINK_HANDLER
from handlers.make_tg_session_handler import MAKE_TG_SESSION_HANDLER

def main() -> None:
    """Run the bot."""
    if_table()
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()
    # Health log on startup for Railway
    import logging, os
    logging.getLogger(__name__).setLevel(logging.INFO)
    logging.info("Bot starting...")
    logging.info("ENV set: %s", ','.join(sorted([k for k in os.environ.keys() if k in {
        'BOT_TOKEN','ADMIN_CHAT','ORDER_CHAT','API_ID','API_HASH','DB_NAME','DB_DIR','DB_PATH'
    }])))

    # Language Selection
    application.add_handler(CommandHandler("changelanguage", change_language))
    application.add_handler(CallbackQueryHandler(change_language, pattern="change_language"))
    application.add_handler(CallbackQueryHandler(set_language, pattern="set_lang_ru|set_lang_he"))

    # Главное меню
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(show_rest_from_last_day, pattern="rest"))
    application.add_handler(CallbackQueryHandler(show_menu_edit_crude_stock, pattern="crude_manage"))
    application.add_handler(CallbackQueryHandler(beginning, pattern="beginning"))
    application.add_handler(CallbackQueryHandler(msg_client, pattern="msg_client"))

    # templates
    application.add_handler(CallbackQueryHandler(show_templates, pattern="msg_*[0-9]"))

    # templates___end........

    application.add_handler(CallbackQueryHandler(notif_client, pattern="notif_.+"))

    application.add_handler(CallbackQueryHandler(order_ready, pattern="ready_*[0-9]"))

    application.add_handler(CallbackQueryHandler(confirm_stock_shift, pattern="confirm_stock_shift"))

    application.add_handler(CallbackQueryHandler(show_admin_action_kb, pattern="show_admin_menu"))

    # ADMIN HANDLERS
    application.add_handler(ADD_STAFF_HANDLER)

    application.add_handler(CallbackQueryHandler(del_roles, pattern="del_o|del_c|del_s"))
    application.add_handler(CallbackQueryHandler(delete_staff_user, pattern="del_*[0-9]"))
    application.add_handler(CallbackQueryHandler(show_week_report, pattern="week_report"))
    application.add_handler(CallbackQueryHandler(all_orders, pattern="all_orders"))
    application.add_handler(CallbackQueryHandler(filter_orders_by_param, pattern="fdate|fproduct|fclient|fstatus"))
    application.add_handler(CallbackQueryHandler(manage_roles, pattern="manage_roles"))
    application.add_handler(CallbackQueryHandler(show_security_menu, pattern="security_menu"))

    application.job_queue.run_daily(show_week_report, time=datetime.time(hour=12), days=(6,),)

    # Filter orders by date
    application.add_handler(MessageHandler(filters.Regex(r'^order:\d{2}\.\d{2}\.\d{4}:\d{2}\.\d{2}\.\d{4}$'), filter_orders_by_date))

    # Delete orders before date
    application.add_handler(MessageHandler(filters.Regex(r'^clean:\d{2}\.\d{2}\.\d{4}$'), erase_orders_before_date))
    
    # Filter orders by product
    application.add_handler(MessageHandler(filters.Regex(r'^order(\$[^\s]+)+$'), filter_orders_by_product))
    
    # Filter orders by client
    application.add_handler(MessageHandler(filters.Regex(r'^order@([A-Za-z0-9_]+|\d{10,15})$'), filter_orders_by_client))

    # Filter orders by status
    application.add_handler(CallbackQueryHandler(filter_orders_by_status, pattern="|".join((Status.completed.value,Status.active.value,Status.pending.value,Status.cancelled.value,Status.delay.value,))))
    application.add_handler(CallbackQueryHandler(fetch_orders_excel, pattern="orders_xl"))

    application.add_handler(CallbackQueryHandler(show_cleanup_tip, pattern="cleanup"))
    application.add_handler(CallbackQueryHandler(dump_choose_format, pattern="dump"))
    application.add_handler(CallbackQueryHandler(dump_database, pattern="json|xlsx"))

    application.add_handler(CallbackQueryHandler(quick_reports, pattern='quick_reports'))
    application.add_handler(CallbackQueryHandler(show_daily_profit_options, pattern='daily_profit'))
    application.add_handler(CallbackQueryHandler(daily_profit_report, pattern='profit_today|profit_yesterday'))
    application.add_handler(CallbackQueryHandler(report_by_product, pattern='report_by_product'))
    application.add_handler(CallbackQueryHandler(report_by_client, pattern='report_by_client'))
    application.add_handler(CallbackQueryHandler(report_by_price, pattern='report_by_price'))
    application.add_handler(CallbackQueryHandler(report_by_days, pattern='report_by_days'))


    application.add_handler(CallbackQueryHandler(manage_links_tip, pattern="links"))

    # Tg Sessions
    application.add_handler(CallbackQueryHandler(show_tg_sessions, pattern="show_tg_sessions"))
    application.add_handler(CallbackQueryHandler(show_session_action, pattern="sess_act_*[0-9]"))
    application.add_handler(CallbackQueryHandler(make_tg_session_as_worker, pattern="worker_*[0-9]"))
    application.add_handler(CallbackQueryHandler(delete_tg_session, pattern="del_sess_*[0-9]"))
    application.add_handler(CallbackQueryHandler(back_session_kb, pattern="back_session_kb"))


    # ADMIN HANDLERS ___END

    # application.add_handler(CallbackQueryHandler(approve_user, pattern=FuncEnums.APPROVE_USER.value))
    # application.add_handler(MessageHandler(filters.Regex(FuncEnums.USER_AGENT_REGEXP.value), handle_user_agent)) # ua@123456
    # application.job_queue.run_repeating(send_new_orders, interval=5, first=0)

    application.add_handler(NEW_ORDER_HANDLER)
    application.add_handler(EDIT_PRODUCT_HANDLER)
    application.add_handler(CHOOSE_MINUTES_HANDLER)
    application.add_handler(WRITE_MINUTES_HANDLER)
    application.add_handler(DELAY_MINUTES_HANDLER)
    application.add_handler(CREATE_NEW_TEMPLATE)
    application.add_handler(SEND_OR_EDIT_TEMPLATE)
    application.add_handler(END_SHIFT_HANDLER)
    application.add_handler(EDIT_CRUDE_HANDLER)
    application.add_handler(CHANGE_LINK_HANDLER)
    application.add_handler(MAKE_TG_SESSION_HANDLER)



    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    # logging
    logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.ERROR)
    main()