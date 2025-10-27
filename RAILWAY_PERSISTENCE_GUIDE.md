# 🗄️ מדריך Persistence ב-Railway - Courier Bot

## ✅ **הפתרון: Supabase Cloud Database**

המערכת עובדת עם Supabase PostgreSQL - מסד נתונים בנוי לענן ששורד redeployment ו-rebuild של Railway ללא צורך ב-volumes מקומיים.

## 🚀 **הגדרת Supabase ב-Railway**

### **שלב 1: הוספת Environment Variables**

1. **היכנס ל-Railway Dashboard:**
   - לך לפרויקט `courier-bot`
   - לחץ על השירות `courier-bot`

2. **לך ל-Settings → Variables**
   - לחץ **"New Variable"**

3. **הוסף את ה-Variables הבאים:**

```
# SUPABASE - REQUIRED
SUPABASE_URL = https://your-project.supabase.co
SUPABASE_ANON_KEY = your_anon_key
SUPABASE_SECRET_KEY = your_service_role_key

# BOT - REQUIRED
BOT_TOKEN = your_bot_token

# OPTIONAL
ADMIN_ID = your_admin_id
ADMIN_CHAT = -1001234567890
ORDER_CHAT = -1009876543210
API_ID = your_api_id
API_HASH = your_api_hash
```

### **שלב 2: קבלת פרטי Supabase**

1. **היכנס ל-Supabase Dashboard:**
   - https://app.supabase.com/projects/your-project

2. **Settings → API:**
   - העתק את `Project URL` → `SUPABASE_URL`
   - העתק את `anon public` key → `SUPABASE_ANON_KEY`
   - העתק את `service_role` key → `SUPABASE_SECRET_KEY`

### **שלב 3: מבנה הטבלאות ב-Supabase**

המערכת משתמשת בטבלאות הבאות:
- `users` - משתמשים
- `products` - מוצרים
- `orders` - הזמנות
- `shifts` - משמרות
- `bot_settings` - הגדרות
- `templates` - תבניות
- `tgsessions` - sessions של Telegram

כל הטבלאות נוצרות אוטומטית עם הפעלה ראשונה של הבוט.

### **שלב 4: Deploy**

1. **Push את הקוד:**
   ```bash
   git push origin main
   ```

2. **Railway יבנה מחדש אוטומטית**

3. **בדוק שה-DB מחובר:**
   - לך ל-**"Logs"** של השירות
   - חפש: `✅ Using Supabase database`

## 🔍 **איך זה עובד**

### **חיבור ישיר ל-Supabase:**
```python
# db/supabase_client.py
class SupabaseClient:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY")
        
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }
```

כל הפעולות (SELECT, INSERT, UPDATE, DELETE) מתבצעות דרך HTTP requests ישירים ל-Supabase REST API.

## ✅ **בדיקות**

### **1. בדוק שה-Supabase מחובר:**
```bash
# ב-Railway Logs, חפש:
"✅ Using Supabase database"
"✅ Supabase Client initialized: https://..."
```

### **2. בדוק שה-DB עובד:**
- צור הזמנה חדשה
- בדוק שהיא נשמרת
- Redeploy
- בדוק שההזמנה עדיין קיימת

### **3. בדוק persistence:**
- הוסף מוצר חדש
- Redeploy
- בדוק שהמוצר עדיין קיים

## 🚨 **אם משהו לא עובד**

### **בעיה: "SUPABASE_URL not set"**
**פתרון:**
1. בדוק שה-Variable `SUPABASE_URL` קיים
2. בדוק שהוא מכיל את ה-URL הנכון
3. Redeploy

### **בעיה: "401 Unauthorized"**
**פתרון:**
1. בדוק שה-Variable `SUPABASE_ANON_KEY` נכון
2. בדוק שזה ה-anon key (לא service_role)
3. וודא שה-RLS policies ב-Supabase מתירים גישה

### **בעיה: נתונים לא נשמרים**
**פתרון:**
1. בדוק שה-tables קיימות ב-Supabase
2. בדוק שה-RLS policies מתירים INSERT/UPDATE
3. בדוק Logs לשגיאות

## 📊 **יתרונות הפתרון**

✅ **Persistence מלא** - כל הנתונים ב-Supabase הקלוד  
✅ **Backup אוטומטי** - Supabase עושה backup אוטומטי  
✅ **Scalability** - ניתן להגדיל capacity לפי הצורך  
✅ **Zero Downtime** - redeployment לא משפיע על נתונים  
✅ **No Volumes** - אין צורך ב-volumes מקומיים  
✅ **Cloud Native** - מסד נתונים מושלם לבנייה מסוג זה  

## 🔄 **Migration מנתונים קיימים**

אם יש לך נתונים קיימים ב-SQLite:

1. **Export מה-DB הקיים:**
   ```bash
   sqlite3 database.db ".dump" > backup.sql
   ```

2. **Import ל-Supabase:**
   - השתמש ב-Supabase Dashboard → SQL Editor
   - או השתמש ב-pg_dump/pg_restore

## 📝 **סיכום**

עם Supabase, ה-database **ישרוד** כל redeployment ו-rebuild. כל הנתונים (הזמנות, משתמשים, מוצרים, משמרות) יישמרו לצמיתות ב-cloud database.

**זמן יישום:** 5 דקות  
**מורכבות:** נמוכה  
**סיכון:** נמוך  
**תלות:** רק ב-Supabase credentials
