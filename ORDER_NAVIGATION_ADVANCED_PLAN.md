# מערכת ניווט מתקדמת להזמנה חדשה

## 📋 מבוא

מערכת ההזמנה החדשה היא מורכבת עם אפשרות להוסיף/ערוך מוצרים מרובים. כל מוצר עובר תהליך של בחירה → כמות → מחיר, ויש אפשרות לערוך מוצרים קיימים או להוסיף חדשים.

**האתגר:** כפתור "חזור" צריך לעבוד בכל מצב ומכל שלב, עם אפשרות לניווט בין מוצרים שונים ולביטול פעולות.

## 🏗️ ארכיטקטורת המצבים

### מצבי הזמנה ברמה הגבוהה

```python
class OrderStates:
    NAME = 1           # הזנת שם לקוח
    USERNAME = 2       # הזנת @username
    PHONE = 3          # הזנת טלפון
    ADDRESS = 4        # הזנת כתובת
    PRODUCT_LIST = 5   # רשימת מוצרים + אפשרות הוספה/עריכה
    CONFIRMATION = 6   # אישור סופי של ההזמנה
```

### מצבי מוצר (לכל מוצר בנפרד)

```python
class ProductStates:
    SELECT_PRODUCT = 10    # בחירת מוצר מהרשימה
    ENTER_QUANTITY = 11    # הזנת כמות
    ENTER_PRICE = 12       # הזנת מחיר ליחידה
    CONFIRM_PRODUCT = 13   # אישור המוצר להזמנה
```

### מצבי עריכה (למוצר קיים)

```python
class EditStates:
    SELECT_EDIT_ACTION = 20   # בחירת מה לערוך (כמות/מחיר/מחיקה)
    EDIT_QUANTITY = 21        # עריכת כמות
    EDIT_PRICE = 22           # עריכת מחיר
    CONFIRM_EDIT = 23         # אישור השינויים
```

## 💾 מבנה הנתונים

```python
context.user_data["collect_order_data"] = {
    # נתוני לקוח בסיסיים
    "customer": {
        "name": "שם",
        "username": "@user",
        "phone": "055-1234567",
        "address": "כתובת"
    },

    # רשימת מוצרים
    "products": [
        {
            "id": 1,
            "name": "חלב",
            "quantity": 2,
            "unit_price": 5.0,
            "total_price": 10.0
        },
        {
            "id": 2,
            "name": "לחם",
            "quantity": 1,
            "unit_price": 8.0,
            "total_price": 8.0
        }
    ],

    # מצב נוכחי של ההזמנה
    "current_state": OrderStates.PRODUCT_LIST,

    # מוצר שנמצא כרגע בעריכה/הוספה
    "active_product": {
        "index": 1,  # אינדקס ברשימת products (-1 = מוצר חדש)
        "state": ProductStates.ENTER_QUANTITY,
        "temp_data": {
            "selected_product_id": 3,
            "name": "ביצים",
            "quantity": None,
            "unit_price": None
        }
    },

    # היסטוריית ניווט
    "navigation_stack": [
        {"type": "order", "state": OrderStates.NAME, "timestamp": "..."},
        {"type": "order", "state": OrderStates.USERNAME, "timestamp": "..."},
        {"type": "order", "state": OrderStates.PHONE, "timestamp": "..."},
        {"type": "order", "state": OrderStates.ADDRESS, "timestamp": "..."},
        {"type": "order", "state": OrderStates.PRODUCT_LIST, "timestamp": "..."},
        {"type": "product", "product_index": 1, "state": ProductStates.SELECT_PRODUCT, "timestamp": "..."},
        {"type": "product", "product_index": 1, "state": ProductStates.ENTER_QUANTITY, "timestamp": "..."}
    ]
}
```

## 🔄 לוגיקת הניווט

### עקרון בסיסי: Navigation Stack

כל פעולה דוחפת למחסנית (stack) את המצב הנוכחי. כפתור "חזור" מוציא את המצב העליון וחוזר למצב הקודם.

### סוגי מצבים במחסנית

1. **order** - מצבי הזמנה כלליים
2. **product** - הוספת/עריכת מוצר ספציפי
3. **edit** - עריכה של מוצר קיים

## 📋 תרחישים מפורטים

### תרחיש 1: הזמנה רגילה עם מוצר אחד

```
שם → טלפון → כתובת → בחר מוצר → כמות → מחיר → אישור
↑     ↑        ↑        ↑           ↑       ↑
```

