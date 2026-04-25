# NIST CSF 2.0 Explorer (Lifecycle + Product Manager Dashboard)

## New capabilities
- Added 10 Product Manager users (`prodmanager1` ... `prodmanager10`).
- Added per-Product-Manager control progress tracking in separate table:
  - `product_manager_control_status`
  - statuses: `open`, `in_progress`, `closed`
- Product Managers can update only their own status records.
- Compliance/Risk can see a dashboard of PM metrics and retain existing lifecycle admin permissions.

## Access model
- **All users:** can navigate all 6 CSF functions.
- **Compliance/Risk:** full control lifecycle management + dashboard + audit.
- **Product managers:** read released controls, update only their own PM status/comment.
- **Ops/Read-only:** read released controls only.

## APIs
- Auth/bootstrap: `POST /api/login`, `POST /api/logout`, `GET /api/bootstrap`
- Controls: `GET /api/controls`
- PM status update: `POST /api/pm/status` (product_manager only)
- Dashboard: `GET /api/dashboard` (compliance/risk only)
- Existing manager lifecycle APIs retained (`/api/controls/*`)

## Run
```bash
python app.py
```
Open: `http://localhost:8000`

Demo password: `password123`
- Compliance: `alice`
- Risk: `ravi`
- Product managers: `priya`, `prodmanager1`..`prodmanager10`
- Tech ops: `ops1`
- Read-only: `viewer`
