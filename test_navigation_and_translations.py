#!/usr/bin/env python3
"""
🔍 COMPREHENSIVE NAVIGATION & TRANSLATION TEST SCRIPT
Tests all navigation buttons, translations, and keyboard functionality
"""

import sys
import os
from typing import List, Dict, Any, Optional

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import configurations
from config.config import *
from config.kb import *
from config.translations import t, TEXTS
from funcs.bot_funcs import *
from db.db import db_client

class TestResult:
    def __init__(self, name: str, passed: bool, message: str, severity: str = "ERROR"):
        self.name = name
        self.passed = passed
        self.message = message
        self.severity = severity  # ERROR, WARNING, INFO

class NavigationTester:
    def __init__(self):
        self.results: List[TestResult] = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        
    def test(self, name: str, condition: bool, error_msg: str, success_msg: str = "OK", severity: str = "ERROR"):
        """Run a test and record result"""
        self.total_tests += 1
        if condition:
            self.passed_tests += 1
            self.results.append(TestResult(name, True, success_msg, "INFO"))
            print(f"✅ {name}: {success_msg}")
        else:
            self.failed_tests += 1
            self.results.append(TestResult(name, False, error_msg, severity))
            print(f"❌ {name}: {error_msg}")
        return condition
    
    def warning(self, name: str, message: str):
        """Record a warning"""
        self.results.append(TestResult(name, False, message, "WARNING"))
        print(f"⚠️  {name}: {message}")
    
    def info(self, name: str, message: str):
        """Record info"""
        self.results.append(TestResult(name, True, message, "INFO"))
        print(f"ℹ️  {name}: {message}")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)
        print(f"Total Tests: {self.total_tests}")
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        print(f"Success Rate: {(self.passed_tests/self.total_tests*100) if self.total_tests > 0 else 0:.1f}%")
        
        # Group by severity
        errors = [r for r in self.results if r.severity == "ERROR" and not r.passed]
        warnings = [r for r in self.results if r.severity == "WARNING"]
        
        if errors:
            print(f"\n🔴 CRITICAL ERRORS ({len(errors)}):")
            for r in errors:
                print(f"  - {r.name}: {r.message}")
        
        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for r in warnings:
                print(f"  - {r.name}: {r.message}")
        
        print("="*80)
        return self.failed_tests == 0

def test_translations():
    """Test all translations exist"""
    print("\n" + "="*80)
    print("🌐 TESTING TRANSLATIONS")
    print("="*80)
    
    tester = NavigationTester()
    
    # Required translation keys for navigation
    required_keys = [
        "btn_home", "btn_back", "no_previous_menu",
        "filter_by_date_instruction", "filter_by_client_instruction", "filter_by_product_instruction",
        "edit_stock_or_delete", "edit_crude_stock_prompt", "choose_status",
        "filter_by", "choose_language"
    ]
    
    for key in required_keys:
        # Check both languages
        ru_exists = key in TEXTS and "ru" in TEXTS[key]
        he_exists = key in TEXTS and "he" in TEXTS[key]
        
        tester.test(
            f"Translation '{key}' exists in Russian",
            ru_exists,
            f"Missing Russian translation for '{key}'",
            "Russian translation exists"
        )
        
        tester.test(
            f"Translation '{key}' exists in Hebrew",
            he_exists,
            f"Missing Hebrew translation for '{key}'",
            "Hebrew translation exists"
        )
        
        # Check they're not empty
        if ru_exists:
            ru_value = TEXTS[key]["ru"]
            tester.test(
                f"Translation '{key}' (ru) not empty",
                bool(ru_value and ru_value.strip()),
                f"Russian translation for '{key}' is empty",
                "Not empty"
            )
        
        if he_exists:
            he_value = TEXTS[key]["he"]
            tester.test(
                f"Translation '{key}' (he) not empty",
                bool(he_value and he_value.strip()),
                f"Hebrew translation for '{key}' is empty",
                "Not empty"
            )
    
    return tester

