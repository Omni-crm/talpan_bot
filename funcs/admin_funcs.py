import datetime, traceback
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, Job, ExtBot
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from config.config import *
from config.kb import *
from config.translations import t, get_user_lang
from db.db import *
from funcs.utils import *

@is_admin
async def del_roles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    data = update.callback_query.data

    # Using Supabase only
    from db.db import db_client
    
    if data == 'del_o':
        operators_data = db_client.select('users', {'role': 'operator'})
        dikb = [[InlineKeyboardButton(f"@{u.get('username')}|{u.get('firstname')}", callback_data=f"del_{u.get('user_id')}") for u in operators_data]]
    elif data == 'del_c':
        # CRITICAL FIX: Use 'courier' (Role.RUNNER.value) not 'runner'!
        operators_data = db_client.select('users', {'role': 'courier'})
        dikb = [[InlineKeyboardButton(f"@{u.get('username')}|{u.get('firstname')}", callback_data=f"del_{u.get('user_id')}") for u in operators_data]]
    elif data == 'del_s':
        operators_data = db_client.select('users', {'role': 'stockman'})
        dikb = [[InlineKeyboardButton(f"@{u.get('username')}|{u.get('firstname')}", callback_data=f"del_{u.get('user_id')}") for u in operators_data]]

    replkbmkp = InlineKeyboardMarkup(inline_keyboard=dikb)
    await update.effective_message.edit_text(t('click_to_remove', lang), reply_markup=replkbmkp, parse_mode=ParseMode.HTML)


async def delete_staff_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    user_id = int(update.callback_query.data.replace('del_', ''))

    # Using Supabase only
    from db.db import db_client
    
    users = db_client.select('users', {'user_id': user_id})
    
    if users:
        user = users[0]
        role = user['role']

        db_client.update('users', {'role': 'guest'}, {'user_id': user_id})
        await update.effective_message.edit_text(t('staff_removed', lang).format(user['firstname'], user['username'], role), reply_markup=get_admin_action_kb(lang), parse_mode=ParseMode.HTML)