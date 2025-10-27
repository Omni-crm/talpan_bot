אני# 🗄️ מדריך הגדרות מסד נתונים

## 📋 סקירה כללית

המערכת משתמשת ב-Supabase כמסד הנתונים, מה שמבטיח:
- ✅ **עמידות**: הגדרות נשמרות ב-Supabase הקלוד
- ✅ **גמישות**: עדכון הגדרות ללא restart
- ✅ **אבטחה**: אין חשיפה של הגדרות ב-Git
- ✅ **Cloud Database**: Supabase PostgreSQL
- ✅ **No Local Files**: אין תלות בקבצי DB מקומיים

## 🚀 הגדרה ראשונית

### 1. הפעלת סקריפט האתחול
```bash
python3 init_settings.py
```

### 2. הזנת הערכים
הסקריפט יבקש ממך להזין:
- 🤖 **BOT_TOKEN**: טוקן הבוט
- 🔑 **API_ID**: מזהה API
- 🔐 **API_HASH**: Hash של API
- 👥 **ADMIN_CHAT**: קבוצת מנהלים (ID או @username)
- 📦 **ORDER_CHAT**: קבוצת שליחים (ID או @username)
- 👑 **ADMINS**: רשימת מנהלים (user IDs)
- ⚙️ **OPERATORS**: רשימת מפעילים (user IDs)
- 📦 **STOCKMEN**: רשימת מחסנאים (user IDs)
- 🚚 **COURIERS**: רשימת שליחים (user IDs)

## 🔧 פונקציות מתקדמות

### פתרון Username ל-ID
```python
from db.db import resolve_chat_identifier

# המרת username ל-ID
user_id = await resolve_chat_identifier("@username")
group_id = await resolve_chat_identifier("@groupname")
```

### ניהול הגדרות
```python
from db.db import get_bot_setting, set_bot_setting, get_bot_setting_list, set_bot_setting_list

# קבלת הגדרה
admin_chat = get_bot_setting('admin_chat')

# עדכון הגדרה
set_bot_setting('admin_chat', '-1001234567890', user_id=123456)

# ניהול רשימות
admins = get_bot_setting_list('admins')
set_bot_setting_list('admins', [123456, 789012], user_id=123456)
```

## 🚂 Railway Deployment

### 1. יצירת Railway Volume
1. היכנס ל-Railway Dashboard
2. בחר את הפרויקט
3. עבור ל-Volumes
4. צור Volume חדש עם path: `/data`

### 2. הגדרת Environment Variables
```bash
# רק הגדרות בסיסיות (השאר נשמר במסד נתונים)
BOT_TOKEN=your_bot_token
API_ID=your_api_id
API_HASH=your_api_hash
```

### 3. אתחול הגדרות
לאחר ה-deployment הראשון, הפעל:
```bash
python3 init_settings.py
```

## 📊 מבנה מסד הנתונים

### טבלת BotSettings
```sql
CREATE TABLE bot_settings (
    id INTEGER PRIMARY KEY,
    key VARCHAR(50) UNIQUE NOT NULL,
    value VARCHAR(500) NOT NULL,
    value_type VARCHAR(20) DEFAULT 'string',
    description VARCHAR(200),
    updated_at DATETIME,
    updated_by BIGINT
);
```

### הגדרות נפוצות
- `admin_chat`: קבוצת מנהלים
- `order_chat`: קבוצת שליחים
- `bot_token`: טוקן הבוט
- `api_id`: API ID
- `api_hash`: API Hash
- `admins`: רשימת מנהלים (JSON)
- `operators`: רשימת מפעילים (JSON)
- `stockmen`: רשימת מחסנאים (JSON)
- `couriers`: רשימת שליחים (JSON)

## 🔄 עדכון הגדרות

### דרך הבוט
```python
# עדכון קבוצת מנהלים
await update.effective_message.reply_text("הזן ID או @username של קבוצת מנהלים:")
# הבוט יקלוט ויעדכן אוטומטית
```

### דרך קוד
```python
from db.db import set_bot_setting, resolve_chat_identifier

# עדכון עם המרת username
new_chat_id = await resolve_chat_identifier("@new_admin_group")
set_bot_setting('admin_chat', new_chat_id, user_id=123456)
```

## 🛡️ אבטחה

### הגנה על הגדרות
- כל ההגדרות נשמרות במסד הנתונים
- אין חשיפה של `.env` ב-Git
- Railway Volumes מבטיחים עמידות

### גיבוי
```bash
# גיבוי מסד נתונים
cp /data/database.db /backup/database_$(date +%Y%m%d).db
```

## 🚨 פתרון בעיות

### בעיה: "Chat not found"
**פתרון**: בדוק שהקבוצה קיימת והבוט חבר בה

### בעיה: הגדרות לא נשמרות
**פתרון**: ודא ש-Railway Volume מחובר ל-`/data`

### בעיה: שגיאות אתחול
**פתרון**: הפעל `python3 init_settings.py` שוב

## 📈 יתרונות המערכת החדשה

1. **עמידות**: הגדרות נשמרות גם אחרי redeployment
2. **גמישות**: עדכון ללא restart
3. **אבטחה**: אין חשיפה ב-Git
4. **ניהול**: ממשק נוח לעדכון הגדרות
5. **גיבוי**: מסד נתונים ניתן לגיבוי
6. **Railway**: תמיכה מלאה ב-Railway Volumes

## 🎯 סיכום

המערכת החדשה מספקת פתרון מקיף לניהול הגדרות:
- ✅ שמירה במסד נתונים
- ✅ עמידות ב-Railway
- ✅ המרת username ל-ID
- ✅ ניהול רשימות משתמשים
- ✅ עדכון דינמי
- ✅ אבטחה משופרת

הבוט מוכן להפעלה עם כל ההגדרות החדשות! 🚀
