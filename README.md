# Home Asset Accountability Platform (MVP)

Modular monolith MVP for tracking property hierarchy, assets, responsibilities, issues, documents, costs/tax relevance, government checklist, vendors, notifications, and audit logs.

## Run
```bash
python app.py
```
Open http://localhost:8000

## Demo login
- owner@example.com / password

## Implemented MVP modules
- Identity & Access (basic login)
- Property Structure (property/floor/room/asset/part schema)
- Asset & Component tracking
- Responsibility assignment schema
- Issue lifecycle + status history
- Document mock upload + linking metadata
- Cost & Tax relevance records
- Government checklist table
- Vendor directory table
- Notification foundation table
- Centralized audit log table
- Dashboard API summary and UI cards

## Architecture
- `src/modules/*`: module boundaries (domain-first structure)
- `src/lib/*`: shared db and audit helpers
- `prisma/schema.prisma`: future PostgreSQL Prisma schema starter for migration
- `app.py`: HTTP API composition layer for MVP
- `static/*`: responsive dashboard UI

## Seed data included
- Sample Family House, floors, rooms, assets
- Vendors: Plumber, Electrician, Carpenter, Interior contractor, Painter
- Sample issue: Bathroom leakage

## Future extensions
- Replace sqlite with PostgreSQL + Prisma migrations
- Add Next.js frontend/API routes with same module contracts
- S3/blob document adapters
- Mobile app integration via reusable APIs
