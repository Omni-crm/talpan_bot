#!/usr/bin/env python3
"""
🔍 BACK BUTTON VERIFICATION TEST
Tests that all back buttons work correctly with navigation history
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_back_button_flow():
    """Test simulated navigation flow"""
    print("=" * 80)
    print("🧪 BACK BUTTON FLOW TEST")
    print("=" * 80)
    
    # Simulate user_data
    context_user_data = {}
    
    # Test navigation history functions
    from funcs.utils import add_to_navigation_history, get_previous_menu
    
    test_cases = [
        {
            'name': 'Main → Admin → Daily Profit → Back → Back',
            'flow': [
                ('admin_menu', 'Enter admin menu'),
                ('daily_profit_menu', 'Enter daily profit'),
                ('back', 'Click back - should go to admin'),
                ('back', 'Click back - should go to home'),
            ],
            'expected_final': 'home'
        },
        {
            'name': 'Main → Admin → Quick Reports → Back',
            'flow': [
                ('admin_menu', 'Enter admin menu'),
                ('quick_reports_menu', 'Enter quick reports'),
                ('back', 'Click back - should go to admin'),
            ],
            'expected_final': 'admin_menu'
        },
        {
            'name': 'Main → Admin → Orders Filter → Back',
            'flow': [
                ('admin_menu', 'Enter admin menu'),
                ('orders_filter_menu', 'Enter orders filter'),
                ('back', 'Click back - should go to admin'),
            ],
            'expected_final': 'admin_menu'
        },
        {
            'name': 'Main → Admin → TG Sessions → Back',
            'flow': [
                ('admin_menu', 'Enter admin menu'),
                ('tg_sessions_menu', 'Enter TG sessions'),
                ('back', 'Click back - should go to admin'),
            ],
            'expected_final': 'admin_menu'
        },
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\n📋 TEST: {test['name']}")
        print("-" * 80)
        
        # Reset history
        context_user_data['navigation_history'] = []
        
        class MockContext:
            user_data = context_user_data
        
        context = MockContext()
        
        # Simulate flow
        for action, description in test['flow']:
            if action == 'back':
                menu = get_previous_menu(context)
                if menu:
                    print(f"  ⬅️  {description} → {menu['menu']}")
                else:
                    print(f"  ⬅️  {description} → HOME (no history)")
            else:
                add_to_navigation_history(context, action)
                print(f"  ➡️  {description} (history: {[m['menu'] for m in context.user_data['navigation_history']]})")
        
        # Check final state
        remaining_history = context.user_data.get('navigation_history', [])
        if test['expected_final'] == 'home' and len(remaining_history) == 0:
            print(f"  ✅ PASS: Navigation completed successfully")
            passed += 1
        elif remaining_history and remaining_history[-1]['menu'] == test['expected_final']:
            print(f"  ✅ PASS: Ended at {test['expected_final']}")
            passed += 1
        else:
            print(f"  ❌ FAIL: Expected {test['expected_final']}, got {remaining_history}")
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"📊 RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return failed == 0

def test_navigation_handler_coverage():
    """Test that handle_navigation supports all menu types"""
    print("\n" + "=" * 80)
    print("🔍 NAVIGATION HANDLER COVERAGE TEST")
    print("=" * 80)
    
    # Read handle_navigation function
    with open('funcs/bot_funcs.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all menu names added to history
    import re
    history_adds = re.findall(r"add_to_navigation_history\([^,]+,\s*'([^']+)'\)", content)
    
    print(f"\n📋 Found {len(history_adds)} menu types being added to history:")
    for menu in sorted(set(history_adds)):
        print(f"  • {menu}")
    
    # Find all menu names in handle_navigation
    handler_pattern = r"elif menu_name == '([^']+)':|if menu_name == '([^']+)':"
    handler_menus = re.findall(handler_pattern, content)
    handler_menus = [m[0] or m[1] for m in handler_menus if m[0] or m[1]]
    
    print(f"\n📋 Found {len(handler_menus)} menu types in handler:")
    for menu in sorted(set(handler_menus)):
        print(f"  • {menu}")
    
    # Check for missing menus
    history_set = set(history_adds)
    handler_set = set(handler_menus)
    
    missing = history_set - handler_set
    extra = handler_set - history_set
    
    print(f"\n" + "=" * 80)
    
    if missing:
        print(f"❌ MISSING FROM HANDLER ({len(missing)}):")
        for menu in sorted(missing):
            print(f"  • {menu}")
        print("\n⚠️  These menus add themselves to history but handler doesn't support them!")
        return False
    else:
        print("✅ All menu types are supported by handler!")
    
    if extra:
        print(f"\n⚠️  EXTRA IN HANDLER ({len(extra)}):")
        for menu in sorted(extra):
            print(f"  • {menu}")
        print("These are in handler but not added to history (might be intentional)")
    
    return True

def test_duplicate_history_entries():
    """Test that we don't get duplicate entries"""
    print("\n" + "=" * 80)
    print("🔍 DUPLICATE HISTORY ENTRIES TEST")
    print("=" * 80)
    
    from funcs.utils import add_to_navigation_history
    
    class MockContext:
        user_data = {}
    
    context = MockContext()
    
    # Add same menu multiple times
    add_to_navigation_history(context, 'admin_menu')
    add_to_navigation_history(context, 'admin_menu')
    add_to_navigation_history(context, 'admin_menu')
    
    history = context.user_data.get('navigation_history', [])
    
    print(f"Added 'admin_menu' 3 times")
    print(f"History length: {len(history)}")
    print(f"History: {[m['menu'] for m in history]}")
    
    if len(history) == 3:
        print("\n⚠️  WARNING: Duplicate entries are NOT prevented!")
        print("Consider adding duplicate prevention to add_to_navigation_history")
        return False
    else:
        print("\n✅ Duplicates are handled correctly")
        return True

def main():
    """Run all tests"""
    print("🔍 STARTING BACK BUTTON VERIFICATION TESTS")
    print("=" * 80)
    
    results = []
    
    # Run tests
    results.append(("Flow Test", test_back_button_flow()))
    results.append(("Handler Coverage", test_navigation_handler_coverage()))
    results.append(("Duplicate Prevention", test_duplicate_history_entries()))
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - Review above for details")
        sys.exit(1)

if __name__ == "__main__":
    main()
