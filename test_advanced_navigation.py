#!/usr/bin/env python3
"""
טסט מקיף למערכת ניווט מתקדמת להזמנה חדשה
בודק את כל התרחישים והשינויים במבנה הנתונים
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
    push_navigation_state,
    step_back,
    restore_order_state,
    restore_product_state,
    restore_edit_state
)

class TestAdvancedNavigation(unittest.TestCase):
    """טסטים למערכת הניווט המתקדמת"""

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
                "current_state": CollectOrderDataStates.NAME,
                "active_product": None,
                "navigation_stack": [],
                "lang": "he"
            }
        }
        self.update = MagicMock()
        self.update.callback_query = MagicMock()
        self.update.callback_query.answer = AsyncMock()

    def test_push_navigation_state(self):
        """בדיקת דחיפה למחסנית ניווט"""
        # אתחול מחסנית
        self.context.user_data["collect_order_data"]["navigation_stack"] = []

        # דחיפה ראשונה
        push_navigation_state(self.context, "order", {
            "state": CollectOrderDataStates.NAME,
            "action": "enter_client_name"
        })

        stack = self.context.user_data["collect_order_data"]["navigation_stack"]
        self.assertEqual(len(stack), 1)
        self.assertEqual(stack[0]["type"], "order")
        self.assertEqual(stack[0]["state"], CollectOrderDataStates.NAME)

    def test_push_multiple_states(self):
        """בדיקת דחיפה מרובה למחסנית"""
        push_navigation_state(self.context, "order", {
            "state": CollectOrderDataStates.NAME,
            "action": "enter_client_name"
        })

        push_navigation_state(self.context, "order", {
            "state": CollectOrderDataStates.USERNAME,
            "action": "enter_client_username"
        })

        push_navigation_state(self.context, "order", {
            "state": CollectOrderDataStates.PHONE,
            "action": "enter_client_phone"
        })

        stack = self.context.user_data["collect_order_data"]["navigation_stack"]
        self.assertEqual(len(stack), 3)

        # בדיקת סדר הפוך (LIFO)
        self.assertEqual(stack[-1]["state"], CollectOrderDataStates.PHONE)
        self.assertEqual(stack[-2]["state"], CollectOrderDataStates.USERNAME)
        self.assertEqual(stack[-3]["state"], CollectOrderDataStates.NAME)

    def test_navigation_stack_limit(self):
        """בדיקת הגבלת גודל המחסנית"""
        # דחיפה של 25 מצבים
        for i in range(25):
            push_navigation_state(self.context, "order", {
                "state": CollectOrderDataStates.NAME,
                "action": f"action_{i}"
            })

        stack = self.context.user_data["collect_order_data"]["navigation_stack"]
        # צריך להיות מקסימום 20
        self.assertEqual(len(stack), 20)

    @patch('handlers.new_order_handler.restore_order_state')
    async def test_step_back_order_state(self, mock_restore):
        """בדיקת חזרה למצב order"""
        # אתחול מחסנית עם מצבי order
        self.context.user_data["collect_order_data"]["navigation_stack"] = [
            {"type": "order", "state": CollectOrderDataStates.NAME, "timestamp": "2024-01-01"},
            {"type": "order", "state": CollectOrderDataStates.USERNAME, "timestamp": "2024-01-01"},
            {"type": "order", "state": CollectOrderDataStates.PHONE, "timestamp": "2024-01-01"}
        ]

        mock_restore.return_value = CollectOrderDataStates.USERNAME

        result = await step_back(self.update, self.context)

        # צריך לקרוא ל-restore_order_state
        mock_restore.assert_called_once()
        self.assertEqual(result, CollectOrderDataStates.USERNAME)

        # המחסנית צריכה להכיל רק מצב אחד עכשיו
        stack = self.context.user_data["collect_order_data"]["navigation_stack"]
        self.assertEqual(len(stack), 2)  # הוצאנו את האחרון, נשארו 2

    @patch('handlers.new_order_handler.restore_order_state')
    async def test_step_back_to_product_list(self, mock_restore):
        """בדיקת חזרה לרשימת מוצרים"""
        # אתחול מחסנית עם מצב product list
        self.context.user_data["collect_order_data"]["navigation_stack"] = [
            {"type": "order", "state": CollectOrderDataStates.PRODUCT_LIST, "timestamp": "2024-01-01"}
        ]

        mock_restore.return_value = CollectOrderDataStates.PRODUCT_LIST

        result = await step_back(self.update, self.context)

        mock_restore.assert_called_once_with(
            self.update, self.context,
            {"type": "order", "state": CollectOrderDataStates.PRODUCT_LIST, "timestamp": "2024-01-01"}
        )

    @patch('handlers.new_order_handler.start')
    async def test_step_back_no_more_states(self, mock_start):
        """בדיקת חזרה כשאין יותר מצבים"""
        # מחסנית עם מצב אחד בלבד
        self.context.user_data["collect_order_data"]["navigation_stack"] = [
            {"type": "order", "state": CollectOrderDataStates.NAME, "timestamp": "2024-01-01"}
        ]

        result = await step_back(self.update, self.context)

        # צריך לקרוא ל-start ולהחזיר END
        mock_start.assert_called_once_with(self.update, self.context)
        self.assertEqual(result, -1)  # ConversationHandler.END

    @patch('handlers.new_order_handler.edit_conversation_message')
    @patch('handlers.new_order_handler.get_cancel_kb')
    @patch('handlers.new_order_handler.t')
    async def test_restore_order_state_name(self, mock_t, mock_kb, mock_edit):
        """בדיקת שחזור מצב שם"""
        mock_t.return_value = "הזן שם לקוח"
        mock_kb.return_value = MagicMock()
        mock_edit.return_value = MagicMock()

        self.context.user_data["collect_order_data"]["start_msg"] = MagicMock()

        result = await restore_order_state(self.update, self.context, {
            "state": CollectOrderDataStates.NAME
        })

        self.assertEqual(result, CollectOrderDataStates.NAME)
        mock_edit.assert_called_once()

    @patch('handlers.new_order_handler.edit_conversation_message')
    @patch('handlers.new_order_handler.get_username_kb')
    @patch('handlers.new_order_handler.t')
    async def test_restore_order_state_username(self, mock_t, mock_kb, mock_edit):
        """בדיקת שחזור מצב שם משתמש"""
        mock_t.return_value = "הזן @username"
        mock_kb.return_value = MagicMock()
        mock_edit.return_value = MagicMock()

        self.context.user_data["collect_order_data"]["start_msg"] = MagicMock()

        result = await restore_order_state(self.update, self.context, {
            "state": CollectOrderDataStates.USERNAME
        })

        self.assertEqual(result, CollectOrderDataStates.USERNAME)
        mock_edit.assert_called_once()

    @patch('handlers.new_order_handler.edit_conversation_message')
    @patch('handlers.new_order_handler.get_back_cancel_kb')
    @patch('handlers.new_order_handler.t')
    async def test_restore_order_state_phone(self, mock_t, mock_kb, mock_edit):
        """בדיקת שחזור מצב טלפון"""
        mock_t.return_value = "הזן טלפון"
        mock_kb.return_value = MagicMock()
        mock_edit.return_value = MagicMock()

        self.context.user_data["collect_order_data"]["start_msg"] = MagicMock()

        result = await restore_order_state(self.update, self.context, {
            "state": CollectOrderDataStates.PHONE
        })

        self.assertEqual(result, CollectOrderDataStates.PHONE)
        mock_edit.assert_called_once()

    @patch('handlers.new_order_handler.edit_conversation_message')
    @patch('handlers.new_order_handler.get_back_cancel_kb')
    @patch('handlers.new_order_handler.t')
    async def test_restore_order_state_address(self, mock_t, mock_kb, mock_edit):
        """בדיקת שחזור מצב כתובת"""
        mock_t.return_value = "הזן כתובת"
        mock_kb.return_value = MagicMock()
        mock_edit.return_value = MagicMock()

        self.context.user_data["collect_order_data"]["start_msg"] = MagicMock()

        result = await restore_order_state(self.update, self.context, {
            "state": CollectOrderDataStates.ADDRESS
        })

        self.assertEqual(result, CollectOrderDataStates.ADDRESS)
        mock_edit.assert_called_once()

    @patch('handlers.new_order_handler.edit_conversation_message')
    @patch('handlers.new_order_handler.get_products_markup')
    @patch('handlers.new_order_handler.t')
    async def test_restore_order_state_product_list(self, mock_t, mock_kb, mock_edit):
        """בדיקת שחזור מצב רשימת מוצרים"""
        mock_t.return_value = "בחר מוצר"
        mock_kb.return_value = MagicMock()
        mock_edit.return_value = MagicMock()

        self.context.user_data["collect_order_data"]["start_msg"] = MagicMock()
        self.update.effective_user = MagicMock()

        result = await restore_order_state(self.update, self.context, {
            "state": CollectOrderDataStates.PRODUCT_LIST
        })

        self.assertEqual(result, CollectOrderDataStates.PRODUCT_LIST)
        mock_edit.assert_called_once()

    async def test_restore_product_state(self):
        """בדיקת שחזור מצב מוצר - צריך לחזור לרשימת מוצרים"""
        with patch('handlers.new_order_handler.restore_order_state') as mock_restore:
            mock_restore.return_value = CollectOrderDataStates.PRODUCT_LIST

            result = await restore_product_state(self.update, self.context, {
                "product_index": 0,
                "state": ProductStates.SELECT_PRODUCT
            })

            mock_restore.assert_called_once_with(
                self.update, self.context,
                {"state": CollectOrderDataStates.PRODUCT_LIST, "action": "back_to_product_list"}
            )

    async def test_restore_edit_state(self):
        """בדיקת שחזור מצב עריכה - צריך לחזור לרשימת מוצרים"""
        with patch('handlers.new_order_handler.restore_order_state') as mock_restore:
            mock_restore.return_value = CollectOrderDataStates.PRODUCT_LIST

            result = await restore_edit_state(self.update, self.context, {
                "product_index": 0,
                "state": EditStates.SELECT_EDIT_ACTION
            })

            mock_restore.assert_called_once_with(
                self.update, self.context,
                {"state": CollectOrderDataStates.PRODUCT_LIST, "action": "back_to_product_list"}
            )

    def test_data_structure_initialization(self):
        """בדיקת מבנה הנתונים הראשוני"""
        data = self.context.user_data["collect_order_data"]

        # בדיקת מבנה customer
        self.assertIn("customer", data)
        self.assertEqual(data["customer"]["name"], None)
        self.assertEqual(data["customer"]["username"], None)
        self.assertEqual(data["customer"]["phone"], None)
        self.assertEqual(data["customer"]["address"], None)

        # בדיקת products
        self.assertIn("products", data)
        self.assertEqual(data["products"], [])

        # בדיקת מצב נוכחי
        self.assertIn("current_state", data)
        self.assertEqual(data["current_state"], CollectOrderDataStates.NAME)

        # בדיקת מוצר פעיל
        self.assertIn("active_product", data)
        self.assertEqual(data["active_product"], None)

        # בדיקת מחסנית ניווט
        self.assertIn("navigation_stack", data)
        self.assertEqual(data["navigation_stack"], [])

    def test_enum_values(self):
        """בדיקת ערכי ה-enums החדשים"""
        # CollectOrderDataStates
        self.assertEqual(CollectOrderDataStates.START, 0)
        self.assertEqual(CollectOrderDataStates.NAME, 1)
        self.assertEqual(CollectOrderDataStates.USERNAME, 2)
        self.assertEqual(CollectOrderDataStates.PHONE, 3)
        self.assertEqual(CollectOrderDataStates.ADDRESS, 4)
        self.assertEqual(CollectOrderDataStates.PRODUCT_LIST, 5)
        self.assertEqual(CollectOrderDataStates.CONFIRMATION, 6)

        # ProductStates
        self.assertEqual(ProductStates.SELECT_PRODUCT, 10)
        self.assertEqual(ProductStates.ENTER_QUANTITY, 11)
        self.assertEqual(ProductStates.ENTER_PRICE, 12)
        self.assertEqual(ProductStates.CONFIRM_PRODUCT, 13)

        # EditStates
        self.assertEqual(EditStates.SELECT_EDIT_ACTION, 20)
        self.assertEqual(EditStates.EDIT_QUANTITY, 21)
        self.assertEqual(EditStates.EDIT_PRICE, 22)
        self.assertEqual(EditStates.CONFIRM_EDIT, 23)

    def test_navigation_stack_persistence(self):
        """בדיקת שמירת המחסנית בין קריאות"""
        # דחיפה ראשונה
        push_navigation_state(self.context, "order", {
            "state": CollectOrderDataStates.NAME,
            "action": "test_action"
        })

        # סימולציה של קריאה חדשה לאותו context
        # המחסנית צריכה להישאר
        stack = self.context.user_data["collect_order_data"]["navigation_stack"]
        self.assertEqual(len(stack), 1)

        # דחיפה נוספת
        push_navigation_state(self.context, "order", {
            "state": CollectOrderDataStates.USERNAME,
            "action": "test_action2"
        })

        stack = self.context.user_data["collect_order_data"]["navigation_stack"]
        self.assertEqual(len(stack), 2)


if __name__ == '__main__':
    print("🚀 התחלת טסטים למערכת ניווט מתקדמת")
    print("=" * 50)

    # הרץ את הטסטים
    unittest.main(verbosity=2)