**חזרה מכל שלב:** חזור לשלב הקודם

### תרחיש 2: הוספת מוצר שני

```
מוצר 1 הושלם → הוסף עוד? → בחר מוצר 2 → כמות 2 → מחיר 2 → אישור 2
                    ↑            ↑             ↑          ↑
```

**חזרה מבחירת מוצר 2:** חזור ל"הוסף עוד?"
**חזרה מכמות 2:** חזור לבחירת מוצר 2

### תרחיש 3: עריכת מוצר ראשון אחרי הוספת מוצר שני

```
מוצר 2 הושלם → ערוך מוצר 1 → מה לערוך? → שנה כמות → חדש: 3 → אישור
                      ↑               ↑              ↑           ↑
```

**חזרה משינוי כמות:** חזור ל"מה לערוך?"
**חזרה מ"מה לערוך?":** חזור לרשימת מוצרים

### תרחיש 4: ביטול הוספת מוצר באמצע

```
מוצר 1 ✓ → הוסף מוצר 2 → בחר מוצר → כמות: 5 → ❌ חזור ← ביטול הוספה
                                                    ↑
```

**חזרה מבחירת מוצר:** מוצר 2 נמחק, חזור ל"הוסף עוד?"
**חזרה מכמות:** נשאר בבחירת מוצר (לא מבטל)

### תרחיש 5: עריכה מורכבת עם מוצרים מרובים

```
מוצרים: [A, B, C, D]
ערוך C → שנה כמות → 10 → אישור → ערוך A → שנה מחיר → 15 → אישור
         ↑                       ↑                      ↑
```

**חזרה מ"שנה מחיר" A:** חזור ל"מה לערוך?" A
**חזרה מ"מה לערוך?" A:** חזור לרשימת מוצרים
**חזרה מרשימת מוצרים:** חזור ל"מה לערוך?" C (היה לפני)

### תרחיש 6: יציאה מאמצע עריכה

```
ערוך מוצר B → שנה מחיר → מחיר חדש: 20 → ❌ חזור ← ביטול השינויים
                     ↑
```

**חזרה ממחיר חדש:** השינויים לא נשמרו, חזור ל"מה לערוך?"

### תרחיש 7: ניווט בין מוצרים שונים

```
רשימת מוצרים → ערוך B → ביטול → ערוך D → שנה כמות → חזור → ערוך A
                   ↑            ↑            ↑             ↑
```

כל חזרה מחזירה למצב הקודם

## 🛠️ יישום טכני

### פונקציית push_to_navigation_stack

```python
def push_navigation_state(context, state_type, state_data):
    """דוחף מצב חדש למחסנית הניווט"""
    if "navigation_stack" not in context.user_data["collect_order_data"]:
        context.user_data["collect_order_data"]["navigation_stack"] = []

    stack = context.user_data["collect_order_data"]["navigation_stack"]

    # דחוף את המצב הנוכחי
    stack.append({
        "type": state_type,
        "timestamp": datetime.now(),
        **state_data
    })

    # הגבל לגודל מקסימלי
    if len(stack) > 20:  # יותר מ-20 שלבים אחורה
        stack.pop(0)
```

### פונקציית step_back משופרת

```python
async def step_back(update, context):
    """חזרה חכמה עם טיפול בכל התרחישים"""

    stack = context.user_data["collect_order_data"]["navigation_stack"]

    if len(stack) <= 1:
        # אין אחורה - סגור הזמנה
        return await end_order_conversation(update, context)

    # הוצא את המצב הנוכחי
    current_state = stack.pop()

    # קבל את המצב הקודם
    previous_state = stack[-1]

    # טפל לפי סוג המצב הקודם
    if previous_state["type"] == "order":
        return await restore_order_state(update, context, previous_state)

    elif previous_state["type"] == "product":
        return await restore_product_state(update, context, previous_state)

    elif previous_state["type"] == "edit":
        return await restore_edit_state(update, context, previous_state)
```

### טיפול במצבי order

```python
async def restore_order_state(update, context, state_data):
    """שחזור מצב הזמנה כללי"""
    state = state_data["state"]

    if state == OrderStates.NAME:
        return await show_enter_name(update, context)

    elif state == OrderStates.USERNAME:
        return await show_enter_username(update, context)

    elif state == OrderStates.PHONE:
        return await show_enter_phone(update, context)

    elif state == OrderStates.ADDRESS:
        return await show_enter_address(update, context)

    elif state == OrderStates.PRODUCT_LIST:
        return await show_product_list(update, context)
```

