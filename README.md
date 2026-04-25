# NIST CSF 2.0 Explorer (Lifecycle + Visibility Controls)

## Access Model
- **All users** can access and click all six NIST CSF functions on the homepage.
- **Compliance Officer** and **Risk Officer**:
  - Full visibility of all controls (released, hidden, soft-deleted, deprecated)
  - Can create/edit/release/hide/soft-delete/restore/deprecate controls
  - Can view audit history
- **IT Product Manager**, **Technical Operations**, and **Read-only** users:
  - Read-only access
  - See only released + visible + not-soft-deleted controls

## Schema Highlights
- `functions`, `categories`, `subcategories`
- `controls` with lifecycle/visibility fields:
  - `status`
  - `is_visible_to_general_users`
  - `is_soft_deleted`
  - `created_by`, `updated_by`, `created_at`, `updated_at`
- `users`, `roles`, `functional_groups`, `role_category_permissions`
- `audit_log` for lifecycle actions

## APIs
- `POST /api/login`, `POST /api/logout`
- `GET /api/bootstrap`
- `GET /api/controls` (role-aware data visibility)
- Manager-only:
  - `POST /api/controls/create`
  - `POST /api/controls/edit`
  - `POST /api/controls/bulk-release`
  - `POST /api/controls/bulk-hide`
  - `POST /api/controls/soft-delete`
  - `POST /api/controls/restore`
  - `POST /api/controls/deprecate`
  - `GET /api/audit`

## Run
```bash
python app.py
```
Open: `http://localhost:8000`

Demo users (`password123`):
- `alice` (compliance_officer)
- `ravi` (risk_officer)
- `priya` (product_manager)
- `ops1` (tech_ops)
- `viewer` (readonly_user)
