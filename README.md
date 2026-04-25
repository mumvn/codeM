# NIST CSF 2.0 Explorer (Refactored)

## Feasibility Confirmation
Yes — this is fully feasible and implemented.

The app now uses a normalized CSF hierarchy with **no duplicated definition storage**:
- Function
- Category
- Subcategory

The control view is a **derived projection** from subcategories (control code = subcategory code), so control text is not redundantly duplicated in another table.

## Refactored Data Model (Normalized)
- `functions(id, code, name, description)`
- `categories(id, code, function_id, name, description)`
- `subcategories(id, code, category_id, definition)`
- `functional_groups(id, name, description)`
- `roles(id, name, access_level, functional_group_id)`
- `users(id, username, password_hash, role_id)`
- `role_category_permissions(role_id, category_id)`

## Updated App Flow
1. Login.
2. Homepage shows **tree navigation only** (Function → Category → Subcategory with definitions).
3. Clicking Function/Category transitions to control table view (no page reload).
4. Control table shows related function/category/subcategory rows and derived control mapping.
5. Back button returns to tree homepage.

## Run
```bash
python app.py
```
Open: `http://localhost:8000`

Demo accounts:
- `alice` / `password123`
- `ravi` / `password123`
- `priya` / `password123`
- `ops1` / `password123`
