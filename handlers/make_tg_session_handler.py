from telegram.ext import CallbackQueryHandler, TypeHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from pyrogram import Client
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.error import BadRequest
from pyrogram.errors import BadRequest, SessionPasswordNeeded
from pyrogram.types import User as PyrogramUser
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from db.db import *
from config.kb import TWO_STEP_ASK_KB, DIGITS_KB, get_cancel_kb
from config.translations import t, get_user_lang


class AuthStates:
    handle_acc_phone = 0
    fetch_actions = 1
    handle_password = 2
    process_number_1 = 3
    process_number_2 = 4
    process_number_3 = 5
    process_number_4 = 6
    process_number_5 = 7

async def start_sessing_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """STARTING CREATION OF A SESSION VIA THE BOT BUTTONS."""
    await update.callback_query.answer()
    inline_keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    start_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="Введите номер телефона аккаунта (с кодом страны):", reply_markup=reply_markup)
    context.user_data["auth_data"] = {}
    context.user_data["auth_data"]["start_msg_id"] = start_msg.id

    return AuthStates.handle_acc_phone

async def handle_acc_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    phone_number = update.message.text
    
    context.user_data["auth_data"]["phone_number"] = phone_number

    msg = await context.bot.send_message(
        text=f"На аккаунте стоит пароль ? (нужно для создания сессии):",
        chat_id=update.effective_chat.id,
        reply_markup=TWO_STEP_ASK_KB
    )

    context.user_data["auth_data"]["message_id"] = msg.id

    return AuthStates.fetch_actions

async def fetch_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer("Processing.")
    inline_keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    if update.callback_query.data == "two_step_yes":
        await context.bot.edit_message_text(
            text="Send two-step password in chat:",
            chat_id=update.effective_chat.id,
            message_id=context.user_data["auth_data"]["message_id"],
            reply_markup=reply_markup
        )

        return AuthStates.handle_password
    else:
        app = Client(context.user_data["auth_data"]["phone_number"], api_id=TgSession.get_api_id(), api_hash=TgSession.get_api_hash(), in_memory=True)
        context.user_data["auth_data"]["app"] = app

        try:
            await app.connect()
            sent_code = await app.send_code(phone_number=context.user_data["auth_data"]["phone_number"])
        except Exception as e:
            print(e)
            await context.bot.edit_message_text(
                text=f"[ERROR] Make sure that all data is correct. The text of the error: {e}",
                chat_id=update.effective_chat.id,
                message_id=context.user_data["auth_data"]["message_id"]
            )
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data["auth_data"]["start_msg_id"]
            )
            del context.user_data["auth_data"]
            try:
                await app.disconnect()
            except: pass

            return ConversationHandler.END

        context.user_data["auth_data"]["phone_code_hash"] = sent_code.phone_code_hash

        await context.bot.edit_message_text(
            text=f"Now type the authorization code:",
            chat_id=update.effective_chat.id,
            message_id=context.user_data["auth_data"]["message_id"],
            reply_markup=DIGITS_KB
        )

        return AuthStates.process_number_1

async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    password = update.message.text

    context.user_data["auth_data"]["password"] = password

    app = Client(context.user_data["auth_data"]["phone_number"], api_id=TgSession.get_api_id(), api_hash=TgSession.get_api_hash(), password=password, in_memory=True)
    context.user_data["auth_data"]["app"] = app

    try:
        await app.connect()
        sent_code = await app.send_code(phone_number=context.user_data["auth_data"]["phone_number"])
    except Exception as e:
        print(e)
        await context.bot.edit_message_text(
            text=f"[ERROR] Make sure that all data is correct. The text of the error: {e}",
            chat_id=update.effective_chat.id,
            message_id=context.user_data["auth_data"]["message_id"]
        )
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=context.user_data["auth_data"]["start_msg_id"]
        )

        del context.user_data["auth_data"]
        try:
            await app.disconnect()
        except: pass

        return ConversationHandler.END

    context.user_data["auth_data"]["phone_code_hash"] = sent_code.phone_code_hash

    await context.bot.edit_message_text(
        text=f"Now type the authorization code:",
        chat_id=update.effective_chat.id,
        message_id=context.user_data["auth_data"]["message_id"],
        reply_markup=DIGITS_KB
    )

    return AuthStates.process_number_1

