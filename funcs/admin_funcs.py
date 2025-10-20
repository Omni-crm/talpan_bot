import datetime, traceback
from sqlalchemy.exc import IntegrityError
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

    session = Session()

    if data == 'del_o':
        operators = session.query(User).filter(User.role==Role.OPERATOR).all()
        dikb = [[InlineKeyboardButton(f"@{o.username}|{o.firstname}", callback_data=f"del_{o.user_id}") for o in operators]]
    elif data == 'del_c':
        operators = session.query(User).filter(User.role==Role.RUNNER).all()
        dikb = [[InlineKeyboardButton(f"@{o.username}|{o.firstname}", callback_data=f"del_{o.user_id}") for o in operators]]
    elif data == 'del_s':
        operators = session.query(User).filter(User.role==Role.STOCKMAN).all()
        dikb = [[InlineKeyboardButton(f"@{o.username}|{o.firstname}", callback_data=f"del_{o.user_id}") for o in operators]]

    replkbmkp = InlineKeyboardMarkup(inline_keyboard=dikb)
    await update.effective_message.edit_text(t('click_to_remove', lang), reply_markup=replkbmkp, parse_mode=ParseMode.HTML)
    
    session.close()


async def delete_staff_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    lang = get_user_lang(update.effective_user.id)

    user_id = int(update.callback_query.data.replace('del_', ''))

    session = Session()

    user = session.query(User).filter(User.user_id==user_id).first()

    if user:
        role = user.role.value

        user.role = Role.GUEST
        session.commit()
        await update.effective_message.edit_text(t('staff_removed', lang).format(user.firstname, user.username, role), reply_markup=get_admin_action_kb(lang), parse_mode=ParseMode.HTML)

    session.close()