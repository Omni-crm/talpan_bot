"""
טסט אינטגרציה מלא לבדיקת בעיות 1-4
בודק את כל הלוגיקה ביחד בסביבה קרובה לפרודקשן
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# הוספת הנתיב הנכון
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from funcs.bot_funcs import handle_navigation, start, show_rest_from_last_day, show_menu_edit_crude_stock
from handlers.edit_product_handler import start_edit_product, cancel
from funcs.utils import cleanup_start_messages, is_in_conversation, peek_navigation_history


def create_mock_db():
    """Mock של מסד הנתונים"""
    mock_client = MagicMock()
    # Mock של מוצרים
    mock_client.select.return_value = [
        {'id': 1, 'name': 'Product A', 'stock': 10, 'price': 100},
        {'id': 2, 'name': 'Product B', 'stock': 5, 'price': 200}
    ]
    return mock_client


def create_mock_update_context():
    """יצירת mock של update ו-context"""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.data = "back"
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_chat = MagicMock()
    update.effective_chat.id = 67890
    update.message = MagicMock()
    update.message.text = "/start"
    update.message.delete = AsyncMock()

    context = MagicMock()
    context.user_data = {}
    context.bot = AsyncMock()

    return update, context


async def test_problem_1_inventory_navigation():
    """טסט בעיה 1: ניווט חזרה ממלאי נוכחי"""
    update, context = create_mock_update_context()
    mock_db = create_mock_db()

    # סימולציה של תהליך: מלאי נוכחי -> עריכת מוצר -> חזרה
    print("🧪 בדיקת בעיה 1: ניווט חזרה ממלאי נוכחי")

    # שלב 1: הצגת מלאי נוכחי
    update.callback_query.data = "rest"  # קריאה למלאי נוכחי
    with patch('funcs.bot_funcs.send_message_with_cleanup', new_callable=AsyncMock):
        await show_rest_from_last_day(update, context)

    # בדיקה שהדגלים נקבעו נכון
    assert context.user_data.get('came_from_inventory') == True
    assert context.user_data.get('current_inventory_view') == 'stock_list'

    # הוספת היסטוריה (כמו שקורה בניווט רגיל)
    context.user_data['navigation_history'] = [{'menu': 'stock_list_menu'}]

    # שלב 2: סימולציה של כניסה לעריכת מוצר
    update.callback_query.data = "edit_1"
    with patch('telegram.Message.edit_text', new_callable=AsyncMock) as mock_edit:
        mock_msg = AsyncMock()
        mock_edit.return_value = mock_msg
        with patch('config.kb.get_edit_product_kb_with_back') as mock_kb:
            mock_kb.return_value = MagicMock()
            with patch('db.db.get_product_by_id', return_value={'id': 1, 'name': 'Product A', 'stock': 10}):
                await start_edit_product(update, context)

    # בדיקה שהדגל נשאר (בגלל היסטוריה)
    assert context.user_data.get('came_from_inventory') == True

    # שלב 3: סימולציה של לחיצה על חזרה בעריכת מוצר
    context.user_data["edit_product_data"] = {
        'start_msg': mock_msg,
        'product': {'id': 1, 'name': 'Product A'},
        'lang': 'he'
    }

    with patch('funcs.bot_funcs.show_rest_from_last_day', new_callable=AsyncMock) as mock_show_rest:
        await cancel(update, context)

        # בדיקה שחזר למלאי נוכחי
        mock_show_rest.assert_called_once()
        args = mock_show_rest.call_args
        assert args[1]['from_back_button'] == True  # חשוב: from_back_button=True

    print("✅ בעיה 1 עובדת: חזרה ממלאי נוכחי תקינה")
    return True


async def test_problem_2_edit_actions_keyboard():
    """טסט בעיה 2: כפתור חזור בתפריט עריכה"""
    update, context = create_mock_update_context()

    print("🧪 בדיקת בעיה 2: כפתור חזור בתפריט עריכה")

    # סימולציה של כניסה לעריכת מוצר
    update.callback_query.data = "edit_stock_1"
    with patch('telegram.Message.edit_text', new_callable=AsyncMock) as mock_edit:
        mock_msg = AsyncMock()
        mock_edit.return_value = mock_msg
        with patch('config.kb.get_edit_product_kb_with_back') as mock_kb:
            mock_kb.return_value = MagicMock()
            with patch('db.db.get_product_by_id', return_value={'id': 1, 'name': 'Product A', 'stock': 10}):
                await start_edit_product(update, context)

    # בדיקה שה-Message.edit_text נקרא עם ה-keyboard הנכון
    mock_edit.assert_called_once()
    call_args = mock_edit.call_args
    assert 'reply_markup' in call_args.kwargs

    print("✅ בעיה 2 עובדת: keyboard עם כפתור חזור נטען")
    return True


async def test_problem_3_start_cleanup():
    """טסט בעיה 3: ניקוי הודעות /start"""
    update, context = create_mock_update_context()

    print("🧪 בדיקת בעיה 3: ניקוי הודעות /start")

    # יצירת mock של היסטוריית צ'אט עם הודעות /start
    mock_messages = []
    for i in range(5):
        msg = MagicMock()
        msg.text = "/start" if i < 4 else "hello"  # 4 הודעות /start ו-1 רגילה
        msg.from_user = MagicMock()
        msg.from_user.id = 12345
        msg.delete = AsyncMock()
        mock_messages.append(msg)

    context.bot.get_chat_history = AsyncMock(return_value=mock_messages)

    # הרצת הפונקציה
    await cleanup_start_messages(update, context)

    # בדיקה ש-4 הודעות /start נמחקו (השארת אחת)
    delete_calls = sum(1 for msg in mock_messages if msg.text == "/start" and msg.delete.called)
    assert delete_calls == 3  # מחק 3 מתוך 4, השאיר 1

    print("✅ בעיה 3 עובדת: ניקוי הודעות /start תקין")
    return True


async def test_problem_4_conversation_back_logic():
    """טסט בעיה 4: לוגיקת חזרה בתוך conversations"""
    update, context = create_mock_update_context()

    print("🧪 בדיקת בעיה 4: לוגיקת חזרה בתוך conversations")

    # טסט 1: זיהוי conversation
    context.user_data = {'edit_product_data': {}}
    assert is_in_conversation(context) == True

    context.user_data = {'new_order_data': {}}
    assert is_in_conversation(context) == True

    context.user_data = {}
    assert is_in_conversation(context) == False

    # טסט 2: handle_conversation_back - edit_product
    context.user_data = {'edit_product_data': {'start_msg': AsyncMock()}}
    with patch('handlers.edit_product_handler.cancel', new_callable=AsyncMock) as mock_cancel:
        from funcs.bot_funcs import handle_conversation_back
        await handle_conversation_back(update, context)
        mock_cancel.assert_called_once_with(update, context)

    # טסט 3: handle_conversation_back - add_staff
    context.user_data = {'add_staff_data': {}}
    with patch('funcs.bot_funcs.show_admin_action_kb', new_callable=AsyncMock) as mock_show:
        await handle_conversation_back(update, context)
        mock_show.assert_called_once()

    print("✅ בעיה 4 עובדת: לוגיקת חזרה ב-conversations תקינה")
    return True


async def test_integration_full_flow():
    """טסט אינטגרציה מלא: תהליך שלם של ניווט"""
    update, context = create_mock_update_context()

    print("🧪 בדיקת תהליך אינטגרציה מלא")

    # תרחיש: משתמש רואה מלאי -> לוחץ על מוצר -> עורך -> חוזר
    context.user_data = {}

    # שלב 1: הצגת מלאי נוכחי
    with patch('funcs.bot_funcs.send_message_with_cleanup', new_callable=AsyncMock):
        await show_rest_from_last_day(update, context)

    assert context.user_data.get('came_from_inventory') == True

    # שלב 2: סימולציה של כניסה לעריכה
    context.user_data['navigation_history'] = [{'menu': 'stock_list_menu'}]
    update.callback_query.data = "edit_1"

    with patch('telegram.Message.edit_text', new_callable=AsyncMock) as mock_edit:
        mock_msg = AsyncMock()
        mock_edit.return_value = mock_msg
        with patch('config.kb.get_edit_product_kb_with_back') as mock_kb:
            mock_kb.return_value = MagicMock()
            with patch('db.db.get_product_by_id', return_value={'id': 1, 'name': 'Product A', 'stock': 10}):
                await start_edit_product(update, context)

    # בדיקה שהדגל נשמר
    assert context.user_data.get('came_from_inventory') == True

    # שלב 3: סימולציה של חזרה דרך handle_navigation
    context.user_data["edit_product_data"] = {
        'start_msg': mock_msg,
        'product': {'id': 1, 'name': 'Product A'},
        'lang': 'he'
    }

    update.callback_query.data = "back"
    with patch('funcs.bot_funcs.show_rest_from_last_day', new_callable=AsyncMock) as mock_show_rest:
        await handle_navigation(update, context)
        mock_show_rest.assert_called_once()

    print("✅ תהליך אינטגרציה מלא עובד תקין")
    return True


async def main():
    """הרצת כל הטסטים"""
    print("🚀 התחלת טסטים אינטגרציה לבדיקת בעיות 1-4\n")

    results = []

    try:
        result = await test_problem_1_inventory_navigation()
        results.append(("בעיה 1", result))
    except Exception as e:
        print(f"❌ טסט 1 נכשל: {e}")
        import traceback
        traceback.print_exc()
        results.append(("בעיה 1", False))

    try:
        result = await test_problem_2_edit_actions_keyboard()
        results.append(("בעיה 2", result))
    except Exception as e:
        print(f"❌ טסט 2 נכשל: {e}")
        import traceback
        traceback.print_exc()
        results.append(("בעיה 2", False))

    try:
        result = await test_problem_3_start_cleanup()
        results.append(("בעיה 3", result))
    except Exception as e:
        print(f"❌ טסט 3 נכשל: {e}")
        import traceback
        traceback.print_exc()
        results.append(("בעיה 3", False))

    try:
        result = await test_problem_4_conversation_back_logic()
        results.append(("בעיה 4", result))
    except Exception as e:
        print(f"❌ טסט 4 נכשל: {e}")
        import traceback
        traceback.print_exc()
        results.append(("בעיה 4", False))

    try:
        result = await test_integration_full_flow()
        results.append(("אינטגרציה מלאה", result))
    except Exception as e:
        print(f"❌ טסט אינטגרציה נכשל: {e}")
        import traceback
        traceback.print_exc()
        results.append(("אינטגרציה מלאה", False))

    # סיכום
    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"\n📊 תוצאות: {passed}/{total} עברו")
    if passed == total:
        print("🎉 כל טסטי האינטגרציה עברו בהצלחה!")
        print("✅ בעיות 1-4 נפתרו בהצלחה!")
    else:
        print("❌ יש כשלים בטסטי האינטגרציה")
        failed = [name for name, success in results if not success]
        print(f"טסטים שנכשלו: {failed}")


if __name__ == "__main__":
    asyncio.run(main())
