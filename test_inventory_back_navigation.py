#!/usr/bin/env python3
"""
טסט פשוט לבדיקת לוגיקת תיקון בעיה 1
בודק את הלוגיקה של cancel() בלבד
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock


async def test_cancel_logic():
    """טסט פשוט לבדיקת לוגיקת cancel"""
    print("🧪 בדיקת לוגיקת cancel()")

    # יצירת mock objects
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.answer = AsyncMock()
    context = MagicMock()

    # Mock של הודעה
    msg_mock = AsyncMock()
    context.user_data = {
        'edit_product_data': {
            'start_msg': msg_mock
        },
        'came_from_inventory': True  # דגל שקבענו
    }

    # ייבוא הפונקציה (בלי תלויות חיצוניות)
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Mock של פונקציות חיצוניות
    from funcs import bot_funcs
    bot_funcs.show_rest_from_last_day = AsyncMock()
    bot_funcs.start = AsyncMock()

    # ייבוא הפונקציה המבוקרת
    from handlers.edit_product_handler import cancel

    try:
        # הרצת הפונקציה
        result = await cancel(update, context)

        # בדיקות
        assert result == -1, f"Expected END (-1), got {result}"  # ConversationHandler.END = -1

        # וידוא ש-show_rest_from_last_day נקרא עם from_back_button=True
        bot_funcs.show_rest_from_last_day.assert_called_once_with(
            update, context, from_back_button=True
        )

        # וידוא ש-start לא נקרא (כי באנו ממלאי)
        bot_funcs.start.assert_not_called()

        # וידוא שהודעה נמחקה
        msg_mock.delete.assert_called_once()

        # וידוא שנתונים נוקו
        assert 'edit_product_data' not in context.user_data, "edit_product_data לא נוקה"

        print("✅ לוגיקת cancel() עובדת נכון עם came_from_inventory=True")
        return True

    except Exception as e:
        print(f"❌ טסט נכשל: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cancel_logic_without_inventory_flag():
    """טסט לבדיקה שאם אין דגל - חוזר לעמוד הבית"""
    print("🧪 בדיקת לוגיקת cancel() ללא דגל")

    # יצירת mock objects
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.answer = AsyncMock()
    context = MagicMock()

    # Mock של הודעה - ללא דגל came_from_inventory
    msg_mock = AsyncMock()
    context.user_data = {
        'edit_product_data': {
            'start_msg': msg_mock
        }
        # אין came_from_inventory
    }

    # ייבוא הפונקציה (בלי תלויות חיצוניות)
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Mock של פונקציות חיצוניות
    from funcs import bot_funcs
    bot_funcs.show_rest_from_last_day = AsyncMock()
    bot_funcs.start = AsyncMock()

    # ייבוא הפונקציה המבוקרת
    from handlers.edit_product_handler import cancel

    try:
        # הרצת הפונקציה
        result = await cancel(update, context)

        # בדיקות
        assert result == -1, f"Expected END (-1), got {result}"

        # וידוא ש-start נקרא (כי לא באנו ממלאי)
        bot_funcs.start.assert_called_once_with(update, context)

        # וידוא ש-show_rest_from_last_day לא נקרא
        bot_funcs.show_rest_from_last_day.assert_not_called()

        print("✅ לוגיקת cancel() עובדת נכון ללא came_from_inventory")
        return True

    except Exception as e:
        print(f"❌ טסט נכשל: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """הרצת כל הטסטים"""
    print("🚀 התחלת טסטים לבדיקת תיקון בעיה 1\n")

    test1 = await test_cancel_logic()
    test2 = await test_cancel_logic_without_inventory_flag()

    if test1 and test2:
        print("\n🎉 כל הטסטים עברו בהצלחה!")
        print("✅ בעיה 1 נפתרה - כפתור חזור מחזיר למלאי נוכחי")
        return True
    else:
        print("\n❌ חלק מהטסטים נכשלו")
        return False


if __name__ == "__main__":
    result = asyncio.run(run_all_tests())
    exit(0 if result else 1)