### טיפול במצבי product

```python
async def restore_product_state(update, context, state_data):
    """שחזור מצב הוספת מוצר"""
    product_index = state_data["product_index"]
    state = state_data["state"]

    # טען את נתוני המוצר
    active_product = context.user_data["collect_order_data"]["active_product"]
    active_product["index"] = product_index
    active_product["state"] = state

    if state == ProductStates.SELECT_PRODUCT:
        return await show_product_selection(update, context)

    elif state == ProductStates.ENTER_QUANTITY:
        return await show_quantity_input(update, context)

    elif state == ProductStates.ENTER_PRICE:
        return await show_price_input(update, context)
```

### טיפול במצבי edit

```python
async def restore_edit_state(update, context, state_data):
    """שחזור מצב עריכת מוצר"""
    product_index = state_data["product_index"]
    state = state_data["state"]

    # טען את נתוני העריכה
    active_product = context.user_data["collect_order_data"]["active_product"]
    active_product["index"] = product_index
    active_product["state"] = state

    if state == EditStates.SELECT_EDIT_ACTION:
        return await show_edit_options(update, context)

    elif state == EditStates.EDIT_QUANTITY:
        return await show_edit_quantity(update, context)

    elif state == EditStates.EDIT_PRICE:
        return await show_edit_price(update, context)
```

## 🔄 זרימת נתונים

### בעת התחלת הוספת מוצר

```python
def start_adding_product(context, product_index):
    """מתחיל הוספת מוצר חדש"""
    context.user_data["collect_order_data"]["active_product"] = {
        "index": product_index,  # -1 for new product
        "state": ProductStates.SELECT_PRODUCT,
    }

    # הוסף ל-navigation stack
    push_navigation_state(context, "product", {
        "product_index": product_index,
        "state": ProductStates.SELECT_PRODUCT
    })
```

### בעת התחלת עריכת מוצר

```python
def start_editing_product(context, product_index):
    """מתחיל עריכת מוצר קיים"""
    context.user_data["collect_order_data"]["active_product"] = {
        "index": product_index,
        "state": EditStates.SELECT_EDIT_ACTION,
        "original_data": context.user_data["collect_order_data"]["products"][product_index].copy()
    }

    # הוסף ל-navigation stack
    push_navigation_state(context, "edit", {
        "product_index": product_index,
        "state": EditStates.SELECT_EDIT_ACTION
    })
```

### בעת מעבר בין שלבים

```python
def move_to_next_step(context, new_state):
    """מעבר לשלב הבא עם שמירה ב-stack"""
    # עדכן את המצב הנוכחי
    if "active_product" in context.user_data["collect_order_data"]:
        context.user_data["collect_order_data"]["active_product"]["state"] = new_state

        # דחוף למחסנית
        active = context.user_data["collect_order_data"]["active_product"]
        push_navigation_state(context, active.get("edit_mode", False) and "edit" or "product", {
            "product_index": active["index"],
            "state": new_state
        })
```

## ✅ דוגמאות קונקרטיות

### דוגמה 1: הוספת 3 מוצרים עם חזרות

```
Navigation Stack:
1. order: NAME
2. order: USERNAME  
3. order: PHONE
4. order: ADDRESS
5. order: PRODUCT_LIST
6. product: index=-1, SELECT_PRODUCT  ← מוצר ראשון
7. product: index=-1, ENTER_QUANTITY
8. product: index=-1, ENTER_PRICE
9. product: index=-1, CONFIRM_PRODUCT  ← מוצר ראשון הושלם
10. order: PRODUCT_LIST               ← חזרה לרשימה
11. product: index=1, SELECT_PRODUCT  ← מוצר שני
12. product: index=1, ENTER_QUANTITY
13. ← חזור כאן
12. product: index=1, SELECT_PRODUCT  ← חזר לבחירת מוצר
14. ← חזור כאן
10. order: PRODUCT_LIST               ← ביטל הוספת מוצר שני
```

### דוגמה 2: עריכה מורכבת

```
Navigation Stack:
1-5. כמו למעלה עד PRODUCT_LIST
6. edit: index=0, SELECT_EDIT_ACTION  ← ערוך מוצר ראשון
7. edit: index=0, EDIT_QUANTITY
8. edit: index=0, CONFIRM_EDIT        ← סיים עריכה
9. order: PRODUCT_LIST               ← חזרה לרשימה
10. edit: index=2, SELECT_EDIT_ACTION ← ערוך מוצר שלישי
11. edit: index=2, EDIT_PRICE
12. ← חזור כאן
11. edit: index=2, SELECT_EDIT_ACTION ← ביטל עריכת מחיר
13. ← חזור כאן
9. order: PRODUCT_LIST               ← ביטל עריכת מוצר שלישי
```

