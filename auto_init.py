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
    
    # קבוצות (אופציונלי)
    admin_chat = os.getenv('ADMIN_CHAT', '')
    if admin_chat:
        try:
            resolved_id = await resolve_chat_identifier(admin_chat, bot_token)
            set_bot_setting('admin_chat', resolved_id, description='קבוצת מנהלים')
            print(f"✅ קבוצת מנהלים נשמרה: {resolved_id}")
        except Exception as e:
            set_bot_setting('admin_chat', admin_chat, description='קבוצת מנהלים')
            print(f"⚠️ קבוצת מנהלים נשמרה כ-username: {admin_chat}")
    
    order_chat = os.getenv('ORDER_CHAT', '')
    if order_chat:
        try:
            resolved_id = await resolve_chat_identifier(order_chat, bot_token)
            set_bot_setting('order_chat', resolved_id, description='קבוצת שליחים')
            print(f"✅ קבוצת שליחים נשמרה: {resolved_id}")
        except Exception as e:
            set_bot_setting('order_chat', order_chat, description='קבוצת שליחים')
            print(f"⚠️ קבוצת שליחים נשמרה כ-username: {order_chat}")
    
    # רשימות משתמשים נוספים (אופציונלי)
    try:
        admins_env = os.getenv('ADMINS', '')
        if admins_env:
            admin_list = [int(x.strip()) for x in admins_env.split(',') if x.strip()]
            set_bot_setting_list('admins', admin_list, description='רשימת מנהלים')
            print(f"✅ מנהלים נוספים נשמרו: {admin_list}")
    except ValueError:
        print("⚠️ שגיאה בפורמט רשימת מנהלים")
    
    try:
        operators_env = os.getenv('OPERATORS', '')
        if operators_env:
            operator_list = [int(x.strip()) for x in operators_env.split(',') if x.strip()]
            set_bot_setting_list('operators', operator_list, description='רשימת מפעילים')
            print(f"✅ מפעילים נשמרו: {operator_list}")
    except ValueError:
        print("⚠️ שגיאה בפורמט רשימת מפעילים")
    
    try:
        stockmen_env = os.getenv('STOCKMEN', '')
        if stockmen_env:
            stockman_list = [int(x.strip()) for x in stockmen_env.split(',') if x.strip()]
            set_bot_setting_list('stockmen', stockman_list, description='רשימת מחסנאים')
            print(f"✅ מחסנאים נשמרו: {stockman_list}")
    except ValueError:
        print("⚠️ שגיאה בפורמט רשימת מחסנאים")
    
    try:
        couriers_env = os.getenv('COURIERS', '')
        if couriers_env:
            courier_list = [int(x.strip()) for x in couriers_env.split(',') if x.strip()]
            set_bot_setting_list('couriers', courier_list, description='רשימת שליחים')
            print(f"✅ שליחים נשמרו: {courier_list}")
    except ValueError:
        print("⚠️ שגיאה בפורמט רשימת שליחים")
    
    print("\n🎉 אתחול אוטומטי הושלם בהצלחה!")
    print("💾 כל ההגדרות נשמרו במסד הנתונים")
    print("🚀 הבוט מוכן להפעלה!")
    print(f"👑 מנהלים: {admin_ids}")
    print(f"🤖 טוקן הבוט: {bot_token[:10]}...")

if __name__ == "__main__":
    asyncio.run(auto_init())
