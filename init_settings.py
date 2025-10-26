#!/usr/bin/env python3
"""
סקריפט לאתחול הגדרות במסד הנתונים
מאפשר להגדיר את כל ההגדרות מראש
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

async def init_settings():
    """אתחול הגדרות במסד הנתונים"""
    print("🚀 מתחיל אתחול הגדרות...")
    
    # בדיקה שהמסד נתונים לא ב-Git
    import os
    if os.path.exists('.git') and os.path.exists('database.db'):
        print("⚠️  אזהרה: מסד נתונים קיים בפרויקט Git!")
        print("   ודא שהוא ב-.gitignore ולא יועלה ל-Git")
        response = input("האם להמשיך? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ ביטול אתחול")
            return
    
    # אתחול הגדרות ברירת מחדל
    initialize_default_settings()
    print("✅ הגדרות ברירת מחדל נוצרו")
    
    # הגדרות מוכנות מראש
    print("\n🔧 מגדיר הגדרות מוכנות...")
    
    # טוקן הבוט
    bot_token = "8447859572:AAFbcJ8HF6yh074Xd2p3yPxugmHJPx0f4DU"
    set_bot_setting('bot_token', bot_token, description='טוקן הבוט')
    print("✅ טוקן הבוט נשמר")
    
    # מנהל ראשי
    admin_id = 1899612463
    set_bot_setting_list('admins', [admin_id], description='רשימת מנהלים')
    print(f"✅ מנהל ראשי נשמר: {admin_id}")
    
    # קבלת הגדרות נוספות
    print("\n📝 הזן הגדרות נוספות (אופציונלי):")
    
    # קבלת API credentials
    api_id = input("🔑 API_ID (אופציונלי): ").strip()
    if api_id:
        set_bot_setting('api_id', api_id, description='API ID')
        print("✅ API ID נשמר")
    
    api_hash = input("🔐 API_HASH (אופציונלי): ").strip()
    if api_hash:
        set_bot_setting('api_hash', api_hash, description='API Hash')
        print("✅ API Hash נשמר")
    
    # קבלת קבוצות
    admin_chat = input("👥 ADMIN_CHAT (ID או @username, אופציונלי): ").strip()
    if admin_chat:
        # ניסיון להמיר ל-ID
        try:
            resolved_id = await resolve_chat_identifier(admin_chat, bot_token)
            set_bot_setting('admin_chat', resolved_id, description='קבוצת מנהלים')
            print(f"✅ קבוצת מנהלים נשמרה: {resolved_id}")
        except Exception as e:
            set_bot_setting('admin_chat', admin_chat, description='קבוצת מנהלים')
            print(f"⚠️ קבוצת מנהלים נשמרה כ-username: {admin_chat}")
    
    order_chat = input("📦 ORDER_CHAT (ID או @username, אופציונלי): ").strip()
    if order_chat:
        try:
            resolved_id = await resolve_chat_identifier(order_chat, bot_token)
            set_bot_setting('order_chat', resolved_id, description='קבוצת שליחים')
            print(f"✅ קבוצת שליחים נשמרה: {resolved_id}")
        except Exception as e:
            set_bot_setting('order_chat', order_chat, description='קבוצת שליחים')
            print(f"⚠️ קבוצת שליחים נשמרה כ-username: {order_chat}")
    
    # קבלת רשימות משתמשים נוספים
    print("\n👤 הזן משתמשים נוספים (אופציונלי):")
    
    operators = input("⚙️ OPERATORS (user IDs, מופרדים בפסיקים): ").strip()
    if operators:
        try:
            operator_list = [int(x.strip()) for x in operators.split(',') if x.strip()]
            set_bot_setting_list('operators', operator_list, description='רשימת מפעילים')
            print(f"✅ מפעילים נשמרו: {operator_list}")
        except ValueError:
            print("❌ שגיאה בפורמט רשימת מפעילים")
    
    stockmen = input("📦 STOCKMEN (user IDs, מופרדים בפסיקים): ").strip()
    if stockmen:
        try:
            stockman_list = [int(x.strip()) for x in stockmen.split(',') if x.strip()]
            set_bot_setting_list('stockmen', stockman_list, description='רשימת מחסנאים')
            print(f"✅ מחסנאים נשמרו: {stockman_list}")
        except ValueError:
            print("❌ שגיאה בפורמט רשימת מחסנאים")
    
    couriers = input("🚚 COURIERS (user IDs, מופרדים בפסיקים): ").strip()
    if couriers:
        try:
            courier_list = [int(x.strip()) for x in couriers.split(',') if x.strip()]
            set_bot_setting_list('couriers', courier_list, description='רשימת שליחים')
            print(f"✅ שליחים נשמרו: {courier_list}")
        except ValueError:
            print("❌ שגיאה בפורמט רשימת שליחים")
    
    print("\n🎉 אתחול הושלם בהצלחה!")
    print("💾 כל ההגדרות נשמרו במסד הנתונים")
    print("🚀 הבוט מוכן להפעלה!")

if __name__ == "__main__":
    asyncio.run(init_settings())