async def process_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    phone_code = update.callback_query.data
    user = update.callback_query.from_user

    if isinstance(context.user_data["auth_data"].get('phone_code'), str):
        context.user_data["auth_data"]['phone_code'] += phone_code
    else:
        context.user_data["auth_data"]['phone_code'] = phone_code
    await update.callback_query.answer(context.user_data['auth_data']['phone_code'])

    if len(context.user_data["auth_data"]['phone_code']) < 5:
        return 2 + len(context.user_data["auth_data"]['phone_code'])

    # Now you can do any logic with your number via `context.user_data['number']`
    app: Client = context.user_data["auth_data"]["app"]

    try:
        session_user: PyrogramUser = await app.sign_in(
            context.user_data["auth_data"]["phone_number"],
            context.user_data["auth_data"]["phone_code_hash"],
            context.user_data["auth_data"]["phone_code"]
        )
    except BadRequest as e:
        await context.bot.edit_message_text(
            text=f"[ERROR] Some error happened. Make sure that all data is correct. The text of the error: {e}",
            chat_id=update.effective_chat.id,
            message_id=context.user_data["auth_data"]["message_id"]
        )
        del context.user_data["auth_data"]
        await app.disconnect()

        return ConversationHandler.END
    except SessionPasswordNeeded:
        await context.bot.edit_message_text(
            text=f"[ERROR] You didn't type two-step password, but it is required.",
            chat_id=update.effective_chat.id,
            message_id=context.user_data["auth_data"]["message_id"]
        )
        del context.user_data["auth_data"]
        try:
            await app.disconnect()
        except: pass

        return ConversationHandler.END
    except Exception as e:
        print(e)
        await context.bot.edit_message_text(
            text=f"[ERROR] Make sure that all data is correct. The text of the error: {e}",
            chat_id=update.effective_chat.id,
            message_id=context.user_data["auth_data"]["message_id"]
        )
        del context.user_data["auth_data"]
        try:
            await app.disconnect()
        except: pass
        return ConversationHandler.END

    if not isinstance(session_user, PyrogramUser):
        await context.bot.edit_message_text(
            text=f"[ERROR] The account is not registered yet.",
            chat_id=update.effective_chat.id,
            message_id=context.user_data["auth_data"]["message_id"]
        )
        del context.user_data["auth_data"]
        await app.disconnect()

        return ConversationHandler.END

    s = await app.export_session_string()
    await app.disconnect()
    # Saves to db.
    session = Session()

    new_string = TgSession(
        owner_id=user.id,
        string=s,
        name=session_user.first_name if not session_user.last_name else (session_user.first_name + ' ' + session_user.last_name),
        username=session_user.username)

    worker = session.query(TgSession).filter_by(is_worker=True).first()

    if not worker:
        new_string.is_worker = True

    session.add(new_string)
    session.commit()

    session.close()

    await context.bot.edit_message_text(
        text=f"Success! Session of {session_user.first_name} {session_user.last_name} @{session_user.username} was created.",
        chat_id=update.effective_chat.id,
        message_id=context.user_data["auth_data"]["message_id"]
    )

    await context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=context.user_data["auth_data"]["start_msg_id"]
    )

    del context.user_data["auth_data"]

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Cancelling.")
    await update.callback_query.answer("Operation cancelled.")

    if context.user_data["auth_data"].get("message_id"):
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            text="Operation cancelled.",
            message_id=context.user_data["auth_data"]["message_id"]
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Operation cancelled."
        )

    await context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=context.user_data["auth_data"]["start_msg_id"]
    )

    del context.user_data["auth_data"]

    return ConversationHandler.END

async def timeout_reached(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data["auth_data"].get("message_id"):
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            text="[ERROR] Bot Waiting Timeout.",
            message_id=context.user_data["auth_data"]["message_id"]
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="[ERROR] Bot Waiting Timeout."
        )

    if context.user_data["auth_data"].get("start_msg_id"):
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=context.user_data["auth_data"]["start_msg_id"]
        )

    del context.user_data["auth_data"]

states = {
    AuthStates.handle_acc_phone: [MessageHandler(filters.Regex("^\d+$"), handle_acc_phone)],
    AuthStates.fetch_actions: [CallbackQueryHandler(fetch_actions, pattern='two_step_yes|two_step_no')],
    AuthStates.handle_password: [MessageHandler(filters.Regex(".*"), handle_password)],
    AuthStates.process_number_1: [CallbackQueryHandler(process_number, pattern=r'^\d$')],
    AuthStates.process_number_2: [CallbackQueryHandler(process_number, pattern=r'^\d$')],
    AuthStates.process_number_3: [CallbackQueryHandler(process_number, pattern=r'^\d$')],
    AuthStates.process_number_4: [CallbackQueryHandler(process_number, pattern=r'^\d$')],
    AuthStates.process_number_5: [CallbackQueryHandler(process_number, pattern=r'^\d$')],
    ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_reached)]
}

MAKE_TG_SESSION_HANDLER = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_sessing_creation, pattern='make_tg_session')],
    states=states,
    fallbacks=[CallbackQueryHandler(cancel, pattern='cancel')],
    conversation_timeout=120
)