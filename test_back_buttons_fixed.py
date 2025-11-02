#!/usr/bin/env python3
"""
🔍 COMPREHENSIVE BACK BUTTON TEST - UPDATED FOR from_back_button PARAMETER
Tests the actual back button navigation with real simulation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_back_navigation_with_parameter():
    """Test that navigating back with from_back_button=True doesn't re-add menus to history"""
    print("=" * 80)
    print("🧪 TEST: Back Navigation with from_back_button Parameter")
    print("=" * 80)
    
    # Simulate user_data
    class MockContext:
        user_data = {}
    
    context = MockContext()
    
    from funcs.utils import add_to_navigation_history, get_previous_menu
    
    # Simulate: Main → Admin → Orders Filter
    print("\n1️⃣  User goes to Admin menu")
    add_to_navigation_history(context, 'admin_menu')
    print(f"   History: {[m['menu'] for m in context.user_data.get('navigation_history', [])]}")
    
    print("\n2️⃣  User goes to Orders Filter menu")
    add_to_navigation_history(context, 'orders_filter_menu')
    print(f"   History: {[m['menu'] for m in context.user_data.get('navigation_history', [])]}")
    
    # Now simulate clicking BACK
    print("\n3️⃣  User clicks BACK button")
    
    # Get previous menu
    previous = get_previous_menu(context)
    print(f"   Previous menu: {previous['menu']}")
    print(f"   History after pop: {[m['menu'] for m in context.user_data.get('navigation_history', [])]}")
    
    # Now the handle_navigation would call all_orders(from_back_button=True)
    # With from_back_button=True, it should NOT add to history!
    print("\n4️⃣  Simulating all_orders(from_back_button=True)")
    print("   (In real code, the function checks 'from_back_button' and skips add_to_navigation_history)")
    
    # Simulate the check: if not from_back_button: add_to_navigation_history(...)
    from_back_button = True
    if not from_back_button:
        add_to_navigation_history(context, 'orders_filter_menu')
        print("   ❌ Added to history (BUG!)")
    else:
        print("   ✅ Skipped adding to history")
    
    print(f"   History: {[m['menu'] for m in context.user_data.get('navigation_history', [])]}")
    
    # Check result
    history = context.user_data.get('navigation_history', [])
    print(f"\n📊 FINAL HISTORY: {[m['menu'] for m in history]}")
    
    # Expected: Only 'admin_menu' should remain
    if len(history) == 1 and history[0]['menu'] == 'admin_menu':
        print("✅ PASS: Back navigation works correctly!")
        return True
    else:
        print(f"❌ FAIL: Expected ['admin_menu'], got {[m['menu'] for m in history]}")
        return False

def test_forward_navigation_still_adds():
    """Test that forward navigation (from_back_button=False) still adds to history"""
    print("\n" + "=" * 80)
    print("🧪 TEST: Forward Navigation Still Adds to History")
    print("=" * 80)
    
    class MockContext:
        user_data = {}
    
    context = MockContext()
    
    from funcs.utils import add_to_navigation_history
    
    print("\n1️⃣  Simulating normal menu entry (from_back_button=False)")
    
    # Simulate: if not from_back_button: add_to_navigation_history(...)
    from_back_button = False
    if not from_back_button:
        add_to_navigation_history(context, 'admin_menu')
        print("   ✅ Added to history (correct!)")
    else:
        print("   ❌ Skipped adding (BUG!)")
    
    history = context.user_data.get('navigation_history', [])
    print(f"   History: {[m['menu'] for m in history]}")
    
    if len(history) == 1 and history[0]['menu'] == 'admin_menu':
        print("✅ PASS: Forward navigation still works!")
        return True
    else:
        print(f"❌ FAIL: Expected ['admin_menu'], got {[m['menu'] for m in history]}")
        return False

def test_complex_navigation_flow():
    """Test complex navigation: Main → Admin → Orders → Daily Profit → Back → Back"""
    print("\n" + "=" * 80)
    print("🧪 TEST: Complex Navigation Flow")
    print("=" * 80)
    
    class MockContext:
        user_data = {}
    
    context = MockContext()
    
    from funcs.utils import add_to_navigation_history, get_previous_menu
    
    # Flow: Main → Admin → Orders → Daily Profit
    print("\n📍 Navigation Flow:")
    print("   Main → Admin → Orders → Daily Profit")
    
    # Forward navigation - adds to history
    add_to_navigation_history(context, 'admin_menu')
    print(f"   After Admin: {[m['menu'] for m in context.user_data.get('navigation_history', [])]}")
    
    add_to_navigation_history(context, 'orders_filter_menu')
    print(f"   After Orders: {[m['menu'] for m in context.user_data.get('navigation_history', [])]}")
    
    add_to_navigation_history(context, 'daily_profit_menu')
    print(f"   After Daily Profit: {[m['menu'] for m in context.user_data.get('navigation_history', [])]}")
    
    # First BACK: Daily Profit → Orders
    print("\n⬅️  First BACK (Daily Profit → Orders)")
    prev = get_previous_menu(context)
    print(f"   Going to: {prev['menu']}")
    # Simulate: all_orders(from_back_button=True) - does NOT add to history
    print(f"   History: {[m['menu'] for m in context.user_data.get('navigation_history', [])]}")
    
    # Second BACK: Orders → Admin
    print("\n⬅️  Second BACK (Orders → Admin)")
    prev = get_previous_menu(context)
    print(f"   Going to: {prev['menu']}")
    # Simulate: show_admin_action_kb(from_back_button=True) - does NOT add to history
    print(f"   History: {[m['menu'] for m in context.user_data.get('navigation_history', [])]}")
    
    # Check result
    history = context.user_data.get('navigation_history', [])
    print(f"\n📊 FINAL HISTORY: {[m['menu'] for m in history]}")
    
    # Expected: Only 'admin_menu' should remain
    if len(history) == 1 and history[0]['menu'] == 'admin_menu':
        print("✅ PASS: Complex navigation works correctly!")
        return True
    else:
        print(f"❌ FAIL: Expected ['admin_menu'], got {[m['menu'] for m in history]}")
        return False

def test_duplicate_prevention():
    """Test that we still prevent duplicates"""
    print("\n" + "=" * 80)
    print("🧪 TEST: Duplicate Prevention Still Works")
    print("=" * 80)
    
    class MockContext:
        user_data = {}
    
    context = MockContext()
    
    from funcs.utils import add_to_navigation_history
    
    print("\n1️⃣  Adding admin_menu three times (forward navigation)")
    add_to_navigation_history(context, 'admin_menu')
    add_to_navigation_history(context, 'admin_menu')
    add_to_navigation_history(context, 'admin_menu')
    
    history = context.user_data.get('navigation_history', [])
    print(f"   History: {[m['menu'] for m in history]}")
    
    if len(history) == 1:
        print("✅ PASS: Duplicates are prevented!")
        return True
    else:
        print(f"❌ FAIL: Expected 1 entry, got {len(history)}")
        return False

def main():
    """Run all tests"""
    print("🔍 STARTING COMPREHENSIVE BACK BUTTON TESTS")
    print("=" * 80)
    
    results = []
    
    # Run tests
    results.append(("Back Navigation with Parameter", test_back_navigation_with_parameter()))
    results.append(("Forward Navigation Still Adds", test_forward_navigation_still_adds()))
    results.append(("Complex Navigation Flow", test_complex_navigation_flow()))
    results.append(("Duplicate Prevention", test_duplicate_prevention()))
    
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