def test_keyboard_functions():
    """Test all keyboard functions accept lang parameter"""
    print("\n" + "="*80)
    print("⌨️  TESTING KEYBOARD FUNCTIONS")
    print("="*80)
    
    tester = NavigationTester()
    
    # List of keyboard functions that should accept lang
    keyboard_functions = [
        'get_shift_end_kb', 'get_cancel_kb', 'get_back_cancel_kb',
        'get_add_more_or_confirm_kb', 'get_confirm_order_kb', 'get_edit_product_kb',
        'get_edit_product_crude_kb', 'get_select_price_kb', 'get_select_quantity_kb',
        'get_two_step_ask_kb', 'get_digits_kb', 'get_operator_shift_start_kb',
        'get_orders_filter_kb', 'get_filter_orders_by_status_kb', 'get_security_kb',
        'get_db_format_kb', 'get_quick_reports_kb', 'get_filter_instruction_kb',
        'get_change_links_kb', 'get_manage_roles_kb', 'get_admin_action_kb',
        'get_edit_template_kb', 'get_actions_template_kb', 'get_courier_minutes_kb',
        'get_delay_minutes_kb', 'get_username_kb', 'get_skip_back_cancel_kb',
        'get_stock_management_kb', 'get_edit_product_actions_kb', 'get_confirm_delete_kb',
        'get_products_markup_left_edit_stock', 'get_products_markup_left_edit_stock_crude'
    ]
    
    for func_name in keyboard_functions:
        # Check function exists
        exists = func_name in globals() or hasattr(sys.modules['config.kb'], func_name)
        tester.test(
            f"Function '{func_name}' exists",
            exists,
            f"Function '{func_name}' not found in kb.py"
        )
        
        if exists:
            try:
                # Get function
                if func_name in globals():
                    func = globals()[func_name]
                else:
                    func = getattr(sys.modules['config.kb'], func_name)
                
                # Check if it accepts lang parameter
                import inspect
                sig = inspect.signature(func)
                has_lang = 'lang' in sig.parameters
                
                tester.test(
                    f"Function '{func_name}' accepts 'lang' parameter",
                    has_lang,
                    f"Function '{func_name}' does not accept 'lang' parameter",
                    "Accepts lang parameter"
                )
                
                # Try calling with different languages
                if has_lang:
                    try:
                        kb_ru = func(lang='ru')
                        tester.test(
                            f"Function '{func_name}' can be called with lang='ru'",
                            kb_ru is not None,
                            f"Function '{func_name}' returned None for lang='ru'",
                            "Returns keyboard"
                        )
                    except Exception as e:
                        tester.test(
                            f"Function '{func_name}' can be called with lang='ru'",
                            False,
                            f"Error calling '{func_name}' with lang='ru': {str(e)}"
                        )
                    
                    try:
                        kb_he = func(lang='he')
                        tester.test(
                            f"Function '{func_name}' can be called with lang='he'",
                            kb_he is not None,
                            f"Function '{func_name}' returned None for lang='he'",
                            "Returns keyboard"
                        )
                    except Exception as e:
                        tester.test(
                            f"Function '{func_name}' can be called with lang='he'",
                            False,
                            f"Error calling '{func_name}' with lang='he': {str(e)}"
                        )
            except Exception as e:
                tester.test(
                    f"Function '{func_name}' can be inspected",
                    False,
                    f"Error inspecting '{func_name}': {str(e)}"
                )
    
    return tester

def test_navigation_buttons():
    """Test navigation buttons in keyboards"""
    print("\n" + "="*80)
    print("🔘 TESTING NAVIGATION BUTTONS")
    print("="*80)
    
    tester = NavigationTester()
    
    # Test keyboards that should have navigation buttons
    keyboards_with_nav = [
        ('get_products_markup_left_edit_stock', ['home']),
        ('get_products_markup_left_edit_stock_crude', ['back', 'home']),
        ('get_filter_instruction_kb', ['back', 'home']),
        ('get_filter_orders_by_status_kb', ['back', 'home']),
        ('get_select_price_kb', ['back', 'home']),
        ('get_select_quantity_kb', ['back', 'home']),
        ('get_two_step_ask_kb', ['home']),
        ('get_digits_kb', ['home']),
        ('get_courier_minutes_kb', ['home']),
        ('get_delay_minutes_kb', ['home']),
    ]
    
    for func_name, expected_buttons in keyboards_with_nav:
        try:
            # Get function
            if func_name in globals():
                func = globals()[func_name]
            else:
                func = getattr(sys.modules['config.kb'], func_name)
            
            # Call with Hebrew to test translation
            kb = func(lang='he')
            
            # Check if keyboard has buttons
            if hasattr(kb, 'inline_keyboard'):
                buttons_text = []
                buttons_data = []
                
                for row in kb.inline_keyboard:
                    for button in row:
                        buttons_text.append(button.text)
                        buttons_data.append(button.callback_data)
                
                # Check for expected callback_data
                for expected in expected_buttons:
                    has_button = expected in buttons_data
                    tester.test(
                        f"Keyboard '{func_name}' has '{expected}' button",
                        has_button,
                        f"Keyboard '{func_name}' missing '{expected}' button. Found: {buttons_data}",
                        f"Has '{expected}' button"
                    )
                
                # Check that buttons don't have hardcoded Russian text
                for i, text in enumerate(buttons_text):
                    # Common Russian words in buttons
                    russian_indicators = ['Отмена', 'Назад', 'Домой', 'Главное меню']
                    has_russian = any(indicator in text for indicator in russian_indicators)
                    
                    if has_russian and buttons_data[i] in expected_buttons:
                        tester.warning(
                            f"Keyboard '{func_name}' button may have hardcoded Russian",
                            f"Button '{text}' (callback: {buttons_data[i]}) may be hardcoded"
                        )
            else:
                tester.test(
                    f"Keyboard '{func_name}' is valid InlineKeyboardMarkup",
                    False,
                    f"Keyboard '{func_name}' does not have inline_keyboard attribute"
                )
        except Exception as e:
            tester.test(
                f"Keyboard '{func_name}' can be tested",
                False,
                f"Error testing '{func_name}': {str(e)}"
            )
    
    return tester

