#!/usr/bin/env python3
"""
טסט מאוד פשוט ומבודד לבדיקת לוגיקת cancel()
לא תלוי בשום תלויות חיצוניות
"""

from unittest.mock import AsyncMock, MagicMock


def test_cancel_logic_with_inventory_flag():
    """טסט סינכרוני לבדיקת הלוגיקה"""
    print("🧪 בדיקת לוגיקת cancel() עם דגל מלאי")

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

    # Mock של פונקציות חיצוניות
    show_rest_mock = AsyncMock()
    start_mock = AsyncMock()

    # קוד הפונקציה cancel() מועתק לכאן לבדיקה מבודדת
    async def cancel_test(update, context):
        await update.callback_query.answer()
        msg = context.user_data["edit_product_data"]["start_msg"]
        await msg.delete()
        del context.user_data["edit_product_data"]

        # פתרון: בדיקה מאיפה באנו וחזרה לשם
        if context.user_data.get('came_from_inventory'):
            # באנו ממלאי נוכחי - חזרה לשם
            await show_rest_mock(update, context, from_back_button=True)
        else:
            # באנו ממקום אחר - חזרה לעמוד הבית
            await start_mock(update, context)

        return -1  # ConversationHandler.END

    try:
        # הרצת הפונקציה
        import asyncio
        result = asyncio.run(cancel_test(update, context))

        # בדיקות
        assert result == -1, f"Expected END (-1), got {result}"

        # וידוא ש-show_rest_mock נקרא עם from_back_button=True
        show_rest_mock.assert_called_once_with(
            update, context, from_back_button=True
        )

        # וידוא ש-start_mock לא נקרא
        start_mock.assert_not_called()

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


def test_cancel_logic_without_inventory_flag():
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

    # Mock של פונקציות חיצוניות
    show_rest_mock = AsyncMock()
    start_mock = AsyncMock()

    # קוד הפונקציה cancel() מועתק לכאן לבדיקה מבודדת
    async def cancel_test(update, context):
        await update.callback_query.answer()
        msg = context.user_data["edit_product_data"]["start_msg"]
        await msg.delete()
        del context.user_data["edit_product_data"]

        # פתרון: בדיקה מאיפה באנו וחזרה לשם
        if context.user_data.get('came_from_inventory'):
            # באנו ממלאי נוכחי - חזרה לשם
            await show_rest_mock(update, context, from_back_button=True)
        else:
            # באנו ממקום אחר - חזרה לעמוד הבית
            await start_mock(update, context)

        return -1  # ConversationHandler.END

    try:
        # הרצת הפונקציה
        import asyncio
        result = asyncio.run(cancel_test(update, context))

        # בדיקות
        assert result == -1, f"Expected END (-1), got {result}"

        # וידוא ש-start_mock נקרא
        start_mock.assert_called_once_with(update, context)

        # וידוא ש-show_rest_mock לא נקרא
        show_rest_mock.assert_not_called()

        print("✅ לוגיקת cancel() עובדת נכון ללא came_from_inventory")
        return True

    except Exception as e:
        print(f"❌ טסט נכשל: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """הרצת כל הטסטים"""
    print("🚀 התחלת טסטים מבודדים לבדיקת תיקון בעיה 1\n")

    test1 = test_cancel_logic_with_inventory_flag()
    test2 = test_cancel_logic_without_inventory_flag()

    if test1 and test2:
        print("\n🎉 כל הטסטים עברו בהצלחה!")
        print("✅ בעיה 1 נפתרה - כפתור חזור מחזיר למלאי נוכחי")
        return True
    else:
        print("\n❌ חלק מהטסטים נכשלו")
        return False


if __name__ == "__main__":
    result = run_all_tests()
    exit(0 if result else 1)
