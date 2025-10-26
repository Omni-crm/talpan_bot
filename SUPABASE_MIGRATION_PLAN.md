# 🚀 תכנית מעבר למסד נתונים Supabase

## 📋 סקירה כללית
תכנית מפורטת למעבר ממסד נתונים SQLite (SQLAlchemy) ל-Supabase PostgreSQL.

---

## 🎯 שלב 1: הכנה ראשונית

### 1.1 יצירת פרויקט ב-Supabase
1. גש ל-[supabase.com](https://supabase.com)
2. התחבר או צור חשבון
3. לחץ על **"New Project"**
4. הזן פרטים:
   - Project Name: `talpan-bot-db`
   - Database Password: **[שמור את הסיסמה ב-.env]**
   - Region: `West Europe` (הכי קרוב ל-Railway)
   - Plan: **Free Tier**

### 1.2 קבלת פרטי התחברות
1. בפרויקט, לך ל-**Settings → Database**
2. הקודש ל-**Connection string** → **URI**
3. העתק את ה-Connection string (נראה כך: `postgresql://postgres:password@db.xxx.supabase.co:5432/postgres`)

### 1.3 עדכון משתני סביבה
עדכן את קובץ `.env`:
```env
# השלמת הדאטה ב-SUPABASE
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_DB_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres

# Legacy SQLite (ניתן להסיר אחרי המיגרציה)
DB_DIR=/data
DB_PATH=/data/database.db
```

---

## 🔧 שלב 2: התקנת תלויות

### 2.1 עדכון requirements.txt
```txt
# רק requests ל-API calls ל-Supabase
requests==2.31.0

# שמירת SQLAlchemy למקרה (יכול להישאר בשימוש)
# sqlalchemy==2.0.23 (כבר קיים)
```

### 2.2 התקנה
```bash
pip install requests
```

### 2.3 העדפה: Supabase Python Client
או, בחר להשתמש ב-[Supabase Python Client](https://github.com/supabase/supabase-py):

```txt
# חלופה נוחה יותר - גרסה חדשה
supabase==2.15.0
```

```bash
pip install supabase
```

---

## 📝 שלב 3: עדכון קוד בסיסי

### 3.1 יצירת wrapper חדש ל-Supabase

קובץ חדש: `db/supabase_client.py`

```python
"""
Supabase Client Wrapper
עבודה ישירה עם Supabase ללא תלויות נוספות מלבד requests
"""
import os
import requests
from typing import Optional, List, Dict, Any

class SupabaseClient:
    """Client עבור Supabase עם HTTP requests ישירים"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, table: str, data: Optional[Dict] = None) -> Any:
        """בצע HTTP request ל-Supabase"""
        url = f"{self.url}/rest/v1/{table}"
        response = requests.request(method, url, json=data, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def select(self, table: str, filters: Optional[Dict] = None) -> List[Dict]:
        """SELECT query"""
        url = f"{self.url}/rest/v1/{table}"
        params = filters or {}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def insert(self, table: str, data: Dict) -> Dict:
        """INSERT query"""
        url = f"{self.url}/rest/v1/{table}"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def update(self, table: str, data: Dict, filters: Optional[Dict] = None) -> Dict:
        """UPDATE query"""
        url = f"{self.url}/rest/v1/{table}"
        params = filters or {}
        response = requests.patch(url, headers=self.headers, json=data, params=params)
        response.raise_for_status()
        return response.json()
    
    def delete(self, table: str, filters: Optional[Dict] = None) -> Dict:
        """DELETE query"""
        url = f"{self.url}/rest/v1/{table}"
        params = filters or {}
        response = requests.delete(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json() if response.content else {}

# יצירת instance גלובלי
def get_supabase_client():
    """קבל Supabase client instance"""
    return SupabaseClient()
```

### 3.2 עדכון `db/db.py` להגדרת Client

```python
# הוספה לתחילת הקובץ
from .supabase_client import get_supabase_client

# בחר בין Supabase ל-SQLite
USE_SUPABASE = os.getenv("SUPABASE_URL") is not None

if USE_SUPABASE:
    db_client = get_supabase_client()
    print("✅ Using Supabase database")
else:
    db_client = None
    print("⚠️ Using SQLite database (local fallback)")
```

### 3.3 עדכון פונקציות לעבודה עם Supabase

```python
# דוגמה לעדכון פונקציה
async def get_user_by_id(user_id: int):
    if USE_SUPABASE:
        result = db_client.select('users', {'user_id': f'eq.{user_id}'})
        return result[0] if result else None
    else:
        session = Session()
        user = session.query(User).filter(User.user_id == user_id).first()
        session.close()
        return user.to_dict() if user else None

# דוגמה לכתיבה
async def create_user(user_data):
    if USE_SUPABASE:
        result = db_client.insert('users', user_data)
        return result
    else:
        session = Session()
        user = User(**user_data)
        session.add(user)
        session.commit()
        session.close()
```

---

## 🗄️ שלב 4: מיגרציה של schema

### 4.1 יצירת script מיגרציה
קובץ חדש: `scripts/migrate_to_supabase.py`

```python
"""
Script to migrate SQLite database to Supabase PostgreSQL
"""
import asyncio
from sqlalchemy import text
from db.db import Base, engine, SupabaseEngine

async def migrate_schema():
    """Create all tables in Supabase"""
    async with SupabaseEngine.begin() as conn:
        # Drop existing tables if they exist (careful in production!)
        await conn.run_sync(Base.metadata.drop_all)
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Schema migrated to Supabase!")

async def migrate_data():
    """Migrate data from SQLite to Supabase"""
    # This will be done manually or with a separate script
    print("ℹ️  Data migration to be done separately")
    pass

if __name__ == "__main__":
    asyncio.run(migrate_schema())
```

### 4.2 הרצה
```bash
python3 scripts/migrate_to_supabase.py
```

---

## 📊 שלב 5: מיגרציה של נתונים

### 5.1 יצירת script מיגרציה נתונים
קובץ חדש: `scripts/migrate_data.py`

```python
"""
Migrate data from SQLite to Supabase
"""
import asyncio
import json
from db.db import SQLiteSession, SupabaseSession
from db.db import User, Order, Product, BotSettings, TgSession, Shift

async def migrate_data():
    """Migrate all data from SQLite to Supabase"""
    
    # Read from SQLite (synchronous)
    with SQLiteSession() as sqlite_session:
        users = sqlite_session.query(User).all()
        orders = sqlite_session.query(Order).all()
        products = sqlite_session.query(Product).all()
        settings = sqlite_session.query(BotSettings).all()
        sessions = sqlite_session.query(TgSession).all()
        shifts = sqlite_session.query(Shift).all()
    
    # Write to Supabase (asynchronous)
    async with SupabaseSession() as supabase_session:
        # Migrate Users
        for user in users:
            supabase_session.add(User(**user.__dict__))
        
        # Migrate Orders
        for order in orders:
            supabase_session.add(Order(**order.__dict__))
        
        # Migrate Products
        for product in products:
            supabase_session.add(Product(**product.__dict__))
        
        # Migrate Settings
        for setting in settings:
            supabase_session.add(BotSettings(**setting.__dict__))
        
        # Migrate Sessions
        for session in sessions:
            supabase_session.add(TgSession(**session.__dict__))
        
        # Migrate Shifts
        for shift in shifts:
            supabase_session.add(Shift(**shift.__dict__))
        
        await supabase_session.commit()
    
    print("✅ Data migrated successfully!")

if __name__ == "__main__":
    asyncio.run(migrate_data())
```

---

## 🔄 שלב 6: עדכון handlers לקבל Async

### 6.1 דוגמה לעדכון handler
לפני:
```python
async def some_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = Session()
    user = session.query(User).filter(User.user_id == update.effective_user.id).first()
    # ...
    session.close()
```

אחרי:
```python
async def some_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with SessionLocal() as session:
        user = await session.query(User).filter(User.user_id == update.effective_user.id).first()
        # ...
        # No need to close - context manager handles it
```

---

## 🧪 שלב 7: בדיקות

### 7.1 בדיקות בסיסיות
1. **הרצת הבוט** - וודא שהבוט עובד
2. **יצירת משתמש חדש** - בדוק שהמשתמש נוצר ב-Supabase
3. **יצירת הזמנה** - ודא שההזמנה נשמרת
4. **פתיחת משמרת** - בדוק שהמשמרת נפתחת
5. **שליחת דוח** - ודא שהדוחות עובדים

### 7.2 בדיקת ביצועים
```bash
# בדיקת חיבור
python3 -c "from db.db import engine; print('Connected!' if engine else 'Failed')"

# בדיקת לוח מחוונים ב-Supabase
# לך ל-Supabase Dashboard → Table Editor → בדוק טבלאות
```

---

## 🚀 שלב 8: העלאה ל-Railway

### 8.1 עדכון railway.toml
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python3 bot.py"
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 10

[[services]]
name = "courier-bot"

[services.variables]
SUPABASE_DB_URL = "postgresql://postgres:password@db.xxx.supabase.co:5432/postgres"
SUPABASE_URL = "your-supabase-url"
SUPABASE_KEY = "your-supabase-key"

# ה-SQLite עדיין נשאר כ-fallback
DB_DIR = "/tmp"  # שינוי ל-tmp כי לא צריך persistence
DB_PATH = "/tmp/database.db"
```

### 8.2 עדכון requirements.txt (לדפלוי)
```txt
# Supabase Client - גרסה חדשה
supabase==2.15.0

# או אם מעדיפים רק HTTP requests:
# requests==2.31.0
```

### 8.3 העלאה ל-Railway
```bash
git add .
git commit -m "Migrate to Supabase PostgreSQL database"
git push origin main
```

---

## 🧹 שלב 9: ניקוי (אופציונלי)

### 9.1 הסרת SQLite fallback
אחרי שמוכח שהכל עובד:
1. הסר את `db/database.db` (SQLite)
2. הסר את משתני סביבה SQLite מ-railway.toml
3. עדכן את הקוד להסיר fallback logic

### 9.2 אופטימיזציות
- הוסף connection pooling
- הוסף retry logic למקרי שגיאה
- הוסף monitoring ב-Supabase Dashboard

---

## 📊 לוח זמנים משוער

| שלב | זמן משוער | תאריך יעד |
|-----|-----------|-----------|
| 1. הכנה | 30 דק' | Day 1 |
| 2. התקנת תלויות | 15 דק' | Day 1 |
| 3. עדכון קוד | 2-3 שעות | Day 1 |
| 4. מיגרציה של schema | 30 דק' | Day 1 |
| 5. מיגרציה של נתונים | 1 שעה | Day 1 |
| 6. עדכון handlers | 2-3 שעות | Day 1 |
| 7. בדיקות | 1 שעה | Day 1 |
| 8. העלאה ל-Railway | 30 דק' | Day 1 |
| 9. ניקוי | 30 דק' | Day 2 |

**סה"כ: ~8-10 שעות עבודה**

---

## ⚠️ נקודות חשובות

### לפני התחלה:
- ✅ צור backup של מסד הנתונים הישן
- ✅ צור פרויקט נפרד ב-Supabase לבדיקות
- ✅ ודא שיש גיבוי של כל הנתונים

### במהלך המיגרציה:
- ⚠️ אל תתקן בעיות במקביל - תסדר את המיגרציה תחילה
- ⚠️ שנה handler אחד בכל פעם
- ⚠️ בדוק אחרי כל שינוי

### אחרי המיגרציה:
- ✅ שמור את מסד הנתונים הישן לפחות שבוע
- ✅ ניטור ביצועים ב-Supabase Dashboard
- ✅ ודא שכל הפונקציונליות עובדת

---

## 📞 תמיכה

אם יש בעיות במהלך המיגרציה:
1. בדוק את ה-logs ב-Railway
2. בדוק את ה-console ב-Supabase Dashboard
3. השתמש ב-Supabase SQL Editor לבדיקות ידניות
4. אם צריך, חזור ל-SQLite (הסתר `SUPABASE_DB_URL` ב-env)

---

## ✅ סיכום

**מעבר ל-Supabase ישפר:**
- ✅ יציבות
- ✅ ביצועים
- ✅ תחזוקה
- ✅ גיבויים
- ✅ גישה מרחוק
- ✅ ניהול קל יותר

**מוכן להתחיל?** נתחיל בשלב 1! 🚀

