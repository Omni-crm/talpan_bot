#!/usr/bin/env python3
"""
טסט מקיף ל-Phase 4: עריכת מוצרים
בודק את המערכת החדשה של עריכת מוצרים עם temp_data ו-original_data
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# הוסף את התיקייה הראשית ל-PATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from handlers.new_order_handler import (
    CollectOrderDataStates,
    ProductStates,
    EditStates,
    start_edit_product,
    edit_product_quantity,
    edit_product_price,
    delete_product_confirm,
    apply_edit_changes,
    cancel_edit_changes,
    restore_edit_state,
    apply_quantity_edit,
    apply_price_edit
)

class TestPhase4ProductEditing(unittest.TestCase):
    """טסטים ל-Phase 4: עריכת מוצרים"""

    def setUp(self):
        """אתחול לפני כל טסט"""
        self.context = MagicMock()
        self.context.user_data = {
            "collect_order_data": {
                "customer": {
                    "name": "Test User",
                    "username": "@testuser",
                    "phone": "055-1234567",
                    "address": "Test Address"
                },
                "products": [{
                    "id": 123,
                    "name": "Test Product",
                    "quantity": 3,
                    "unit_price": 10.5,
                    "total_price": 31.5
                }],
                "current_state": CollectOrderDataStates.PRODUCT_LIST,
                "active_product": None,
                "navigation_stack": [],
                "lang": "he"
            }
        }
        self.update = MagicMock()
        self.update.callback_query = MagicMock()
        self.update.callback_query.answer = AsyncMock()
        self.update.effective_user = MagicMock()

    async def test_start_edit_product_success(self):
        """בדיקת התחלת עריכת מוצר בהצלחה"""
        # Mock message
        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        # Set callback data for editing product at index 0
        self.update.callback_query.data = "edit_0"

        with patch('handlers.new_order_handler.get_edit_product_options_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["עריכת מוצר", "בחר פעולת עריכה"]

            result = await start_edit_product(self.update, self.context)

            # בדוק ש-active_product נוצר
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertIsNotNone(active_product)
            self.assertEqual(active_product["index"], 0)
            self.assertEqual(active_product["state"], EditStates.SELECT_EDIT_ACTION)
            self.assertTrue(active_product["edit_mode"])

            # בדוק original_data ו-temp_data
            self.assertEqual(active_product["original_data"]["name"], "Test Product")
            self.assertEqual(active_product["temp_data"]["quantity"], 3)
            self.assertEqual(active_product["temp_data"]["unit_price"], 10.5)

            # בדוק navigation stack
            stack = self.context.user_data["collect_order_data"]["navigation_stack"]
            self.assertEqual(len(stack), 1)
            self.assertEqual(stack[0]["type"], "edit")
            self.assertEqual(stack[0]["state"], EditStates.SELECT_EDIT_ACTION)

            self.assertEqual(result, EditStates.SELECT_EDIT_ACTION)

    async def test_start_edit_product_invalid_index(self):
        """בדיקת עריכת מוצר עם אינדקס לא תקין"""
        # Set callback data for editing product at invalid index
        self.update.callback_query.data = "edit_5"  # Only have 1 product at index 0

        with patch('handlers.new_order_handler.restore_order_state') as mock_restore:
            mock_restore.return_value = CollectOrderDataStates.PRODUCT_LIST

            result = await start_edit_product(self.update, self.context)

            mock_restore.assert_called_once()

    async def test_edit_product_quantity(self):
        """בדיקת בחירה עריכת כמות"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": EditStates.SELECT_EDIT_ACTION,
            "edit_mode": True,
            "temp_data": {
                "name": "Test Product",
                "quantity": 3,
                "unit_price": 10.5,
                "stock": 50
            }
        }

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_select_quantity_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["ערוך כמות ל", "כמות נוכחית", "הזן כמות חדשה"]

            result = await edit_product_quantity(self.update, self.context)

            # בדוק ש-active_product עודכן
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["state"], EditStates.EDIT_QUANTITY)

            # בדוק navigation stack
            stack = self.context.user_data["collect_order_data"]["navigation_stack"]
            self.assertEqual(len(stack), 1)
            self.assertEqual(stack[0]["state"], EditStates.EDIT_QUANTITY)

            self.assertEqual(result, EditStates.EDIT_QUANTITY)

    async def test_apply_quantity_edit_success(self):
        """בדיקת החלת שינויי כמות בהצלחה"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": EditStates.EDIT_QUANTITY,
            "edit_mode": True,
            "temp_data": {
                "name": "Test Product",
                "quantity": 3,
                "unit_price": 10.5,
                "stock": 50,
                "total_price": 31.5
            }
        }

        # Mock הודעה עם כמות חדשה
        self.update.callback_query = None
        self.update.effective_message = MagicMock()
        self.update.effective_message.text = "5"
        self.update.effective_message.delete = AsyncMock()

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_edit_product_options_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["כמות עודכנה", "עריכת מוצר", "בחר פעולת עריכה"]

            result = await apply_quantity_edit(self.update, self.context)

            # בדוק ש-temp_data עודכן
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["temp_data"]["quantity"], 5)
            self.assertEqual(active_product["temp_data"]["total_price"], 52.5)  # 5 * 10.5
            self.assertEqual(active_product["state"], EditStates.SELECT_EDIT_ACTION)

            self.assertEqual(result, EditStates.SELECT_EDIT_ACTION)

    async def test_apply_quantity_edit_insufficient_stock(self):
        """בדיקת כמות גדולה מהמלאי בעריכה"""
        # אתחל active_product עם מלאי קטן
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": EditStates.EDIT_QUANTITY,
            "edit_mode": True,
            "temp_data": {
                "name": "Test Product",
                "quantity": 3,
                "unit_price": 10.5,
                "stock": 5,  # מלאי קטן
                "total_price": 31.5
            }
        }

        # Mock הודעה עם כמות גדולה מהמלאי
        self.update.callback_query = None
        self.update.effective_message = MagicMock()
        self.update.effective_message.text = "10"
        self.update.effective_message.delete = AsyncMock()

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_back_cancel_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["ערוך כמות ל", "אין מספיק מלאי", "מלאי זמין"]

            result = await apply_quantity_edit(self.update, self.context)

            # צריך להישאר באותו state עם הודעת שגיאה
            self.assertEqual(result, EditStates.EDIT_QUANTITY)

    async def test_apply_price_edit_success(self):
        """בדיקת החלת שינויי מחיר בהצלחה"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": EditStates.EDIT_PRICE,
            "edit_mode": True,
            "temp_data": {
                "name": "Test Product",
                "quantity": 3,
                "unit_price": 10.5,
                "stock": 50,
                "total_price": 31.5
            }
        }

        # Mock הודעה עם מחיר חדש
        self.update.callback_query = None
        self.update.effective_message = MagicMock()
        self.update.effective_message.text = "12.0"
        self.update.effective_message.delete = AsyncMock()

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_edit_product_options_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["מחיר עודכן", "עריכת מוצר", "בחר פעולת עריכה"]

            result = await apply_price_edit(self.update, self.context)

            # בדוק ש-temp_data עודכן
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["temp_data"]["unit_price"], 12.0)
            self.assertEqual(active_product["temp_data"]["total_price"], 36.0)  # 3 * 12.0
            self.assertEqual(active_product["state"], EditStates.SELECT_EDIT_ACTION)

            self.assertEqual(result, EditStates.SELECT_EDIT_ACTION)

    async def test_delete_product_confirm(self):
        """בדיקת מחיקת מוצר"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": EditStates.SELECT_EDIT_ACTION,
            "edit_mode": True,
            "temp_data": {
                "name": "Test Product",
                "quantity": 3,
                "unit_price": 10.5,
                "total_price": 31.5
            }
        }

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_products_markup') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["מוצר נמחק", "אין מוצרים בהזמנה", "בחר מוצר"]

            result = await delete_product_confirm(self.update, self.context)

            # בדוק שמוצר נמחק
            products = self.context.user_data["collect_order_data"]["products"]
            self.assertEqual(len(products), 0)

            # בדוק ש-active_product נמחק
            self.assertNotIn("active_product", self.context.user_data["collect_order_data"])

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)

    async def test_apply_edit_changes(self):
        """בדיקת החלת שינויים סופית"""
        # אתחל active_product עם שינויים
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": EditStates.SELECT_EDIT_ACTION,
            "edit_mode": True,
            "original_data": {
                "name": "Test Product",
                "quantity": 3,
                "unit_price": 10.5,
                "total_price": 31.5
            },
            "temp_data": {
                "name": "Test Product",
                "quantity": 5,  # שונה
                "unit_price": 12.0,  # שונה
                "total_price": 60.0  # 5 * 12.0
            }
        }

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.create_product_list_text') as mock_create_list, \
             patch('handlers.new_order_handler.get_product_management_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_create_list.return_value = "רשימת מוצרים מעודכנת..."
            mock_kb.return_value = MagicMock()
            mock_t.return_value = "שינויים הוחלו"

            result = await apply_edit_changes(self.update, self.context)

            # בדוק שמוצר עודכן ברשימה
            products = self.context.user_data["collect_order_data"]["products"]
            self.assertEqual(products[0]["quantity"], 5)
            self.assertEqual(products[0]["unit_price"], 12.0)
            self.assertEqual(products[0]["total_price"], 60.0)

            # בדוק ש-active_product נמחק
            self.assertNotIn("active_product", self.context.user_data["collect_order_data"])

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)

    async def test_cancel_edit_changes(self):
        """בדיקת ביטול שינויים"""
        # אתחל active_product עם שינויים
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": EditStates.SELECT_EDIT_ACTION,
            "edit_mode": True,
            "temp_data": {
                "name": "Test Product",
                "quantity": 5,  # שונה מהמקורי
                "unit_price": 12.0,  # שונה מהמקורי
                "total_price": 60.0
            }
        }

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.create_product_list_text') as mock_create_list, \
             patch('handlers.new_order_handler.get_product_management_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_create_list.return_value = "רשימת מוצרים..."
            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["שינויים בוטלו", "עריכת מוצר"]

            result = await cancel_edit_changes(self.update, self.context)

            # בדוק שמוצר לא השתנה (השינויים בוטלו)
            products = self.context.user_data["collect_order_data"]["products"]
            self.assertEqual(products[0]["quantity"], 3)  # חזר למקורי
            self.assertEqual(products[0]["unit_price"], 10.5)  # חזר למקורי

            # בדוק ש-active_product נמחק
            self.assertNotIn("active_product", self.context.user_data["collect_order_data"])

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)

    async def test_restore_edit_select_action(self):
        """בדיקת שחזור מצב בחירת פעולת עריכה"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": EditStates.EDIT_QUANTITY,
            "edit_mode": True,
            "temp_data": {"name": "Test Product"}
        }

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_edit_product_options_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["עריכת מוצר", "בחר פעולת עריכה"]

            state_data = {"state": EditStates.SELECT_EDIT_ACTION}
            result = await restore_edit_state(self.update, self.context, state_data)

            # בדוק ש-active_product עודכן
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["state"], EditStates.SELECT_EDIT_ACTION)

            self.assertEqual(result, EditStates.SELECT_EDIT_ACTION)

    def test_edit_state_enum_values(self):
        """בדיקת ערכי ה-enum החדש"""
        self.assertEqual(EditStates.SELECT_EDIT_ACTION, 20)
        self.assertEqual(EditStates.EDIT_QUANTITY, 21)
        self.assertEqual(EditStates.EDIT_PRICE, 22)
        self.assertEqual(EditStates.CONFIRM_EDIT, 23)

    def test_temp_data_preservation(self):
        """בדיקת שמירת temp_data במהלך עריכה"""
        # סימולציה של עריכה
        original_data = {
            "name": "Original Product",
            "quantity": 2,
            "unit_price": 8.0,
            "total_price": 16.0
        }

        temp_data = original_data.copy()
        temp_data["quantity"] = 5  # שינוי
        temp_data["total_price"] = 40.0  # חישוב חדש

        # בדוק שהנתונים נשמרו
        self.assertEqual(original_data["quantity"], 2)  # מקורי לא השתנה
        self.assertEqual(temp_data["quantity"], 5)  # זמני השתנה
        self.assertEqual(temp_data["total_price"], 40.0)

    def test_navigation_stack_edit_flow(self):
        """בדיקת navigation stack במהלך תהליך עריכה"""
        from handlers.new_order_handler import push_navigation_state

        # סימולציה של תהליך עריכה מלא
        push_navigation_state(self.context, "order", {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "started_product_list"
        })

        push_navigation_state(self.context, "edit", {
            "product_index": 0,
            "state": EditStates.SELECT_EDIT_ACTION,
            "action": "started_editing_product"
        })

        push_navigation_state(self.context, "edit", {
            "product_index": 0,
            "state": EditStates.EDIT_QUANTITY,
            "action": "chose_to_edit_quantity"
        })

        push_navigation_state(self.context, "edit", {
            "product_index": 0,
            "state": EditStates.SELECT_EDIT_ACTION,
            "action": "quantity_updated_to_5"
        })

        push_navigation_state(self.context, "order", {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "applied_edit_changes"
        })

        stack = self.context.user_data["collect_order_data"]["navigation_stack"]
        self.assertEqual(len(stack), 5)

        # בדוק סוגי המצבים
        self.assertEqual(stack[0]["type"], "order")
        self.assertEqual(stack[1]["type"], "edit")
        self.assertEqual(stack[2]["type"], "edit")
        self.assertEqual(stack[3]["type"], "edit")
        self.assertEqual(stack[4]["type"], "order")

        # בדוק סדר המצבים
        self.assertEqual(stack[0]["state"], CollectOrderDataStates.PRODUCT_LIST)
        self.assertEqual(stack[1]["state"], EditStates.SELECT_EDIT_ACTION)
        self.assertEqual(stack[2]["state"], EditStates.EDIT_QUANTITY)
        self.assertEqual(stack[3]["state"], EditStates.SELECT_EDIT_ACTION)
        self.assertEqual(stack[4]["state"], CollectOrderDataStates.PRODUCT_LIST)


if __name__ == '__main__':
    print("🚀 התחלת טסטים ל-Phase 4: עריכת מוצרים")
    print("=" * 50)

    # הרץ את הטסטים
    unittest.main(verbosity=2)
