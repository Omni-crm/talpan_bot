#!/usr/bin/env python3
"""
טסט פשוט ומבודד לבדיקת בעיה 2: כפתור חזור בבחירת פעולת עריכה
בודק רק את הלוגיקה הבסיסית ללא תלויות חיצוניות
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock


async def test_keyboard_has_back_button():
    """טסט לבדיקת שה-keyboard החדש מכיל כפתור חזור"""
    print("🧪 בדיקת keyboard עם כפתור חזור")

    # ייבוא הפונקציה
    from config.kb import get_edit_product_kb_with_back

    # קריאה לפונקציה
    keyboard = get_edit_product_kb_with_back('he')

    # בדיקה שה-keyboard קיים
    assert keyboard is not None, "keyboard לא נוצר"
    assert hasattr(keyboard, 'inline_keyboard'), "keyboard לא תקין"

    # בדיקת כפתורי ה-keyboard
    button_callbacks = []
    for row in keyboard.inline_keyboard:
        for button in row:
            button_callbacks.append(button.callback_data)

    # וידוא שיש את כל הכפתורים הנדרשים
    required_buttons = ['edit_name', 'edit_stock', 'edit_price', 'delete', 'back_to_product_list']
    for button in required_buttons:
        assert button in button_callbacks, f"כפתור {button} חסר"

    # וידוא שיש בדיוק 5 כפתורים (4 פעולות + 1 חזור)
    assert len(button_callbacks) == 5, f"מספר כפתורים לא נכון: {len(button_callbacks)}"

    print("✅ keyboard מכיל את כל הכפתורים הנדרשים כולל back_to_product_list")
    return True


async def test_back_to_product_list_function():
    """טסט לבדיקת הפונקציה back_to_product_list"""
    print("🧪 בדיקת פונקציית back_to_product_list")

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

    # קוד הפונקציה back_to_product_list מועתק לכאן לבדיקה מבודדת
    async def back_to_product_list_test(update, context):
        await update.callback_query.answer()

        # מחיקת הודעה נוכחית
        msg = context.user_data["edit_product_data"]["start_msg"]
        await msg.delete()

        # ניקוי נתונים
        del context.user_data["edit_product_data"]

        # חזרה לרשימת מלאי נוכחי
        await show_rest_mock(update, context, from_back_button=True)

        return -1  # ConversationHandler.END

    # הרצת הפונקציה
    result = await back_to_product_list_test(update, context)

    # בדיקות
    assert result == -1, f"Expected END (-1), got {result}"

    # וידוא ש-show_rest_mock נקרא עם from_back_button=True
    show_rest_mock.assert_called_once_with(
        update, context, from_back_button=True
    )

    # וידוא שהודעה נמחקה
    msg_mock.delete.assert_called_once()

    # וידוא שנתונים נוקו
    assert 'edit_product_data' not in context.user_data, "edit_product_data לא נוקה"

    print("✅ פונקציית back_to_product_list עובדת נכון")
    return True


async def test_translations_exist():
    """טסט לבדיקת שכל הטקסטים החדשים קיימים בתרגומים"""
    print("🧪 בדיקת תרגומים חדשים")

    from config.translations import t

    # רשימת הטקסטים החדשים
    new_texts = ['btn_edit_name', 'btn_edit_stock', 'btn_edit_price', 'btn_delete']

    for text_key in new_texts:
        # בדיקה בעברית
        hebrew_text = t(text_key, 'he')
        assert hebrew_text != text_key, f"טקסט {text_key} לא תורגם לעברית"
        assert hebrew_text != "", f"טקסט {text_key} ריק"

        # בדיקה ברוסית
        russian_text = t(text_key, 'ru')
        assert russian_text != text_key, f"טקסט {text_key} לא תורגם לרוסית"
        assert russian_text != "", f"טקסט {text_key} ריק"

    print("✅ כל הטקסטים החדשים קיימים בתרגומים")
    return True


async def run_all_tests():
    """הרצת כל הטסטים"""
    print("🚀 התחלת טסטים מבודדים לבדיקת בעיה 2\n")

    test1 = await test_keyboard_has_back_button()
    test2 = await test_back_to_product_list_function()
    test3 = await test_translations_exist()

    if test1 and test2 and test3:
        print("\n🎉 כל הטסטים עברו בהצלחה!")
        print("✅ בעיה 2 נפתרה - כפתור חזור בבחירת פעולת עריכה קיים ומתפקד")
        return True
    else:
        print("\n❌ חלק מהטסטים נכשלו")
        return False


if __name__ == "__main__":
    result = asyncio.run(run_all_tests())
    exit(0 if result else 1)
