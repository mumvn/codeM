# NIST CSF 2.0 Hierarchy Explorer

## Understanding Confirmed
This implementation is based on **NIST CSWP 29 (NIST Cybersecurity Framework 2.0, February 26, 2024)** and models the full hierarchy on the homepage:

**Function → Category → Subcategory → Control**

- Functions: GV, ID, PR, DE, RS, RC.
- Categories: all CSF 2.0 core categories (22 total).
- Subcategories: all CSF 2.0 core outcomes (106 total) with definitions from the framework Appendix A structure.
- Controls: mapped per subcategory as NIST CSF 2.0 core control records.

## Database Schema
- `functions(id, code, name, description)`
- `categories(id, code, function_id, name, description)`
- `subcategories(id, code, category_id, name, definition)`
- `controls(id, subcategory_id, control_code, control_type, details)`
- `functional_groups(id, name, description)`
- `roles(id, name, access_level, functional_group_id)`
- `users(id, username, password_hash, role_id)`
- `role_category_permissions(role_id, category_id)`

## UI Flow
1. Login using role-based demo users.
2. Homepage displays an expandable/collapsible tree.
3. Each **Function** node shows function definition and child categories.
4. Each **Category** node shows category definition and all subcategory definitions.
5. Clicking a function loads all permitted categories/subcategories/controls under that function.
6. Clicking a category loads that category's subcategories/controls in table format.
7. Search, sorting, and pagination operate on returned control rows.

## Run
```bash
python app.py
```
Open: `http://localhost:8000`

Demo accounts:
- `alice` / `password123` (Compliance Officer)
- `ravi` / `password123` (Risk Officer)
- `priya` / `password123` (IT Product Manager)
- `ops1` / `password123` (Technical Operations)