## ⚠️ נקודות חשובות

### 1. ניהול זיכרון
- לנקות `active_product` כשיוצאים ממצב עריכה/הוספה
- לשמור temp_data רק למצב הנוכחי
- למחוק נתונים זמניים כשמבטלים פעולה

### 2. אישור שינויים
- שינויים זמניים לא נשמרים עד אישור מפורש
- כפתור "חזור" מבטל שינויים שלא נשמרו
- שינויים מאושרים נשמרים לרשימת המוצרים

### 3. גבולות מערכת
- מקסימום 20 מוצרים להזמנה
- מקסימום 20 שלבים אחורה בניווט
- הגבלת זמן להזמנה (timeout)

### 4. UX/UI
- הודעות ברורות על כל פעולה
- אישור לפני ביטול שינויים
- אפשרות "ביטול" נפרד מ"חזור"

## 📋 רשימת משימות יישום

### Phase 1: תשתית בסיסית ✅
- [x] הוספת navigation_stack ל-context
- [x] פונקציות push/pop ל-stack
- [x] הגדרת כל ה-enums (OrderStates, ProductStates, EditStates)

### Phase 2: מצבי order בסיסיים ✅
- [x] שחזור מצבי שם/טלפון/כתובת
- [x] step_back למצבי order
- [x] שינוי מבנה הנתונים לכל הפונקציות

### Phase 3: הוספת מוצרים ✅
- [x] active_product structure
- [x] שחזור מצבי בחירה/כמות/מחיר
- [x] ביטול הוספת מוצר באמצע
- [x] collect_product עם מבנה חדש
- [x] collect_quantity עם בדיקות מלאי
- [x] collect_total_price עם השלמת מוצר
- [x] טסטים מקיפים (11 טסטים)

### Phase 4: עריכת מוצרים ✅
- [x] edit states ו-temp_data
- [x] שחזור מצבי עריכה
- [x] ביטול שינויים בעריכה
- [x] start_edit_product עם original_data ו-temp_data
- [x] edit_product_quantity/price עם בדיקות מלאי
- [x] delete_product_confirm למחיקת מוצר
- [x] apply_edit_changes/cancel_edit_changes
- [x] apply_quantity_edit/apply_price_edit
- [x] טסטים מקיפים (13 טסטים)

### Phase 5: אינטגרציה ובדיקות ✅
- [x] טיפול בכל התרחישים
- [x] בדיקות עם מוצרים מרובים
- [x] edge cases ו-error handling
- [x] טסט אינטגרציה מקיף (19 שלבים של הזמנה מלאה)
- [x] בדיקת ניווט אחורה בכל התהליך
- [x] טיפול מקיף בשגיאות (מוצרים לא קיימים, אינדקסים לא תקינים, קלט לא תקין)
- [x] בדיקת אינטגריטי נתונים בכל התהליך
- [x] בדיקת edge cases (הזמנה ריקה, עריכות מרובות)
- [x] מעקב מקיף של navigation stack

### Phase 6: תיקון חזרה אחורה חכם ✅
- [x] זיהוי פעולת הוספת מוצר עם flag 'last_action_was_product_addition'
- [x] מחיקה אוטומטית של מוצר בכל חזרה אחורה (לא רק במקרים ספציפיים)
- [x] איפוס flag בתחילת תהליכים חדשים ובאישור הזמנה
- [x] לוגיקה מבוססת timestamp לזיהוי מוצר שנוסף לאחרונה
- [x] ביטול עריכות מוצרים קיימים כשחוזרים אחורה
- [x] ביטול הוספות לא שלמות כשחוזרים אחורה באמצע
- [x] בדיקות מקיפות לכל תרחישי חזרה אחורה

## 🎯 סיכום

המפתח הוא **navigation_stack** עם סוגי מצבים שונים:
- `order` - מצבי הזמנה כלליים
- `product` - הוספת מוצר חדש
- `edit` - עריכת מוצר קיים

כפתור "חזור" תמיד מוציא את המצב העליון ומשחזר את הקודם, עם לוגיקה ספציפית לכל סוג מצב.

זה מאפשר ניווט מלא וחופשי בכל התרחישים המורכבים עם מוצרים מרובים.
