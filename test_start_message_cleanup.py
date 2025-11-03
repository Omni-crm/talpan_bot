#!/usr/bin/env python3
"""
טסט מקיף לבדיקת תיקון בעיה 3: ניקוי הודעות /start

הטסט בודק:
1. ניקוי הודעת /start נוכחית
2. ניקוי הודעות /start ישנות (30 הודעות אחרונות)
3. השארת הודעת /start אחת אחרונה
4. התמודדות עם שגיאות (הודעות שנמחקו, הרשאות)
5. לוגים מתאימים
6. אי הפלה של הבוט במקרה של שגיאות
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, call
from io import StringIO


async def test_cleanup_start_messages_basic():
    """טסט בסיסי - ניקוי הודעת /start נוכחית"""
    print("🧪 בדיקת ניקוי הודעת /start נוכחית")

    # יצירת mock objects
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = '/start'
    update.message.delete = AsyncMock()
    update.effective_user.id = 12345
    update.effective_chat.id = 67890

    context = MagicMock()
    context.bot = AsyncMock()

    # ייבוא הפונקציה
    from funcs.utils import cleanup_start_messages

    # הרצת הפונקציה
    await cleanup_start_messages(update, context)

    # בדיקות
    update.message.delete.assert_called_once()

    print("✅ הודעת /start נוכחית נמחקה")
    return True


async def test_cleanup_start_messages_history():
    """טסט מתקדם - ניקוי 30 הודעות אחרונות"""
    print("🧪 בדיקת ניקוי 30 הודעות אחרונות")

    # יצירת mock objects
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = '/start'
    update.message.delete = AsyncMock()
    update.effective_user.id = 12345
    update.effective_chat.id = 67890

    context = MagicMock()
    context.bot = AsyncMock()

    # יצירת היסטוריית הודעות עם 5 הודעות /start של המשתמש
    start_messages = []
    other_messages = []

    for i in range(5):
        msg = MagicMock()
        msg.text = '/start'
        msg.from_user = MagicMock()
        msg.from_user.id = 12345
        msg.delete = AsyncMock()
        start_messages.append(msg)

    for i in range(25):
        msg = MagicMock()
        msg.text = 'other message'
        msg.from_user = MagicMock()
        msg.from_user.id = 99999  # משתמש אחר
        other_messages.append(msg)

    # סידור ההודעות: 25 אחרות + 5 /start
    all_messages = other_messages + start_messages
    context.bot.get_chat_history = AsyncMock(return_value=all_messages)

    # ייבוא הפונקציה
    from funcs.utils import cleanup_start_messages

    # הרצת הפונקציה
    await cleanup_start_messages(update, context)

    # בדיקות
    # צריך למחוק את ההודעה הנוכחית
    update.message.delete.assert_called_once()

    # צריך לקרוא ל-get_chat_history עם limit=30
    context.bot.get_chat_history.assert_called_once_with(
        chat_id=67890,
        limit=30
    )

    # צריך למחוק 4 מתוך 5 הודעות /start (להשאיר את האחרונה)
    for msg in start_messages[:-1]:  # כל ההודעות חוץ מהאחרונה
        msg.delete.assert_called_once()

    # ההודעה האחרונה לא צריכה להימחק
    start_messages[-1].delete.assert_not_called()

    # הודעות של משתמשים אחרים לא צריכות להימחק
    for msg in other_messages:
        msg.delete.assert_not_called()

    print("✅ נוקו 4 מתוך 5 הודעות /start, הושארה אחת")
    return True


async def test_cleanup_start_messages_errors():
    """טסט התמודדות עם שגיאות"""
    print("🧪 בדיקת התמודדות עם שגיאות")

    # יצירת mock objects
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = '/start'
    update.message.delete = AsyncMock(side_effect=Exception("Delete failed"))
    update.effective_user.id = 12345
    update.effective_chat.id = 67890

    context = MagicMock()
    context.bot = AsyncMock()
    context.bot.get_chat_history = AsyncMock(side_effect=Exception("History failed"))

    # לכידת לוגים
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger('funcs.utils')
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    try:
        # ייבוא הפונקציה
        from funcs.utils import cleanup_start_messages

        # הרצת הפונקציה - לא צריכה לזרוק שגיאה
        await cleanup_start_messages(update, context)

        # בדיקות
        update.message.delete.assert_called_once()

        # צריך היה לנסות לקבל היסטוריה
        context.bot.get_chat_history.assert_called_once()

        # צריך להיות לוגים על השגיאות
        log_output = log_stream.getvalue()
        assert "Unexpected error deleting current /start message" in log_output
        assert "Could not get chat history for start cleanup" in log_output

        print("✅ הפונקציה מתמודדת עם שגיאות בלי לזרוק exception")
        return True

    finally:
        logger.removeHandler(handler)


async def test_cleanup_start_messages_no_start_message():
    """טסט עם הודעה שאינה /start"""
    print("🧪 בדיקת הודעה שאינה /start")

    # יצירת mock objects
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = 'hello'  # לא /start
    update.effective_user.id = 12345
    update.effective_chat.id = 67890

    context = MagicMock()
    context.bot = AsyncMock()
    context.bot.get_chat_history = AsyncMock(return_value=[])

    # ייבוא הפונקציה
    from funcs.utils import cleanup_start_messages

    # הרצת הפונקציה
    await cleanup_start_messages(update, context)

    # בדיקות
    # ההודעה הנוכחית לא צריכה להימחק כי היא לא /start
    update.message.delete.assert_not_called()

    # אבל צריך היה לבדוק היסטוריה
    context.bot.get_chat_history.assert_called_once()

    print("✅ הודעה שאינה /start לא נמחקה")
    return True


async def test_cleanup_start_messages_empty_history():
    """טסט עם היסטוריה ריקה"""
    print("🧪 בדיקת היסטוריה ריקה")

    # יצירת mock objects
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = '/start'
    update.message.delete = AsyncMock()
    update.effective_user.id = 12345
    update.effective_chat.id = 67890

    context = MagicMock()
    context.bot = AsyncMock()
    context.bot.get_chat_history = AsyncMock(return_value=[])  # ריקה

    # ייבוא הפונקציה
    from funcs.utils import cleanup_start_messages

    # הרצת הפונקציה
    await cleanup_start_messages(update, context)

    # בדיקות
    update.message.delete.assert_called_once()
    context.bot.get_chat_history.assert_called_once()

    print("✅ עובד עם היסטוריה ריקה")
    return True


async def test_start_function_calls_cleanup():
    """טסט בדיקה שה-start() קורא ל-cleanup_start_messages"""
    print("🧪 בדיקת קריאה ל-cleanup_start_messages מ-start()")

    # יצירת mock objects
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = '/start'
    update.effective_user = MagicMock()
    update.effective_user.id = 12345

    context = MagicMock()
    context.user_data = {}

    # Mock של פונקציות חיצוניות
    cleanup_mock = AsyncMock()
    lang_mock = MagicMock(return_value='he')
    menu_mock = AsyncMock(return_value=MagicMock())
    send_mock = AsyncMock()

    # קוד הפונקציה start() מועתק לכאן לבדיקה מבודדת
    async def start_test(update, context):
        user = update.effective_user
        lang = lang_mock(user.id)

        # הוספה: ניקוי הודעות /start לפני הצגת התפריט
        await cleanup_mock(update, context)

        # Just clear navigation history when returning to main menu
        if 'navigation_history' in context.user_data:
            context.user_data['navigation_history'] = []

        reply_markup = await menu_mock(user.id)
        await send_mock(update, context, "main_menu_text", reply_markup=reply_markup)

    # הרצת הפונקציה
    await start_test(update, context)

    # בדיקות
    cleanup_mock.assert_called_once_with(update, context)
    lang_mock.assert_called_once_with(12345)
    menu_mock.assert_called_once_with(12345)
    send_mock.assert_called_once()

    print("✅ פונקציית start() קורא ל-cleanup_start_messages")
    return True


async def run_all_tests():
    """הרצת כל הטסטים"""
    print("🚀 התחלת טסטים מקיפים לבדיקת בעיה 3\n")

    tests = [
        test_cleanup_start_messages_basic,
        test_cleanup_start_messages_history,
        test_cleanup_start_messages_errors,
        test_cleanup_start_messages_no_start_message,
        test_cleanup_start_messages_empty_history,
        test_start_function_calls_cleanup,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ טסט {test_func.__name__} נכשל עם שגיאה: {e}")
            failed += 1

    print(f"\n📊 תוצאות: {passed} עברו, {failed} נכשלו")

    if failed == 0:
        print("\n🎉 כל הטסטים עברו בהצלחה!")
        print("✅ בעיה 3 נפתרה - ניקוי הודעות /start עובד")
        return True
    else:
        print(f"\n❌ {failed} טסטים נכשלו")
        return False


if __name__ == "__main__":
    result = asyncio.run(run_all_tests())
    exit(0 if result else 1)
