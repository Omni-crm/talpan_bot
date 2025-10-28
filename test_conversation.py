#!/usr/bin/env python3
"""Test the manage_stock conversation handler locally"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up basic config
os.environ['USE_SUPABASE'] = 'true'

from telegram.ext import Application
from handlers.manage_stock_handler import MANAGE_STOCK_HANDLER, manage_stock
from handlers.new_order_handler import NEW_ORDER_HANDLER
from config.config import BOT_TOKEN

async def test_handlers():
    """Test that handlers are properly configured"""
    
    print("🔧 Testing ConversationHandler configuration...")
    
    # Check MANAGE_STOCK_HANDLER
    print(f"\n📋 MANAGE_STOCK_HANDLER:")
    print(f"   Entry points: {len(MANAGE_STOCK_HANDLER.entry_points)}")
    for i, ep in enumerate(MANAGE_STOCK_HANDLER.entry_points):
        print(f"   - Entry {i}: {ep}")
    
    print(f"   States: {list(MANAGE_STOCK_HANDLER.states.keys())}")
    for state, handlers in MANAGE_STOCK_HANDLER.states.items():
        print(f"   - State {state}: {len(handlers)} handlers")
        for h in handlers:
            print(f"     * {h}")
    
    print(f"   Fallbacks: {len(MANAGE_STOCK_HANDLER.fallbacks)}")
    for i, fb in enumerate(MANAGE_STOCK_HANDLER.fallbacks):
        print(f"   - Fallback {i}: {fb}")
    
    print(f"   per_chat: {MANAGE_STOCK_HANDLER.per_chat}")
    print(f"   per_user: {MANAGE_STOCK_HANDLER.per_user}")
    print(f"   per_message: {MANAGE_STOCK_HANDLER.per_message}")
    
    # Check NEW_ORDER_HANDLER
    print(f"\n📋 NEW_ORDER_HANDLER:")
    print(f"   Entry points: {len(NEW_ORDER_HANDLER.entry_points)}")
    print(f"   States: {list(NEW_ORDER_HANDLER.states.keys())}")
    print(f"   per_chat: {NEW_ORDER_HANDLER.per_chat}")
    print(f"   per_user: {NEW_ORDER_HANDLER.per_user}")
    print(f"   per_message: {NEW_ORDER_HANDLER.per_message}")
    
    print("\n✅ Handler configuration test complete")
    
    # Now test with actual bot
    print("\n🤖 Creating bot application...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers in correct order
    print("📝 Adding MANAGE_STOCK_HANDLER first...")
    app.add_handler(MANAGE_STOCK_HANDLER)
    
    print("📝 Adding NEW_ORDER_HANDLER second...")
    app.add_handler(NEW_ORDER_HANDLER)
    
    print("\n✅ Handlers added successfully")
    print(f"   Total handlers: {len(app.handlers[0])}")
    
    print("\n🎯 Handler order:")
    for i, handler in enumerate(app.handlers[0]):
        print(f"   {i}. {type(handler).__name__}")

if __name__ == "__main__":
    asyncio.run(test_handlers())
