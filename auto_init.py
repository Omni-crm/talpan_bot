#!/usr/bin/env python3
"""
סקריפט אתחול אוטומטי עם הערכים המוכנים
"""

import asyncio
import sys
import os

# הוספת הנתיב לפרויקט
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.db import (
    initialize_default_settings, 
    set_bot_setting, 
    set_bot_setting_list,
    resolve_chat_identifier
)

async def auto_init():
    """אתחול אוטומטי עם הערכים המוכנים"""
    print("🚀 מתחיל אתחול אוטומטי...")
    
    # Ensure all tables are created first (Supabase managed)
    print("📊 Database tables managed in Supabase...")
    print("✅ Supabase - tables managed in cloud")
    
    # אתחול הגדרות ברירת מחדל
    initialize_default_settings()
    print("✅ הגדרות ברירת מחדל נוצרו")
    
    # הגדרות מוכנות מראש
    print("\n🔧 מגדיר הגדרות מוכנות...")
    
    # טוקן הבוט
    bot_token = "8447859572:AAFbcJ8HF6yh074Xd2p3yPxugmHJPx0f4DU"
    set_bot_setting('bot_token', bot_token, description='טוקן הבוט')
    print("✅ טוקן הבוט נשמר")
    
    # מנהלים
    admin_ids = [1899612463, 5649994883]  # List of admin IDs
    set_bot_setting_list('admins', admin_ids, description='רשימת מנהלים')
    print(f"✅ מנהלים נשמרו: {admin_ids}")
    
    # הגדרות נוספות (אופציונליות)
    print("\n📝 מגדיר הגדרות נוספות...")
    
    # API credentials (אופציונלי)
    api_id = os.getenv('API_ID', '')
    if api_id:
        set_bot_setting('api_id', api_id, description='API ID')
        print("✅ API ID נשמר")
    
    api_hash = os.getenv('API_HASH', '')
    if api_hash:
        set_bot_setting('api_hash', api_hash, description='API Hash')
        print("✅ API Hash נשמר")
    
    # =========================================
    # ⚠️ IMPORTANT: לא לדרוס ערכים מה-ENV!
    # =========================================
    # קבוצות (order_chat, admin_chat) מנוהלות רק דרך הבוט!
    # לא טוענים מ-ENV בכלל!
    
    print("\n💾 Group chats and dynamic users are managed via bot UI only!")
    print("   - order_chat: Set via bot → Admin → Change group links")
    print("   - admin_chat: Set via bot → Admin → Change group links")
    print("   - operators, stockmen, couriers: Set via bot → Manage roles")
    print("\n🔒 Only ADMINS list is loaded from ENV (unchangeable):")
    
    # רק ADMINS מ-ENV (קבוע)
    try:
        admins_env = os.getenv('ADMINS', '')
        if admins_env:
            admin_list = [int(x.strip()) for x in admins_env.split(',') if x.strip()]
            # בדיקה אם רשימת מנהלים קיימת כבר
            existing = db_client.select('bot_settings', {'key': 'admins'})
            if existing:
                print(f"   ✅ ADMINS from ENV: {admin_list} (already in DB, not overwriting)")
            else:
                set_bot_setting_list('admins', admin_list, description='רשימת מנהלים ראשית')
                print(f"   ✅ ADMINS from ENV saved to DB: {admin_list}")
    except ValueError:
        print("   ⚠️ Error in ADMINS format")
    
    # ⚠️ אין יותר טעינה אוטומטית של operators, stockmen, couriers מ-ENV!
    # אלה מנוהלים רק דרך UI הבוט!
            
    print("\n🎉 אתחול אוטומטי הושלם בהצלחה!")
    print("💾 רק BOT_TOKEN + ADMINS נטענו מ-ENV")
    print("💾 כל השאר (קבוצות, משתמשים) מנוהל דרך UI הבוט")
    print("🚀 הבוט מוכן להפעלה!")
    print(f"👑 מנהלים מ-ENV: {admin_ids}")
    print(f"🤖 טוקן הבוט: {bot_token[:10]}...")

if __name__ == "__main__":
    asyncio.run(auto_init())
