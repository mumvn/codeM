# NIST CSF 2.0 Explorer (Two-Level Interaction Model)

## Feasibility Confirmation
Implemented as requested with a strict two-level UX:
1. **Homepage**: function selector only (GV, ID, PR, DE, RS, RC).
2. **Control View**: table + filters (no tree rendering).

## Data Model (Normalized)
- `functions(id, code, name, description)`
- `categories(id, code, function_id, name, description)`
- `subcategories(id, code, category_id, definition)`
- `functional_groups(id, name, description)`
- `roles(id, name, access_level, functional_group_id)`
- `users(id, username, password_hash, role_id)`
- `role_category_permissions(role_id, category_id)`

Notes:
- Control rows are derived from `subcategories` (control ID = subcategory code), avoiding duplicated storage.
- RBAC continues to restrict visibility by role/category permissions.

## Updated UI Flow
1. Login
2. Homepage shows only function cards with definitions
3. Click function card
4. Control view opens dynamically (no reload)
5. Table supports filters: Category, Subcategory, Control ID, Keywords
6. Sorting + pagination supported
7. Back button returns to homepage function selector

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
