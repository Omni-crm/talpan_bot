import logging, os, signal, sys
import telegram
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, Defaults, ContextTypes
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
from handlers.new_order_handler import collect_username
from handlers.manage_stock_handler import MANAGE_STOCK_HANDLER, manage_stock, list_products, edit_product, delete_product_confirm, delete_product_execute
from db.db import initialize_default_settings

# Global variable to store the application
bot_application = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logging.info("🛑 Received shutdown signal, stopping gracefully...")
    if bot_application:
        bot_application.stop()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def main() -> None:
    """Run the bot."""
    global bot_application
    
    # Using Supabase - tables managed in cloud
    print("✅ Using Supabase - tables managed in cloud")
    
    # Initialize bot settings if needed
    initialize_default_settings()
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()
    bot_application = application  # Store globally for signal handler
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

    # Main menu
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(show_rest_from_last_day, pattern="rest"))
    application.add_handler(CallbackQueryHandler(beginning, pattern="beginning"))
    application.add_handler(CallbackQueryHandler(msg_client, pattern="msg_client"))
    application.add_handler(CallbackQueryHandler(manage_stock, pattern="manage_stock"))
    application.add_handler(CallbackQueryHandler(list_products, pattern="list_products"))
    application.add_handler(CallbackQueryHandler(edit_product, pattern="edit_*[0-9]"))
    application.add_handler(CallbackQueryHandler(delete_product_confirm, pattern="delete_product_*[0-9]"))
    application.add_handler(CallbackQueryHandler(delete_product_execute, pattern="confirm_delete_*[0-9]"))

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
    
    # Handler ניווט
    application.add_handler(CallbackQueryHandler(handle_navigation, pattern="back|home"))
    application.add_handler(CallbackQueryHandler(show_staff_list, pattern="view_staff"))
    application.add_handler(CallbackQueryHandler(handle_confirmation, pattern="confirm_|cancel_"))

    # Schedule weekly report (only if job_queue is available)
    if application.job_queue:
        application.job_queue.run_daily(show_week_report, time=datetime.time(hour=12), days=(6,),)

    # CONVERSATION HANDLERS - MUST BE BEFORE MESSAGE HANDLERS!
    application.add_handler(MANAGE_STOCK_HANDLER)
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
    # Excel export removed - now using text messages

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



    # Error handler for conflicts
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors gracefully, especially conflicts."""
        error = context.error
        if isinstance(error, telegram.error.Conflict):
            logging.warning("⚠️ Conflict detected - another bot instance may be running")
        else:
            logging.error(f"Update {update} caused error {error}")
    
    application.add_error_handler(error_handler)
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    # logging
    logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.ERROR)
    
    print("🚀 Starting Courier Bot...")
    print("📊 Healthcheck: Bot is running")
    print("🔧 Build: Updated dependencies")
    
    # Initialize database settings (chat IDs, user lists)
    try:
        from db.db import initialize_default_settings
        initialize_default_settings()
        print("✅ Database tables and settings initialized")
    except Exception as e:
        print(f"⚠️ Warning: Could not initialize database settings: {e}")
    
    main()