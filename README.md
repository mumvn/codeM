# NIST CSF 2.0 Control Explorer

## 1) PDF Understanding Summary (NIST.CSWP.29)
This application is based on **NIST CSWP 29: The NIST Cybersecurity Framework (CSF) 2.0** (published **February 26, 2024**).

Key structure extracted from the PDF:
- **Core hierarchy:** Functions → Categories → Subcategories (implemented as controls in this app).
- **Functions (6):** Govern (GV), Identify (ID), Protect (PR), Detect (DE), Respond (RS), Recover (RC).
- **Categories (22):**
  - GV: OC, RM, RR, PO, OV, SC
  - ID: AM, RA, IM
  - PR: AA, AT, DS, PS, IR
  - DE: CM, AE
  - RS: MA, AN, CO, MI
  - RC: RP, CO
- **Subcategories / control outcomes:** 106 (all included in seed data).
- **Additional compliance/risk metadata captured:** function descriptions, category descriptions, role access levels, functional groups, and tier concepts (Tier 1–4 modeled as extensible metadata pathway).

## 2) Proposed Database Schema
Normalized relational model (SQLite):
- `functions(id, code, name, description)`
- `categories(id, code, function_id, name, description)`
- `controls(id, code, category_id, statement)`
- `functional_groups(id, name, description)`
- `roles(id, name, access_level, functional_group_id)`
- `users(id, username, password_hash, role_id)`
- `role_category_permissions(role_id, category_id)`

This supports RBAC, least privilege, and scalable extension for future CSF metadata (informative references, assessments, profiles, evidence, POA&M, etc.).

## 3) Application Architecture
- **Backend:** Python stdlib HTTP server (`app.py`) + SQLite (`csf.db`) with initialization/seed loading.
- **Frontend:** Static HTML/CSS/JS (`static/`) for interactive browsing.
- **API:**
  - `POST /api/login`
  - `POST /api/logout`
  - `GET /api/bootstrap` (user profile + permitted functions/categories)
  - `GET /api/controls` (filter/search/sort/paginate)
- **AuthN/AuthZ:** session cookie + role-to-category permission mapping.

## 4) UI/UX Flow
1. Login page with demo users.
2. On login, user sees profile banner (role, functional group, access level).
3. Left panel: Function → Category navigation tree.
4. User clicks category.
5. Right panel table loads related controls.
6. Search/sort/pagination on controls table.
7. Data shown is constrained by RBAC permissions.

## 5) Implementation Plan (executed)
1. Parse PDF structure and enumerate all core outcomes.
2. Design normalized relational model for framework + RBAC.
3. Implement backend and DB bootstrap/seed.
4. Implement role-based filtering in APIs.
5. Build interactive modern frontend.
6. Validate control counts and API behavior.

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
