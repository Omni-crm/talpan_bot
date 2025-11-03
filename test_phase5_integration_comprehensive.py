#!/usr/bin/env python3
"""
טסט אינטגרציה מקיף ל-Phase 5: בדיקת כל התרחישים
בודק את כל ה-flow מהתחלה עד הסוף עם מוצרים מרובים ועריכות
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call
import sys
import os
import json

# הוסף את התיקייה הראשית ל-PATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from handlers.new_order_handler import (
    CollectOrderDataStates,
    ProductStates,
    EditStates,
    start_collect_data,
    collect_name,
    collect_username,
    collect_phone,
    collect_address,
    collect_product,
    collect_quantity,
    collect_total_price,
    start_edit_product,
    apply_quantity_edit,
    apply_price_edit,
    apply_edit_changes,
    delete_product_confirm,
    add_more_products,
    go_to_confirm
)

class TestPhase5IntegrationComprehensive(unittest.TestCase):
    """טסט אינטגרציה מקיף לכל המערכת"""

    def setUp(self):
        """אתחול לפני כל טסט"""
        self.context = MagicMock()
        self.context.user_data = {
            "collect_order_data": {
                "customer": {
                    "name": None,
                    "username": None,
                    "phone": None,
                    "address": None
                },
                "products": [],
                "current_state": None,
                "active_product": None,
                "navigation_stack": [],
                "start_msg": None,
                "lang": "he"
            }
        }
        self.update = MagicMock()
        self.update.callback_query = MagicMock()
        self.update.callback_query.answer = AsyncMock()
        self.update.effective_user = MagicMock()
        self.update.effective_message = MagicMock()
        self.update.effective_message.delete = AsyncMock()

    async def test_complete_order_flow_with_multiple_products_and_edits(self):
        """טסט מקיף: הזמנה מלאה עם מוצרים מרובים ועריכות"""

        # === שלב 1: התחלת הזמנה ===
        self.update.callback_query.data = "new"
        msg_mock = AsyncMock()
        self.update.callback_query.message = msg_mock

        with patch('handlers.new_order_handler.send_message_with_cleanup') as mock_send, \
             patch('handlers.new_order_handler.t') as mock_t, \
             patch('handlers.new_order_handler.get_cancel_kb') as mock_kb, \
             patch('handlers.new_order_handler.save_message_id'):

            mock_send.return_value = msg_mock
            mock_t.return_value = "הזן שם לקוח"
            mock_kb.return_value = MagicMock()

            result = await start_collect_data(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.NAME)
            self.assertEqual(self.context.user_data["collect_order_data"]["current_state"], CollectOrderDataStates.NAME)
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 1)

        # === שלב 2: הזנת שם ===
        self.update.message = MagicMock()
        self.update.message.text = "ישראל ישראלי"
        self.update.callback_query = None

        with patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.get_username_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_edit.return_value = msg_mock
            mock_kb.return_value = MagicMock()
            mock_t.return_value = "הזן @username"

            result = await collect_name(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.USERNAME)
            self.assertEqual(self.context.user_data["collect_order_data"]["customer"]["name"], "ישראל ישראלי")
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 2)

        # === שלב 3: הזנת username ===
        self.update.message = MagicMock()
        self.update.message.text = "@israel_test"
        self.update.callback_query = None

        with patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.get_back_cancel_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_edit.return_value = msg_mock
            mock_kb.return_value = MagicMock()
            mock_t.return_value = "הזן טלפון"

            result = await collect_username(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.PHONE)
            self.assertEqual(self.context.user_data["collect_order_data"]["customer"]["username"], "@israel_test")
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 3)

        # === שלב 4: הזנת טלפון ===
        self.update.message = MagicMock()
        self.update.message.text = "050-1234567"

        with patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.get_back_cancel_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_edit.return_value = msg_mock
            mock_kb.return_value = MagicMock()
            mock_t.return_value = "הזן כתובת"

            result = await collect_phone(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.ADDRESS)
            self.assertEqual(self.context.user_data["collect_order_data"]["customer"]["phone"], "050-1234567")
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 4)

        # === שלב 5: הזנת כתובת ===
        self.update.message = MagicMock()
        self.update.message.text = "רחוב הרצל 123, תל אביב"

        with patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.get_products_markup') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_edit.return_value = msg_mock
            mock_kb.return_value = MagicMock()
            mock_t.return_value = "בחר מוצר"

            result = await collect_address(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)
            self.assertEqual(self.context.user_data["collect_order_data"]["customer"]["address"], "רחוב הרצל 123, תל אביב")
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 5)

        # === שלב 6: בחירת מוצר ראשון ===
        self.update.callback_query = MagicMock()
        self.update.callback_query.data = "123"

        with patch('handlers.new_order_handler.get_product_by_id') as mock_get_product, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.get_select_quantity_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_product = {'id': 123, 'name': 'לחם', 'stock': 50}
            mock_get_product.return_value = mock_product
            mock_edit.return_value = msg_mock
            mock_kb.return_value = MagicMock()
            mock_t.return_value = "בחר כמות"

            result = await collect_product(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.QUANTITY)
            self.assertIsNotNone(self.context.user_data["collect_order_data"]["active_product"])
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["temp_data"]["name"], "לחם")
            self.assertEqual(active_product["temp_data"]["selected_product_id"], 123)
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 6)

        # === שלב 7: הזנת כמות למוצר ראשון ===
        self.update.message = MagicMock()
        self.update.message.text = "2"

        with patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.get_select_price_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_edit.return_value = msg_mock
            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["בחר מחיר", "הזן מחיר ל"]

            result = await collect_quantity(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.TOTAL_PRICE)
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["temp_data"]["quantity"], 2)
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 7)

        # === שלב 8: הזנת מחיר למוצר ראשון ===
        self.update.message = MagicMock()
        self.update.message.text = "8.5"

        with patch('handlers.new_order_handler.create_product_list_text') as mock_create_list, \
             patch('handlers.new_order_handler.get_product_management_kb') as mock_kb, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_create_list.return_value = "רשימת מוצרים עם לחם..."
            mock_kb.return_value = MagicMock()
            mock_edit.return_value = msg_mock
            mock_t.return_value = "שינויים הוחלו"

            result = await collect_total_price(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)
            products = self.context.user_data["collect_order_data"]["products"]
            self.assertEqual(len(products), 1)
            self.assertEqual(products[0]["name"], "לחם")
            self.assertEqual(products[0]["quantity"], 2)
            self.assertEqual(products[0]["unit_price"], 8.5)
            self.assertEqual(products[0]["total_price"], 17.0)
            self.assertIsNone(self.context.user_data["collect_order_data"]["active_product"])
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 8)

        # === שלב 9: הוספת מוצר שני ===
        self.update.callback_query = MagicMock()
        self.update.callback_query.data = "add_more"

        with patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.get_products_markup') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_edit.return_value = msg_mock
            mock_kb.return_value = MagicMock()
            mock_t.return_value = "בחר מוצר"

            result = await add_more_products(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 9)

        # === שלב 10: בחירת מוצר שני ===
        self.update.callback_query.data = "456"

        with patch('handlers.new_order_handler.get_product_by_id') as mock_get_product, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.get_select_quantity_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_product = {'id': 456, 'name': 'חלב', 'stock': 30}
            mock_get_product.return_value = mock_product
            mock_edit.return_value = msg_mock
            mock_kb.return_value = MagicMock()
            mock_t.return_value = "בחר כמות"

            result = await collect_product(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.QUANTITY)
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["temp_data"]["name"], "חלב")
            self.assertEqual(active_product["index"], 1)  # מוצר שני
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 10)

        # === שלב 11: הזנת כמות למוצר שני ===
        self.update.message = MagicMock()
        self.update.message.text = "1"

        with patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.get_select_price_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_edit.return_value = msg_mock
            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["בחר מחיר", "הזן מחיר ל"]

            result = await collect_quantity(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.TOTAL_PRICE)
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["temp_data"]["quantity"], 1)

        # === שלב 12: הזנת מחיר למוצר שני ===
        self.update.message = MagicMock()
        self.update.message.text = "6.0"

        with patch('handlers.new_order_handler.create_product_list_text') as mock_create_list, \
             patch('handlers.new_order_handler.get_product_management_kb') as mock_kb, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_create_list.return_value = "רשימת מוצרים עם לחם וחלב..."
            mock_kb.return_value = MagicMock()
            mock_edit.return_value = msg_mock
            mock_t.return_value = "שינויים הוחלו"

            result = await collect_total_price(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)
            products = self.context.user_data["collect_order_data"]["products"]
            self.assertEqual(len(products), 2)
            self.assertEqual(products[1]["name"], "חלב")
            self.assertEqual(products[1]["quantity"], 1)
            self.assertEqual(products[1]["unit_price"], 6.0)
            self.assertEqual(products[1]["total_price"], 6.0)

        # === שלב 13: עריכת מוצר ראשון ===
        self.update.callback_query.data = "edit_0"

        with patch('handlers.new_order_handler.get_edit_product_options_kb') as mock_kb, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_edit.return_value = msg_mock
            mock_t.side_effect = ["עריכת מוצר", "בחר פעולת עריכה"]

            result = await start_edit_product(self.update, self.context)

            self.assertEqual(result, EditStates.SELECT_EDIT_ACTION)
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertTrue(active_product["edit_mode"])
            self.assertEqual(active_product["index"], 0)
            # בדוק ש-original_data נשמר
            self.assertEqual(active_product["original_data"]["name"], "לחם")
            self.assertEqual(active_product["original_data"]["quantity"], 2)
            self.assertEqual(len(self.context.user_data["collect_order_data"]["navigation_stack"]), 11)

        # === שלב 14: בחירת עריכת כמות ===
        self.update.callback_query.data = "edit_quantity"

        with patch('handlers.new_order_handler.get_select_quantity_kb') as mock_kb, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_edit.return_value = msg_mock
            mock_t.side_effect = ["ערוך כמות ל", "כמות נוכחית", "הזן כמות חדשה"]

            result = await edit_product_quantity(self.update, self.context)

            self.assertEqual(result, EditStates.EDIT_QUANTITY)
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["state"], EditStates.EDIT_QUANTITY)

        # === שלב 15: שינוי כמות ===
        self.update.message = MagicMock()
        self.update.message.text = "3"

        with patch('handlers.new_order_handler.get_edit_product_options_kb') as mock_kb, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_edit.return_value = msg_mock
            mock_t.side_effect = ["כמות עודכנה", "עריכת מוצר", "בחר פעולת עריכה"]

            result = await apply_quantity_edit(self.update, self.context)

            self.assertEqual(result, EditStates.SELECT_EDIT_ACTION)
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["temp_data"]["quantity"], 3)
            self.assertEqual(active_product["temp_data"]["total_price"], 25.5)  # 3 * 8.5

        # === שלב 16: החלת השינויים ===
        self.update.callback_query.data = "apply_edit"

        with patch('handlers.new_order_handler.create_product_list_text') as mock_create_list, \
             patch('handlers.new_order_handler.get_product_management_kb') as mock_kb, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_create_list.return_value = "רשימת מוצרים מעודכנת..."
            mock_kb.return_value = MagicMock()
            mock_edit.return_value = msg_mock
            mock_t.return_value = "שינויים הוחלו"

            result = await apply_edit_changes(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)
            products = self.context.user_data["collect_order_data"]["products"]
            self.assertEqual(products[0]["quantity"], 3)
            self.assertEqual(products[0]["total_price"], 25.5)
            self.assertIsNone(self.context.user_data["collect_order_data"]["active_product"])

        # === שלב 17: מחיקת מוצר שני ===
        self.update.callback_query.data = "edit_1"

        with patch('handlers.new_order_handler.get_edit_product_options_kb') as mock_kb, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_edit.return_value = msg_mock
            mock_t.side_effect = ["עריכת מוצר", "בחר פעולת עריכה"]

            result = await start_edit_product(self.update, self.context)

            self.assertEqual(result, EditStates.SELECT_EDIT_ACTION)

        # === שלב 18: בחירת מחיקה ===
        self.update.callback_query.data = "delete_product"

        with patch('handlers.new_order_handler.create_product_list_text') as mock_create_list, \
             patch('handlers.new_order_handler.get_product_management_kb') as mock_kb, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_create_list.return_value = "רשימת מוצרים עם לחם בלבד..."
            mock_kb.return_value = MagicMock()
            mock_edit.return_value = msg_mock
            mock_t.side_effect = ["מוצר נמחק", "עריכת מוצר"]

            result = await delete_product_confirm(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)
            products = self.context.user_data["collect_order_data"]["products"]
            self.assertEqual(len(products), 1)
            self.assertEqual(products[0]["name"], "לחם")

        # === שלב 19: אישור ההזמנה ===
        self.update.callback_query.data = "confirm_order"

        with patch('handlers.new_order_handler.confirm_order') as mock_confirm:
            mock_confirm.return_value = CollectOrderDataStates.CONFIRM_OR_NOT

            result = await go_to_confirm(self.update, self.context)

            # הטסט מסתיים כאן - ההזמנה מוכנה לאישור

    async def test_navigation_back_through_complete_flow(self):
        """בדיקת ניווט אחורה בכל התהליך"""

        # אתחול עם הזמנה מלאה
        self.context.user_data["collect_order_data"].update({
            "customer": {
                "name": "ישראל ישראלי",
                "username": "@israel_test",
                "phone": "050-1234567",
                "address": "רחוב הרצל 123, תל אביב"
            },
            "products": [{
                "id": 123,
                "name": "לחם",
                "quantity": 3,
                "unit_price": 8.5,
                "total_price": 25.5
            }],
            "current_state": CollectOrderDataStates.PRODUCT_LIST,
            "navigation_stack": [
                {"type": "order", "state": CollectOrderDataStates.NAME, "timestamp": "2024-01-01"},
                {"type": "order", "state": CollectOrderDataStates.USERNAME, "timestamp": "2024-01-01"},
                {"type": "order", "state": CollectOrderDataStates.PHONE, "timestamp": "2024-01-01"},
                {"type": "order", "state": CollectOrderDataStates.ADDRESS, "timestamp": "2024-01-01"},
                {"type": "order", "state": CollectOrderDataStates.PRODUCT_LIST, "timestamp": "2024-01-01"}
            ]
        })

        # חזרה לכתובת
        with patch('handlers.new_order_handler.restore_order_state') as mock_restore:
            mock_restore.return_value = CollectOrderDataStates.ADDRESS

            from handlers.new_order_handler import step_back
            result = await step_back(self.update, self.context)

            mock_restore.assert_called_once()
            self.assertEqual(result, CollectOrderDataStates.ADDRESS)

    async def test_error_handling_comprehensive(self):
        """בדיקת טיפול מקיף בשגיאות"""

        # === שגיאה: מוצר לא קיים ===
        self.update.callback_query.data = "999"

        with patch('handlers.new_order_handler.get_product_by_id') as mock_get_product, \
             patch('handlers.new_order_handler.restore_order_state') as mock_restore:

            mock_get_product.return_value = None
            mock_restore.return_value = CollectOrderDataStates.PRODUCT_LIST

            result = await collect_product(self.update, self.context)

            mock_restore.assert_called_once()

        # === שגיאה: אינדקס לא תקין בעריכה ===
        self.update.callback_query.data = "edit_5"  # אין מוצר באינדקס 5

        with patch('handlers.new_order_handler.restore_order_state') as mock_restore:
            mock_restore.return_value = CollectOrderDataStates.PRODUCT_LIST

            result = await start_edit_product(self.update, self.context)

            mock_restore.assert_called_once()

        # === שגיאה: כמות לא תקינה ===
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": EditStates.EDIT_QUANTITY,
            "edit_mode": True,
            "temp_data": {"name": "Test", "stock": 50}
        }

        self.update.message = MagicMock()
        self.update.message.text = "abc"  # לא מספר

        with patch('handlers.new_order_handler.get_select_quantity_kb') as mock_kb, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_edit.return_value = msg_mock
            mock_t.side_effect = ["ערוך כמות ל", "כמות לא תקינה", "הזן כמות חדשה"]

            result = await apply_quantity_edit(self.update, self.context)

            self.assertEqual(result, EditStates.EDIT_QUANTITY)  # נשאר באותו state

    def test_data_integrity_throughout_flow(self):
        """בדיקת אינטגריטי הנתונים בכל התהליך"""

        # אתחול נתונים
        order_data = self.context.user_data["collect_order_data"]

        # בדוק מבנה התחלתי
        self.assertEqual(order_data["customer"]["name"], None)
        self.assertEqual(len(order_data["products"]), 0)
        self.assertEqual(len(order_data["navigation_stack"]), 0)

        # סימולציה של הוספת מוצרים
        order_data["products"] = [
            {"id": 123, "name": "לחם", "quantity": 2, "unit_price": 8.5, "total_price": 17.0},
            {"id": 456, "name": "חלב", "quantity": 1, "unit_price": 6.0, "total_price": 6.0}
        ]

        # חישוב סה"כ
        total = sum(p["total_price"] for p in order_data["products"])
        self.assertEqual(total, 23.0)

        # בדוק שכל המוצרים תקינים
        for product in order_data["products"]:
            self.assertIn("id", product)
            self.assertIn("name", product)
            self.assertIn("quantity", product)
            self.assertIn("unit_price", product)
            self.assertIn("total_price", product)
            self.assertEqual(product["total_price"], product["quantity"] * product["unit_price"])

    def test_navigation_stack_comprehensive_tracking(self):
        """בדיקת מעקב מקיף של navigation stack"""

        from handlers.new_order_handler import push_navigation_state

        # סימולציה של תהליך מלא
        states_sequence = [
            (CollectOrderDataStates.NAME, "started_order"),
            (CollectOrderDataStates.USERNAME, "entered_name"),
            (CollectOrderDataStates.PHONE, "entered_username"),
            (CollectOrderDataStates.ADDRESS, "entered_phone"),
            (CollectOrderDataStates.PRODUCT_LIST, "entered_address"),
            (ProductStates.ENTER_QUANTITY, "selected_product_1"),
            (ProductStates.ENTER_PRICE, "entered_quantity_2"),
            (CollectOrderDataStates.PRODUCT_LIST, "entered_price_8.5"),
            (ProductStates.ENTER_QUANTITY, "selected_product_2"),
            (ProductStates.ENTER_PRICE, "entered_quantity_1"),
            (CollectOrderDataStates.PRODUCT_LIST, "entered_price_6.0"),
            (EditStates.SELECT_EDIT_ACTION, "started_editing_product_0"),
            (EditStates.EDIT_QUANTITY, "chose_to_edit_quantity"),
            (EditStates.SELECT_EDIT_ACTION, "quantity_updated_to_3"),
            (CollectOrderDataStates.PRODUCT_LIST, "applied_edit_changes"),
            (EditStates.SELECT_EDIT_ACTION, "started_editing_product_1"),
            (CollectOrderDataStates.PRODUCT_LIST, "deleted_product_1")
        ]

        for i, (state_type, action) in enumerate(states_sequence):
            if "product" in action or "edit" in action:
                push_navigation_state(self.context, "product" if "product" in action and "edit" not in action else "edit",
                                    {"product_index": 0 if "product_0" in action else 1, "state": state_type, "action": action})
            else:
                push_navigation_state(self.context, "order", {"state": state_type, "action": action})

        stack = self.context.user_data["collect_order_data"]["navigation_stack"]
        self.assertEqual(len(stack), len(states_sequence))

        # בדוק סדר הפוך (LIFO)
        for i, (expected_state, expected_action) in enumerate(reversed(states_sequence)):
            actual = stack[-(i+1)]
            if "product" in expected_action or "edit" in expected_action:
                self.assertEqual(actual["type"], "product" if "product" in expected_action and "edit" not in expected_action else "edit")
            else:
                self.assertEqual(actual["type"], "order")
            self.assertEqual(actual["state"], expected_state)

    async def test_edge_case_empty_order_after_deletions(self):
        """בדיקת edge case: הזמנה ריקה אחרי מחיקת כל המוצרים"""

        # אתחול עם מוצר אחד
        self.context.user_data["collect_order_data"]["products"] = [
            {"id": 123, "name": "לחם", "quantity": 1, "unit_price": 8.5, "total_price": 8.5}
        ]

        # מחיקת המוצר היחיד
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": EditStates.SELECT_EDIT_ACTION,
            "edit_mode": True,
            "temp_data": {"name": "לחם"}
        }

        self.update.callback_query.data = "delete_product"

        with patch('handlers.new_order_handler.get_products_markup') as mock_kb, \
             patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_edit.return_value = msg_mock
            mock_t.side_effect = ["מוצר נמחק", "אין מוצרים בהזמנה", "בחר מוצר"]

            result = await delete_product_confirm(self.update, self.context)

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)
            self.assertEqual(len(self.context.user_data["collect_order_data"]["products"]), 0)
            self.assertIsNone(self.context.user_data["collect_order_data"]["active_product"])

    async def test_multiple_concurrent_edits_simulation(self):
        """בדיקת סימולציה של עריכות מקבילות (למרות שאי אפשר באמת)"""

        # אתחול עם מוצרים מרובים
        self.context.user_data["collect_order_data"]["products"] = [
            {"id": 123, "name": "לחם", "quantity": 2, "unit_price": 8.5, "total_price": 17.0},
            {"id": 456, "name": "חלב", "quantity": 1, "unit_price": 6.0, "total_price": 6.0},
            {"id": 789, "name": "ביצים", "quantity": 6, "unit_price": 2.5, "total_price": 15.0}
        ]

        # עריכה של כל מוצר לפי תור
        for i, product in enumerate(self.context.user_data["collect_order_data"]["products"]):
            # התחלת עריכה
            self.update.callback_query.data = f"edit_{i}"

            with patch('handlers.new_order_handler.get_edit_product_options_kb') as mock_kb, \
                 patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
                 patch('handlers.new_order_handler.t') as mock_t:

                mock_kb.return_value = MagicMock()
                mock_edit.return_value = msg_mock
                mock_t.side_effect = ["עריכת מוצר", "בחר פעולת עריכה"]

                result = await start_edit_product(self.update, self.context)
                self.assertEqual(result, EditStates.SELECT_EDIT_ACTION)

            # עריכת כמות
            self.update.callback_query.data = "edit_quantity"

            with patch('handlers.new_order_handler.get_select_quantity_kb') as mock_kb, \
                 patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
                 patch('handlers.new_order_handler.t') as mock_t:

                mock_kb.return_value = MagicMock()
                mock_edit.return_value = msg_mock
                mock_t.side_effect = ["ערוך כמות ל", "כמות נוכחית", "הזן כמות חדשה"]

                result = await edit_product_quantity(self.update, self.context)
                self.assertEqual(result, EditStates.EDIT_QUANTITY)

            # שינוי כמות
            new_quantity = product["quantity"] + 1
            self.update.message = MagicMock()
            self.update.message.text = str(new_quantity)

            with patch('handlers.new_order_handler.get_edit_product_options_kb') as mock_kb, \
                 patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
                 patch('handlers.new_order_handler.t') as mock_t:

                mock_kb.return_value = MagicMock()
                mock_edit.return_value = msg_mock
                mock_t.side_effect = [f"כמות עודכנה ל{new_quantity}", "עריכת מוצר", "בחר פעולת עריכה"]

                result = await apply_quantity_edit(self.update, self.context)
                self.assertEqual(result, EditStates.SELECT_EDIT_ACTION)

            # החלת שינויים
            self.update.callback_query.data = "apply_edit"

            with patch('handlers.new_order_handler.create_product_list_text') as mock_create_list, \
                 patch('handlers.new_order_handler.get_product_management_kb') as mock_kb, \
                 patch('handlers.new_order_handler.edit_conversation_message') as mock_edit, \
                 patch('handlers.new_order_handler.t') as mock_t:

                mock_create_list.return_value = f"רשימת מוצרים עם {product['name']} מעודכן..."
                mock_kb.return_value = MagicMock()
                mock_edit.return_value = msg_mock
                mock_t.return_value = "שינויים הוחלו"

                result = await apply_edit_changes(self.update, self.context)
                self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)

        # בדוק שכל המוצרים עודכנו
        products = self.context.user_data["collect_order_data"]["products"]
        self.assertEqual(len(products), 3)
        self.assertEqual(products[0]["quantity"], 3)  # 2 + 1
        self.assertEqual(products[1]["quantity"], 2)  # 1 + 1
        self.assertEqual(products[2]["quantity"], 7)  # 6 + 1

        # חישוב סה"כ מעודכן
        total = sum(p["total_price"] for p in products)
        expected_total = (3 * 8.5) + (2 * 6.0) + (7 * 2.5)  # 25.5 + 12.0 + 17.5 = 55.0
        self.assertEqual(total, expected_total)


if __name__ == '__main__':
    print("🚀 התחלת טסט אינטגרציה מקיף ל-Phase 5")
    print("=" * 60)

    # הרץ את הטסטים
    unittest.main(verbosity=2)
