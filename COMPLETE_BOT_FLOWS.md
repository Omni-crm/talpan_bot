# 🤖 Complete Bot Flows Documentation

**Date:** 2025-01-27  
**Bot:** Courier Bot  
**Status:** Post Supabase Migration

## 📋 Table of Contents

1. [Admin Flows](#admin-flows)
2. [Operator Flows](#operator-flows)
3. [Stockman Flows](#stockman-flows)
4. [Courier Flows](#courier-flows)
5. [End-to-End Flows](#end-to-end-flows)

---

## 👑 Admin Flows

### 1. Admin Login & Main Menu

**Flow:**
1. User starts bot with `/start`
2. Bot checks role - if admin → shows admin menu
3. Admin sees: View Orders, Manage Staff, Settings, Reports, Security

**Key Handlers:**
- `bot.py` → `/start` command
- `funcs/bot_funcs.py` → `is_admin` decorator
- `config/kb.py` → `build_start_menu()` - builds admin menu

### 2. Manage Staff

**Flow:**
1. Admin clicks "Manage Staff" (or `/staff`)
2. Shows staff list with roles
3. Options:
   - Add new staff
   - Edit staff role
   - Delete staff
   
**Key Handlers:**
- `funcs/bot_funcs.py` → `show_staff_list()`
- `handlers/add_staff_handler.py` → `ADD_STAFF_HANDLER`
- `db/db.py` → `get_user_by_id()`, `update_user_role()`

### 3. View All Orders

**Flow:**
1. Admin clicks "All Orders"
2. Bot queries all orders from Supabase
3. Displays orders with filters (date, product, status, client)
4. Options: Filter, Export, Delete old orders

**Key Handlers:**
- `funcs/bot_funcs.py` → `all_orders()`
- `funcs/utils.py` → `export_orders_as_text()`
- `db/db.py` → `get_all_orders()`

### 4. Weekly Report

**Flow:**
1. Admin clicks "Week Report"
2. Bot queries shifts from last 7 days
3. Calculates: total income, expenses, profit, orders count
4. Displays report

**Key Handlers:**
- `funcs/utils.py` → `form_week_report()`
- `db/db.py` → `get_all_orders()`, shifts query

### 5. Security & Settings

**Flow:**
1. Admin clicks "Security"
2. Options:
   - Change admin group link
   - Change courier group link
   - Manage Telegram sessions
   - View bot settings

**Key Handlers:**
- `handlers/change_links_handler.py` → `CHANGE_LINK_HANDLER`
- `handlers/make_tg_session_handler.py` → `MAKE_TG_SESSION_HANDLER`
- `db/db.py` → `get_bot_setting()`, `set_bot_setting()`

---

## ⚙️ Operator Flows

### 1. Operator Login

**Flow:**
1. User starts bot with `/start`
2. Bot checks role - if operator → shows operator menu
3. Operator sees: New Order, Active Orders, Templates, Start Shift

**Key Handlers:**
- `bot.py` → `/start` command
- `funcs/bot_funcs.py` → `is_operator` decorator
- `config/kb.py` → `build_start_menu()` - builds operator menu

### 2. Create New Order

**Flow:**
1. Operator clicks "New Order"
2. Bot checks if shift is opened
3. If no shift → prompts to start shift
4. If shift exists → starts order collection:
   - Client name
   - Client username (optional - can skip)
   - Client phone
   - Client address (with geocoding)
   - Product selection
   - Quantity
   - Total price
   - Confirmation
5. Order saved to Supabase
6. Order notified to groups

**Key Handlers:**
- `handlers/new_order_handler.py` → `NEW_ORDER_HANDLER`
- `db/db.py` → `create_order()`, `get_opened_shift()`
- `funcs/utils.py` → geocoding

### 3. Start Shift

**Flow:**
1. Operator clicks "Start Shift"
2. Bot checks if shift exists
3. If exists → prompts to close previous shift
4. If no shift → creates new shift in Supabase
5. Sends confirmation message
6. Shift marked as 'opened'

**Key Handlers:**
- `funcs/bot_funcs.py` → `confirm_stock_shift()`
- `funcs/utils.py` → `send_shift_start_msg()`
- `db/db.py` → `create_shift()`, `get_opened_shift()`

### 4. End Shift

**Flow:**
1. Operator clicks "End Shift"
2. Bot finds opened shift
3. Prompts for: Petrol paid
4. Calculates total income, expenses
5. Updates shift status to 'closed'
6. Updates closed_time
7. Shows summary

**Key Handlers:**
- `handlers/end_shift_handler.py` → `END_SHIFT_HANDLER`
- `db/db.py` → `update_shift()`, `get_opened_shift()`

### 5. View Active Orders

**Flow:**
1. Operator clicks "Active Orders"
2. Bot queries orders with status: 'active', 'pending', 'delay'
3. Shows list with order details
4. Options: Send message to client, Mark as ready, Update status

**Key Handlers:**
- `funcs/bot_funcs.py` → handler for active orders
- `db/db.py` → `get_orders_by_filter()`
- `config/kb.py` → `get_all_active_orders_to_msg_kb()`

### 6. Send/Edit Templates

**Flow:**
1. Operator clicks "Templates"
2. Shows available templates
3. Selects template
4. Selects order to send
5. Bot sends template message to client
6. Options: Edit template, Delete template

**Key Handlers:**
- `handlers/send_or_edit_template.py` → `SEND_OR_EDIT_TEMPLATE`
- `db/db.py` → queries to 'templates' and 'tgsessions'
- `funcs/bot_funcs.py` → `show_templates()`

### 7. Create New Template

**Flow:**
1. Operator clicks "Create Template"
2. Prompts for template name
3. Prompts for template text
4. Saves to Supabase
5. Template available for use

**Key Handlers:**
- `handlers/create_new_shablon.py` → `CREATE_NEW_TEMPLATE`
- `db/db.py` → insert to 'templates'

---

## 📦 Stockman Flows

### 1. Stockman Login

**Flow:**
1. User starts bot with `/start`
2. Bot checks role - if stockman → shows stockman menu
3. Stockman sees: Manage Stock, Edit Products, View Products

**Key Handlers:**
- `bot.py` → `/start` command
- `funcs/bot_funcs.py` → `is_stockman` decorator
- `config/kb.py` → `build_start_menu()`

### 2. Edit Product Stock/Crude

**Flow:**
1. Stockman clicks "Manage Stock"
2. Shows product list
3. Selects product
4. Options:
   - Edit stock
   - Edit crude
   - Delete product
5. Updates saved to Supabase

**Key Handlers:**
- `handlers/edit_product_handler.py` → `EDIT_PRODUCT_HANDLER`
- `handlers/edit_crude_handler.py` → `EDIT_CRUDE_HANDLER`
- `db/db.py` → `get_product_by_id()`, `update_product_stock()`

### 3. View Products

**Flow:**
1. Stockman clicks "View Products"
2. Bot queries all products from Supabase
3. Displays: name, stock, crude, price

**Key Handlers:**
- `config/kb.py` → `get_products_markup()`
- `db/db.py` → `get_all_products()`

---

## 🚚 Courier Flows

### 1. Courier Login

**Flow:**
1. User starts bot with `/start`
2. Bot checks role - if courier → shows courier menu
3. Courier sees: My Deliveries, Update Order Status

**Key Handlers:**
- `bot.py` → `/start` command
- `funcs/bot_funcs.py` → `is_courier` decorator

### 2. View Deliveries

**Flow:**
1. Courier clicks "My Deliveries"
2. Bot queries orders assigned to courier
3. Shows list with status
4. Options: Update status, Add delay time

**Key Handlers:**
- Filter orders by courier
- `config/kb.py` → order markup

### 3. Update Order Status

**Flow:**
1. Courier selects order
2. Options:
   - Mark as 'ready'
   - Add delay (X minutes)
   - Custom delay time
3. Updates order status in Supabase
4. Notifies operator

**Key Handlers:**
- `handlers/courier_choose_minutes.py` → `CHOOSE_MINUTES_HANDLER`
- `handlers/courier_write_minutes.py` → `WRITE_MINUTES_HANDLER`
- `handlers/courier_choose_delay.py` → `DELAY_MINUTES_HANDLER`
- `db/db.py` → `update_order()`

### 4. Mark Order as Ready

**Flow:**
1. Courier clicks on order
2. Clicks "Ready"
3. Order status updated to 'ready'
4. Client notified

**Key Handlers:**
- `funcs/bot_funcs.py` → `order_ready()`
- `db/db.py` → `update_order_status()`

---

## 🔄 End-to-End Flows

### Complete Order Lifecycle

1. **Operator creates order:**
   - Collects client data
   - Selects products
   - Confirms order
   - Order saved as 'active'

2. **Order notification:**
   - Sent to admin group
   - Sent to courier group
   - Template message sent to client

3. **Courier picks up:**
   - Courier selects order
   - Updates status or adds delay
   - Order may go to 'delay' status

4. **Order processing:**
   - Multiple status changes
   - Minute tracking for delays
   - Updates saved to Supabase

5. **Order completion:**
   - Marked as 'ready'
   - Client notified
   - Order closed

### Complete Shift Lifecycle

1. **Shift Start:**
   - Operator clicks "Start Shift"
   - Shift created in Supabase
   - Status: 'opened'
   - Opens inventory

2. **During Shift:**
   - Orders created
   - Products updated
   - Stock managed
   - All data saved to Supabase

3. **Shift End:**
   - Operator provides petrol amount
   - Bot calculates totals
   - Shift status: 'closed'
   - Summary displayed

---

## 🧪 Critical Functions to Test

### Database Operations
- [ ] `get_opened_shift()` - Check if shift exists
- [ ] `create_shift()` - Create new shift
- [ ] `update_shift()` - Close shift
- [ ] `create_order()` - Save new order
- [ ] `get_all_orders()` - Query orders
- [ ] `update_order()` - Update order status
- [ ] `get_product_by_id()` - Get product info
- [ ] `update_product_stock()` - Update inventory
- [ ] `get_user_by_id()` - Get user info
- [ ] `create_tg_session()` - Add Telegram session

### Handlers
- [ ] `confirm_stock_shift()` - Start shift handler
- [ ] `NEW_ORDER_HANDLER` - Full order creation flow
- [ ] `collect_username()` - Username collection
- [ ] `END_SHIFT_HANDLER` - Shift closing
- [ ] `edit_product_stock()` - Stock management
- [ ] `show_templates()` - Template system
- [ ] Courier delay handlers

### Decorators (Role Checks)
- [ ] `is_admin()` - Admin access control
- [ ] `is_operator()` - Operator access control
- [ ] `is_stockman()` - Stockman access control
- [ ] `is_courier()` - Courier access control

---

## 🐛 Known Issues to Test

1. **confirm_stock_shift button not responding**
   - Add error logging ✅
   - Test Supabase connection
   - Verify shift creation

2. **collect_username not working**
   - Add error logging ✅
   - Check callback data pattern
   - Verify conversation state

3. **End shift handler issues**
   - Test shift closing
   - Verify calculations
   - Check Supabase updates

4. **Order creation flow**
   - Test all steps
   - Check data validation
   - Verify Supabase inserts

5. **Template system**
   - Test template send
   - Check Telegram session
   - Verify notifications

---

**Next Step:** Run comprehensive local testing with all flows