def test_static_keyboards():
    """Check for static keyboards that shouldn't exist"""
    print("\n" + "="*80)
    print("🔍 CHECKING FOR STATIC KEYBOARDS")
    print("="*80)
    
    tester = NavigationTester()
    
    # These should NOT exist as constants anymore
    old_static_keyboards = [
        'SELECT_PRICE_KB', 'SELECT_QUANTITY_KB', 'TWO_STEP_ASK_KB',
        'DIGITS_KB', 'COURIER_MINUTES_KB', 'DELAY_MINUTES_KB',
        'FILTER_ORDERS_BY_STATUS_KB'
    ]
    
    for kb_name in old_static_keyboards:
        exists = kb_name in globals() or (hasattr(sys.modules['config.kb'], kb_name) if 'config.kb' in sys.modules else False)
        
        if exists:
            tester.warning(
                f"Static keyboard '{kb_name}' still exists",
                f"Static keyboard '{kb_name}' should be converted to function"
            )
        else:
            tester.info(
                f"Static keyboard '{kb_name}' removed",
                f"Good! '{kb_name}' is not a static keyboard"
            )
    
    return tester

def test_database_connection():
    """Test database connection"""
    print("\n" + "="*80)
    print("💾 TESTING DATABASE CONNECTION")
    print("="*80)
    
    tester = NavigationTester()
    
    try:
        # Test Supabase connection - no limit parameter
        products = db_client.select('products')
        tester.test(
            "Database connection works",
            products is not None and isinstance(products, list),
            "Failed to connect to database or got invalid response",
            "Database connection successful"
        )
        
        # Test users table
        users = db_client.select('users')
        tester.test(
            "Users table accessible",
            users is not None and isinstance(users, list),
            "Cannot access users table or got invalid response",
            "Users table accessible"
        )
    except Exception as e:
        tester.test(
            "Database connection works",
            False,
            f"Database error: {str(e)}"
        )
    
    return tester

def test_imports():
    """Test that all necessary modules can be imported"""
    print("\n" + "="*80)
    print("📦 TESTING IMPORTS")
    print("="*80)
    
    tester = NavigationTester()
    
    # Test critical imports
    modules_to_test = [
        'config.kb',
        'config.translations',
        'funcs.bot_funcs',
        'db.db',
        'handlers.new_order_handler',
        'handlers.make_tg_session_handler',
        'handlers.courier_choose_minutes',
        'handlers.courier_choose_delay'
    ]
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            tester.test(
                f"Module '{module_name}' imports successfully",
                True,
                f"Cannot import '{module_name}'",
                "Import successful"
            )
        except Exception as e:
            tester.test(
                f"Module '{module_name}' imports successfully",
                False,
                f"Import error for '{module_name}': {str(e)}"
            )
    
    return tester

def main():
    """Run all tests"""
    print("🔍 STARTING COMPREHENSIVE NAVIGATION & TRANSLATION TESTS")
    print("="*80)
    
    all_testers = []
    
    # Run all test suites
    all_testers.append(test_imports())
    all_testers.append(test_database_connection())
    all_testers.append(test_translations())
    all_testers.append(test_keyboard_functions())
    all_testers.append(test_navigation_buttons())
    all_testers.append(test_static_keyboards())
    
    # Print final summary
    print("\n" + "="*80)
    print("📊 FINAL SUMMARY")
    print("="*80)
    
    total_tests = sum(t.total_tests for t in all_testers)
    total_passed = sum(t.passed_tests for t in all_testers)
    total_failed = sum(t.failed_tests for t in all_testers)
    
    print(f"Total Tests Run: {total_tests}")
    print(f"✅ Total Passed: {total_passed}")
    print(f"❌ Total Failed: {total_failed}")
    print(f"Success Rate: {(total_passed/total_tests*100) if total_tests > 0 else 0:.1f}%")
    
    # Collect all critical errors
    all_errors = []
    all_warnings = []
    
    for tester in all_testers:
        all_errors.extend([r for r in tester.results if r.severity == "ERROR" and not r.passed])
        all_warnings.extend([r for r in tester.results if r.severity == "WARNING"])
    
    if all_errors:
        print(f"\n🔴 ALL CRITICAL ERRORS ({len(all_errors)}):")
        for r in all_errors:
            print(f"  - {r.name}: {r.message}")
    
    if all_warnings:
        print(f"\n⚠️  ALL WARNINGS ({len(all_warnings)}):")
        for r in all_warnings:
            print(f"  - {r.name}: {r.message}")
    
    print("="*80)
    
    # Exit with error code if tests failed
    if total_failed > 0:
        print("\n❌ TESTS FAILED! Please fix the errors above.")
        sys.exit(1)
    else:
        print("\n✅ ALL TESTS PASSED!")
        sys.exit(0)

if __name__ == "__main__":
    main()
