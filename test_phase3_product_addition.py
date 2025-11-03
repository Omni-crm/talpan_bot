#!/usr/bin/env python3
"""
טסט מקיף ל-Phase 3: הוספת מוצרים
בודק את המערכת החדשה של active_product ו-navigation stack
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
    collect_product,
    collect_quantity,
    collect_total_price,
    restore_product_state
)

class TestPhase3ProductAddition(unittest.TestCase):
    """טסטים ל-Phase 3: הוספת מוצרים"""

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
                "products": [],
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

    @patch('handlers.new_order_handler.get_product_by_id')
    @patch('handlers.new_order_handler.get_products_markup')
    @patch('handlers.new_order_handler.t')
    async def test_collect_product_success(self, mock_t, mock_kb, mock_get_product):
        """בדיקת בחירת מוצר בהצלחה"""
        # Mock product data
        mock_product = {
            'id': 123,
            'name': 'Test Product',
            'stock': 50
        }
        mock_get_product.return_value = mock_product
        mock_t.return_value = "בחר מוצר"
        mock_kb.return_value = MagicMock()

        # Mock message editing
        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock
        msg_mock.edit_text = AsyncMock()

        # Set callback data
        self.update.callback_query.data = "123"

        result = await collect_product(self.update, self.context)

        # בדוק ש-active_product נוצר
        active_product = self.context.user_data["collect_order_data"]["active_product"]
        self.assertIsNotNone(active_product)
        self.assertEqual(active_product["index"], 0)  # מוצר ראשון
        self.assertEqual(active_product["state"], ProductStates.ENTER_QUANTITY)

        # בדוק temp_data
        temp_data = active_product["temp_data"]
        self.assertEqual(temp_data["selected_product_id"], 123)
        self.assertEqual(temp_data["name"], "Test Product")
        self.assertEqual(temp_data["stock"], 50)
        self.assertIsNone(temp_data["quantity"])
        self.assertIsNone(temp_data["unit_price"])

        # בדוק navigation stack
        stack = self.context.user_data["collect_order_data"]["navigation_stack"]
        self.assertEqual(len(stack), 1)
        self.assertEqual(stack[0]["type"], "product")
        self.assertEqual(stack[0]["state"], ProductStates.ENTER_QUANTITY)

        self.assertEqual(result, CollectOrderDataStates.QUANTITY)

    @patch('handlers.new_order_handler.get_product_by_id')
    async def test_collect_product_not_found(self, mock_get_product):
        """בדיקת מוצר שלא נמצא"""
        mock_get_product.return_value = None

        self.update.callback_query.data = "999"
        self.context.user_data["collect_order_data"]["start_msg"] = AsyncMock()

        with patch('handlers.new_order_handler.restore_order_state') as mock_restore:
            mock_restore.return_value = CollectOrderDataStates.PRODUCT_LIST

            result = await collect_product(self.update, self.context)

            mock_restore.assert_called_once()

    async def test_collect_quantity_invalid_format(self):
        """בדיקת כמות בפורמט לא תקין"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": ProductStates.ENTER_QUANTITY,
            "temp_data": {
                "selected_product_id": 123,
                "name": "Test Product",
                "stock": 50,
                "quantity": None,
                "unit_price": None
            }
        }

        # Mock הודעה עם טקסט לא תקין
        self.update.callback_query = None
        self.update.effective_message = MagicMock()
        self.update.effective_message.text = "abc"
        self.update.effective_message.delete = AsyncMock()

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_select_quantity_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.return_value = "כמות לא תקינה"

            result = await collect_quantity(self.update, self.context)

            # צריך להישאר באותו state
            self.assertEqual(result, CollectOrderDataStates.QUANTITY)

    async def test_collect_quantity_insufficient_stock(self):
        """בדיקת כמות גדולה מהמלאי"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": ProductStates.ENTER_QUANTITY,
            "temp_data": {
                "selected_product_id": 123,
                "name": "Test Product",
                "stock": 5,  # מלאי קטן
                "quantity": None,
                "unit_price": None
            }
        }

        # Mock הודעה עם כמות גדולה מהמלאי
        self.update.callback_query = None
        self.update.effective_message = MagicMock()
        self.update.effective_message.text = "10"  # יותר מהמלאי
        self.update.effective_message.delete = AsyncMock()

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_back_cancel_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["אין מספיק מלאי", "מלאי זמין"]

            result = await collect_quantity(self.update, self.context)

            # צריך להישאר באותו state עם הודעת שגיאה
            self.assertEqual(result, CollectOrderDataStates.QUANTITY)

    async def test_collect_quantity_success(self):
        """בדיקת הזנת כמות בהצלחה"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": ProductStates.ENTER_QUANTITY,
            "temp_data": {
                "selected_product_id": 123,
                "name": "Test Product",
                "stock": 50,
                "quantity": None,
                "unit_price": None
            }
        }

        # Mock הודעה עם כמות תקינה
        self.update.callback_query = None
        self.update.effective_message = MagicMock()
        self.update.effective_message.text = "5"
        self.update.effective_message.delete = AsyncMock()

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_select_price_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.return_value = "הזן מחיר"

            result = await collect_quantity(self.update, self.context)

            # בדוק ש-active_product עודכן
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["temp_data"]["quantity"], 5)
            self.assertEqual(active_product["state"], ProductStates.ENTER_PRICE)

            # בדוק navigation stack
            stack = self.context.user_data["collect_order_data"]["navigation_stack"]
            self.assertEqual(len(stack), 1)
            self.assertEqual(stack[0]["state"], ProductStates.ENTER_PRICE)

            self.assertEqual(result, CollectOrderDataStates.TOTAL_PRICE)

    async def test_collect_total_price_success(self):
        """בדיקת הזנת מחיר בהצלחה והשלמת מוצר"""
        # אתחל active_product עם כמות
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": ProductStates.ENTER_PRICE,
            "temp_data": {
                "selected_product_id": 123,
                "name": "Test Product",
                "stock": 50,
                "quantity": 3,
                "unit_price": None
            }
        }

        # Mock הודעה עם מחיר
        self.update.callback_query = None
        self.update.effective_message = MagicMock()
        self.update.effective_message.text = "10.5"
        self.update.effective_message.delete = AsyncMock()

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.create_product_list_text') as mock_create_list, \
             patch('handlers.new_order_handler.get_product_management_kb') as mock_kb:

            mock_create_list.return_value = "רשימת מוצרים..."
            mock_kb.return_value = MagicMock()

            result = await collect_total_price(self.update, self.context)

            # בדוק שהמוצר נוסף לרשימה
            products = self.context.user_data["collect_order_data"]["products"]
            self.assertEqual(len(products), 1)
            product = products[0]
            self.assertEqual(product["id"], 123)
            self.assertEqual(product["name"], "Test Product")
            self.assertEqual(product["quantity"], 3)
            self.assertEqual(product["unit_price"], 10.5)
            self.assertEqual(product["total_price"], 31.5)  # 3 * 10.5

            # בדוק ש-active_product נמחק
            self.assertNotIn("active_product", self.context.user_data["collect_order_data"])

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)

    async def test_restore_product_select_state(self):
        """בדיקת שחזור מצב בחירת מוצר"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": ProductStates.ENTER_QUANTITY,
            "temp_data": {"name": "Test Product"}
        }

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_products_markup') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.return_value = "בחר מוצר"

            state_data = {"state": ProductStates.SELECT_PRODUCT}
            result = await restore_product_state(self.update, self.context, state_data)

            # בדוק ש-active_product עודכן
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["state"], ProductStates.SELECT_PRODUCT)

            self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)

    async def test_restore_product_quantity_state(self):
        """בדיקת שחזור מצב הזנת כמות"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": ProductStates.ENTER_PRICE,
            "temp_data": {"name": "Test Product"}
        }

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_select_quantity_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["הזן כמות", "הזן כמות ל"]

            state_data = {"state": ProductStates.ENTER_QUANTITY}
            result = await restore_product_state(self.update, self.context, state_data)

            # בדוק ש-active_product עודכן
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["state"], ProductStates.ENTER_QUANTITY)

            self.assertEqual(result, CollectOrderDataStates.QUANTITY)

    async def test_restore_product_price_state(self):
        """בדיקת שחזור מצב הזנת מחיר"""
        # אתחל active_product
        self.context.user_data["collect_order_data"]["active_product"] = {
            "index": 0,
            "state": ProductStates.CONFIRM_PRODUCT,
            "temp_data": {"name": "Test Product"}
        }

        msg_mock = AsyncMock()
        self.context.user_data["collect_order_data"]["start_msg"] = msg_mock

        with patch('handlers.new_order_handler.get_select_price_kb') as mock_kb, \
             patch('handlers.new_order_handler.t') as mock_t:

            mock_kb.return_value = MagicMock()
            mock_t.side_effect = ["הזן מחיר", "הזן מחיר ל"]

            state_data = {"state": ProductStates.ENTER_PRICE}
            result = await restore_product_state(self.update, self.context, state_data)

            # בדוק ש-active_product עודכן
            active_product = self.context.user_data["collect_order_data"]["active_product"]
            self.assertEqual(active_product["state"], ProductStates.ENTER_PRICE)

            self.assertEqual(result, CollectOrderDataStates.TOTAL_PRICE)

    def test_data_structure_after_product_addition(self):
        """בדיקת מבנה הנתונים לאחר הוספת מוצר"""
        # סימולציה של מוצר שנוסף
        self.context.user_data["collect_order_data"]["products"] = [{
            "id": 123,
            "name": "Test Product",
            "quantity": 3,
            "unit_price": 10.5,
            "total_price": 31.5
        }]

        # בדוק מבנה המוצר
        product = self.context.user_data["collect_order_data"]["products"][0]
        self.assertIn("id", product)
        self.assertIn("name", product)
        self.assertIn("quantity", product)
        self.assertIn("unit_price", product)
        self.assertIn("total_price", product)

        # וודא ש-active_product נמחק או None
        active_product = self.context.user_data["collect_order_data"].get("active_product")
        self.assertTrue(active_product is None, "active_product should be None or not exist")

    def test_navigation_stack_during_product_flow(self):
        """בדיקת navigation stack במהלך תהליך הוספת מוצר"""
        from handlers.new_order_handler import push_navigation_state

        # סימולציה של תהליך הוספת מוצר
        push_navigation_state(self.context, "order", {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "started_adding_products"
        })

        push_navigation_state(self.context, "product", {
            "product_index": 0,
            "state": ProductStates.ENTER_QUANTITY,
            "action": "selected_product_TestProduct"
        })

        push_navigation_state(self.context, "product", {
            "product_index": 0,
            "state": ProductStates.ENTER_PRICE,
            "action": "quantity_entered_3"
        })

        push_navigation_state(self.context, "order", {
            "state": CollectOrderDataStates.PRODUCT_LIST,
            "action": "product_added_TestProduct"
        })

        stack = self.context.user_data["collect_order_data"]["navigation_stack"]
        self.assertEqual(len(stack), 4)

        # בדוק סוגי המצבים
        self.assertEqual(stack[0]["type"], "order")
        self.assertEqual(stack[1]["type"], "product")
        self.assertEqual(stack[2]["type"], "product")
        self.assertEqual(stack[3]["type"], "order")

        # בדוק סדר המצבים
        self.assertEqual(stack[0]["state"], CollectOrderDataStates.PRODUCT_LIST)
        self.assertEqual(stack[1]["state"], ProductStates.ENTER_QUANTITY)
        self.assertEqual(stack[2]["state"], ProductStates.ENTER_PRICE)
        self.assertEqual(stack[3]["state"], CollectOrderDataStates.PRODUCT_LIST)


if __name__ == '__main__':
    print("🚀 התחלת טסטים ל-Phase 3: הוספת מוצרים")
    print("=" * 50)

    # הרץ את הטסטים
    unittest.main(verbosity=2)
