import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from data.csf_seed import CATEGORIES, CONTROLS, FUNCTIONS

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "csf.db"
STATIC_DIR = BASE_DIR / "static"
SESSIONS = {}
MANAGER_ROLES = {"compliance_officer", "risk_officer"}
PM_ROLE = "product_manager"
PM_STATUSES = {"open", "in_progress", "closed"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = db_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS functions (id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, function_id INTEGER NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL, FOREIGN KEY(function_id) REFERENCES functions(id));
        CREATE TABLE IF NOT EXISTS subcategories (id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, category_id INTEGER NOT NULL, definition TEXT NOT NULL, FOREIGN KEY(category_id) REFERENCES categories(id));
        CREATE TABLE IF NOT EXISTS controls (
            id INTEGER PRIMARY KEY,
            control_id TEXT UNIQUE NOT NULL,
            subcategory_id INTEGER NOT NULL,
            control_text TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'released',
            is_visible_to_general_users INTEGER NOT NULL DEFAULT 1,
            is_soft_deleted INTEGER NOT NULL DEFAULT 0,
            created_by TEXT,
            updated_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(subcategory_id) REFERENCES subcategories(id)
        );
        CREATE TABLE IF NOT EXISTS functional_groups (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, description TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, access_level INTEGER NOT NULL, functional_group_id INTEGER NOT NULL, FOREIGN KEY(functional_group_id) REFERENCES functional_groups(id));
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role_id INTEGER NOT NULL, FOREIGN KEY(role_id) REFERENCES roles(id));
        CREATE TABLE IF NOT EXISTS role_category_permissions (role_id INTEGER NOT NULL, category_id INTEGER NOT NULL, PRIMARY KEY(role_id, category_id), FOREIGN KEY(role_id) REFERENCES roles(id), FOREIGN KEY(category_id) REFERENCES categories(id));
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY, control_id TEXT NOT NULL, action_type TEXT NOT NULL,
            performed_by TEXT NOT NULL, user_role TEXT NOT NULL, timestamp TEXT NOT NULL,
            previous_status TEXT, new_status TEXT, comment TEXT
        );
        CREATE TABLE IF NOT EXISTS product_manager_control_status (
            id INTEGER PRIMARY KEY,
            product_manager_user_id INTEGER NOT NULL,
            control_id TEXT NOT NULL,
            status TEXT NOT NULL,
            status_comment TEXT,
            last_updated_by TEXT,
            last_updated_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(product_manager_user_id, control_id),
            FOREIGN KEY(product_manager_user_id) REFERENCES users(id)
        );
        """
    )

    cur.executemany("INSERT OR IGNORE INTO functions(code,name,description) VALUES(?,?,?)", FUNCTIONS)
    f_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM functions")}
    cur.executemany("INSERT OR IGNORE INTO categories(code,function_id,name,description) VALUES(?,?,?,?)", [(c, f_map[f], n, d) for c, f, n, d in CATEGORIES])
    c_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM categories")}
    cur.executemany("INSERT OR IGNORE INTO subcategories(code,category_id,definition) VALUES(?,?,?)", [(sc, c_map[cc], d) for sc, cc, d in CONTROLS])

    ts = now_iso()
    s_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM subcategories")}
    cur.executemany(
        """
        INSERT OR IGNORE INTO controls(control_id,subcategory_id,control_text,description,status,is_visible_to_general_users,is_soft_deleted,created_by,updated_by,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        [(code, s_map[code], text, text, "released", 1, 0, "system", "system", ts, ts) for code, _, text in CONTROLS],
    )

    groups = [("Compliance", "Compliance officers"), ("Risk", "Risk officers"), ("Product", "Product managers"), ("Operations", "Technical operations"), ("ReadOnly", "Read-only users")]
    cur.executemany("INSERT OR IGNORE INTO functional_groups(name,description) VALUES(?,?)", groups)
    g_map = {r["name"]: r["id"] for r in cur.execute("SELECT id,name FROM functional_groups")}

    roles = [
        ("compliance_officer", 4, g_map["Compliance"]),
        ("risk_officer", 4, g_map["Risk"]),
        ("product_manager", 2, g_map["Product"]),
        ("tech_ops", 2, g_map["Operations"]),
        ("readonly_user", 1, g_map["ReadOnly"]),
    ]
    cur.executemany("INSERT OR IGNORE INTO roles(name,access_level,functional_group_id) VALUES(?,?,?)", roles)
    r_map = {r["name"]: r["id"] for r in cur.execute("SELECT id,name FROM roles")}

    users = [
        ("alice", "password123", "compliance_officer"),
        ("ravi", "password123", "risk_officer"),
        ("priya", "password123", "product_manager"),
        ("ops1", "password123", "tech_ops"),
        ("viewer", "password123", "readonly_user"),
    ] + [(f"prodmanager{i}", "password123", "product_manager") for i in range(1, 11)]
    cur.executemany("INSERT OR IGNORE INTO users(username,password_hash,role_id) VALUES(?,?,?)", [(u, hash_pw(p), r_map[r]) for u, p, r in users])
    for uname, pw, role_name in users:
        cur.execute("UPDATE users SET role_id=?, password_hash=? WHERE username=?", (r_map[role_name], hash_pw(pw), uname))

    perms = {k: ["GV", "ID", "PR", "DE", "RS", "RC"] for k in r_map.keys()}
    fcats = {}
    for row in cur.execute("SELECT c.id, f.code fcode FROM categories c JOIN functions f ON c.function_id=f.id"):
        fcats.setdefault(row["fcode"], []).append(row["id"])
    rows = []
    for role, fn_codes in perms.items():
        for fn in fn_codes:
            for cid in fcats.get(fn, []):
                rows.append((r_map[role], cid))
    cur.executemany("INSERT OR IGNORE INTO role_category_permissions(role_id,category_id) VALUES(?,?)", rows)

    conn.commit()
    conn.close()


def get_session(headers):
    token = SimpleCookie(headers.get("Cookie")).get("session")
    return SESSIONS.get(token.value) if token else None


def get_user_context(conn, user_id):
    row = conn.execute(
        """
        SELECT u.id, u.username, r.name role_name, r.access_level, fg.name functional_group
        FROM users u JOIN roles r ON u.role_id=r.id JOIN functional_groups fg ON fg.id=r.functional_group_id
        WHERE u.id=?
        """,
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def can_manage(ctx):
    return ctx["role_name"] in MANAGER_ROLES


def is_product_manager(ctx):
    return ctx["role_name"] == PM_ROLE


def audit(conn, control_id, action_type, ctx, previous_status, new_status, comment=""):
    conn.execute(
        "INSERT INTO audit_log(control_id,action_type,performed_by,user_role,timestamp,previous_status,new_status,comment) VALUES(?,?,?,?,?,?,?,?)",
        (control_id, action_type, ctx["username"], ctx["role_name"], now_iso(), previous_status, new_status, comment),
    )


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def _serve_static(self, path):
        p = STATIC_DIR / path
        if not p.exists():
            return self.send_error(404)
        ctype = "text/html" if path.endswith(".html") else "text/css" if path.endswith(".css") else "application/javascript"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(p.read_bytes())

    def _require_auth(self):
        sess = get_session(self.headers)
        if not sess:
            self._json({"error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return None, None
        conn = db_conn()
        return conn, get_user_context(conn, sess["user_id"])

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            return self._serve_static("index.html")
        if parsed.path in ["/styles.css", "/app.js"]:
            return self._serve_static(parsed.path[1:])

        conn, ctx = self._require_auth()
        if not conn:
            return

        if parsed.path == "/api/bootstrap":
            functions = conn.execute("SELECT id, code, name, description AS definition FROM functions ORDER BY id").fetchall()
            return self._json({
                "me": ctx,
                "can_manage": can_manage(ctx),
                "is_product_manager": is_product_manager(ctx),
                "can_dashboard": can_manage(ctx),
                "functions": [dict(x) for x in functions],
            })

        if parsed.path == "/api/controls":
            q = parse_qs(parsed.query)
            function_id = q.get("function_id", [None])[0]
            category_code = q.get("category_code", [""])[0].strip()
            subcategory_code = q.get("subcategory_code", [""])[0].strip()
            control_id = q.get("control_id", [""])[0].strip()
            search = q.get("search", [""])[0].strip()
            status_filter = q.get("status", [""])[0].strip()
            sort_by = q.get("sort_by", ["control_id"])[0]
            sort_dir = q.get("sort_dir", ["asc"])[0].upper()
            page = int(q.get("page", [1])[0])
            page_size = min(100, int(q.get("page_size", [12])[0]))
            sort_map = {
                "control_id": "ctrl.control_id",
                "subcategory_code": "s.code",
                "category_code": "c.code",
                "function_code": "f.code",
                "status": "ctrl.status",
            }
            sort_sql = sort_map.get(sort_by, "ctrl.control_id")
            if sort_dir not in {"ASC", "DESC"}:
                sort_dir = "ASC"

            where, vals = ["u.id=?"], [ctx["id"]]
            if function_id:
                where.append("f.id=?")
                vals.append(function_id)
            if category_code:
                where.append("c.code=?")
                vals.append(category_code)
            if subcategory_code:
                where.append("s.code=?")
                vals.append(subcategory_code)
            if control_id:
                where.append("ctrl.control_id LIKE ?")
                vals.append(f"%{control_id}%")
            if search:
                where.append("(ctrl.control_id LIKE ? OR ctrl.control_text LIKE ? OR c.name LIKE ?)")
                vals.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
            if can_manage(ctx):
                if status_filter:
                    where.append("ctrl.status=?")
                    vals.append(status_filter)
            else:
                where.extend(["ctrl.status='released'", "ctrl.is_visible_to_general_users=1", "ctrl.is_soft_deleted=0"])

            join_pm = "LEFT JOIN product_manager_control_status pm ON pm.control_id=ctrl.control_id AND pm.product_manager_user_id=?" if is_product_manager(ctx) else ""
            pm_val = [ctx["id"]] if is_product_manager(ctx) else []
            where_sql = " AND ".join(where)
            base = f"""
                FROM controls ctrl
                JOIN subcategories s ON s.id=ctrl.subcategory_id
                JOIN categories c ON c.id=s.category_id
                JOIN functions f ON f.id=c.function_id
                JOIN role_category_permissions p ON p.category_id=c.id
                JOIN users u ON u.role_id=p.role_id
                {join_pm}
                WHERE {where_sql}
            """
            total = conn.execute(f"SELECT COUNT(*) {base}", pm_val + vals).fetchone()[0]
            offset = (page - 1) * page_size
            pm_cols = ", pm.status pm_status, pm.status_comment pm_status_comment, pm.last_updated_at pm_last_updated_at" if is_product_manager(ctx) else ""
            rows = conn.execute(
                f"""
                SELECT ctrl.id, ctrl.control_id, ctrl.control_text, ctrl.status,
                       f.code function_code, f.name function_name,
                       c.code category_code, c.name category_name,
                       s.code subcategory_code, s.definition subcategory_definition
                       {pm_cols}
                {base}
                ORDER BY {sort_sql} {sort_dir}
                LIMIT ? OFFSET ?
                """,
                pm_val + vals + [page_size, offset],
            ).fetchall()

            opts_where, opts_vals = ["u.id=?"], [ctx["id"]]
            if function_id:
                opts_where.append("f.id=?")
                opts_vals.append(function_id)
            opt_sql = " AND ".join(opts_where)
            categories = conn.execute(
                f"SELECT DISTINCT c.code, c.name FROM categories c JOIN functions f ON f.id=c.function_id JOIN role_category_permissions p ON p.category_id=c.id JOIN users u ON u.role_id=p.role_id WHERE {opt_sql} ORDER BY c.code",
                opts_vals,
            ).fetchall()
            subcategories = conn.execute(
                f"SELECT DISTINCT s.code FROM subcategories s JOIN categories c ON c.id=s.category_id JOIN functions f ON f.id=c.function_id JOIN role_category_permissions p ON p.category_id=c.id JOIN users u ON u.role_id=p.role_id WHERE {opt_sql} ORDER BY s.code",
                opts_vals,
            ).fetchall()

            return self._json({
                "items": [dict(r) for r in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
                "can_manage": can_manage(ctx),
                "is_product_manager": is_product_manager(ctx),
                "filter_options": {"categories": [dict(x) for x in categories], "subcategories": [dict(x) for x in subcategories]},
            })

        if parsed.path == "/api/dashboard":
            if not can_manage(ctx):
                return self._json({"error": "Forbidden"}, HTTPStatus.FORBIDDEN)
            q = parse_qs(parsed.query)
            pm_username = q.get("pm_username", [""])[0].strip()
            function_id = q.get("function_id", [""])[0].strip()
            category_code = q.get("category_code", [""])[0].strip()
            subcategory_code = q.get("subcategory_code", [""])[0].strip()
            status_filter = q.get("status", [""])[0].strip()
            start_date = q.get("start_date", [""])[0].strip()
            end_date = q.get("end_date", [""])[0].strip()

            where = ["ctrl.status='released'", "ctrl.is_visible_to_general_users=1", "ctrl.is_soft_deleted=0"]
            vals = []
            if function_id:
                where.append("f.id=?"); vals.append(function_id)
            if category_code:
                where.append("c.code=?"); vals.append(category_code)
            if subcategory_code:
                where.append("s.code=?"); vals.append(subcategory_code)
            where_sql = " AND ".join(where)

            pm_where = "WHERE r.name='product_manager'"
            pm_vals = []
            if pm_username:
                pm_where += " AND u.username LIKE ?"
                pm_vals.append(f"%{pm_username}%")

            rows = conn.execute(
                f"""
                WITH pm_users AS (
                  SELECT u.id pm_id, u.username pm_username
                  FROM users u JOIN roles r ON r.id=u.role_id
                  {pm_where}
                ), filtered_controls AS (
                  SELECT ctrl.control_id
                  FROM controls ctrl
                  JOIN subcategories s ON s.id=ctrl.subcategory_id
                  JOIN categories c ON c.id=s.category_id
                  JOIN functions f ON f.id=c.function_id
                  WHERE {where_sql}
                )
                SELECT p.pm_username, fc.control_id,
                       COALESCE(pm.status, 'open') AS pm_status,
                       pm.last_updated_at
                FROM pm_users p
                CROSS JOIN filtered_controls fc
                LEFT JOIN product_manager_control_status pm ON pm.product_manager_user_id=p.pm_id AND pm.control_id=fc.control_id
                """,
                pm_vals + vals,
            ).fetchall()

            def in_date(last_updated):
                if not start_date and not end_date:
                    return True
                if not last_updated:
                    return False
                d = last_updated[:10]
                if start_date and d < start_date:
                    return False
                if end_date and d > end_date:
                    return False
                return True

            per = {}
            overall = {"open": 0, "in_progress": 0, "closed": 0}
            overdue_cutoff = datetime.now(timezone.utc) - timedelta(days=14)
            for r in rows:
                status = r["pm_status"]
                if status_filter and status != status_filter:
                    continue
                if not in_date(r["last_updated_at"]):
                    continue
                pm = per.setdefault(r["pm_username"], {"product_manager": r["pm_username"], "total": 0, "open": 0, "in_progress": 0, "closed": 0, "overdue_or_stale": 0})
                pm["total"] += 1
                pm[status] += 1
                overall[status] += 1
                lu = r["last_updated_at"]
                stale = True
                if lu:
                    try:
                        stale = datetime.fromisoformat(lu) < overdue_cutoff
                    except Exception:
                        stale = True
                if stale:
                    pm["overdue_or_stale"] += 1

            managers = []
            for x in per.values():
                x["completion_pct"] = round((x["closed"] / x["total"] * 100), 2) if x["total"] else 0
                managers.append(x)
            managers.sort(key=lambda m: m["product_manager"])

            # Trend: status updates over time
            trend_where = ["r.name='product_manager'", "pm.last_updated_at IS NOT NULL", where_sql]
            trend_vals = vals.copy()
            if pm_username:
                trend_where.append("u.username LIKE ?")
                trend_vals.append(f"%{pm_username}%")
            if status_filter:
                trend_where.append("pm.status=?")
                trend_vals.append(status_filter)
            if start_date:
                trend_where.append("substr(pm.last_updated_at,1,10) >= ?")
                trend_vals.append(start_date)
            if end_date:
                trend_where.append("substr(pm.last_updated_at,1,10) <= ?")
                trend_vals.append(end_date)

            trend_rows = conn.execute(
                f"""
                SELECT substr(pm.last_updated_at,1,10) as day, pm.status, count(*) as cnt
                FROM product_manager_control_status pm
                JOIN users u ON u.id=pm.product_manager_user_id
                JOIN roles r ON r.id=u.role_id
                JOIN controls ctrl ON ctrl.control_id=pm.control_id
                JOIN subcategories s ON s.id=ctrl.subcategory_id
                JOIN categories c ON c.id=s.category_id
                JOIN functions f ON f.id=c.function_id
                WHERE {' AND '.join(trend_where)}
                GROUP BY day, pm.status
                ORDER BY day
                """,
                trend_vals,
            ).fetchall()

            trend = {}
            for tr in trend_rows:
                d = trend.setdefault(tr["day"], {"date": tr["day"], "open": 0, "in_progress": 0, "closed": 0, "updates": 0})
                d[tr["status"]] += tr["cnt"]
                d["updates"] += tr["cnt"]
            trend_list = [trend[k] for k in sorted(trend.keys())]

            categories = conn.execute("SELECT code, name FROM categories ORDER BY code").fetchall()
            subcategories = conn.execute("SELECT code FROM subcategories ORDER BY code").fetchall()
            pm_users = conn.execute("SELECT u.username FROM users u JOIN roles r ON r.id=u.role_id WHERE r.name='product_manager' ORDER BY u.username").fetchall()

            total_rows = sum(m["total"] for m in managers)
            completion_pct = round((overall["closed"] / total_rows * 100), 2) if total_rows else 0
            stale_total = sum(m["overdue_or_stale"] for m in managers)

            return self._json({
                "summary": {
                    "total_controls": total_rows,
                    "total_product_managers": len(managers),
                    "overall_open": overall["open"],
                    "overall_in_progress": overall["in_progress"],
                    "overall_closed": overall["closed"],
                    "overall_completion_pct": completion_pct,
                    "stale_controls": stale_total,
                },
                "status_distribution": overall,
                "per_manager": managers,
                "trend": trend_list,
                "filter_options": {
                    "product_managers": [x["username"] for x in pm_users],
                    "categories": [dict(x) for x in categories],
                    "subcategories": [dict(x) for x in subcategories],
                },
            })

        if parsed.path == "/api/audit":
            if not can_manage(ctx):
                return self._json({"error": "Forbidden"}, HTTPStatus.FORBIDDEN)
            control_id = parse_qs(parsed.query).get("control_id", [""])[0]
            where = "WHERE control_id=?" if control_id else ""
            vals = [control_id] if control_id else []
            logs = conn.execute(f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT 500", vals).fetchall()
            return self._json({"items": [dict(x) for x in logs]})

        return self._json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/api/login":
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            conn = db_conn()
            row = conn.execute("SELECT id, username FROM users WHERE username=? AND password_hash=?", (payload.get("username", ""), hash_pw(payload.get("password", "")))).fetchone()
            if not row:
                return self._json({"error": "Invalid credentials"}, HTTPStatus.UNAUTHORIZED)
            token = secrets.token_hex(24)
            SESSIONS[token] = {"user_id": row["id"], "username": row["username"]}
            return self._json({"ok": True}, cookie=f"session={token}; HttpOnly; Path=/; SameSite=Lax")

        if self.path == "/api/logout":
            token = SimpleCookie(self.headers.get("Cookie")).get("session")
            if token:
                SESSIONS.pop(token.value, None)
            return self._json({"ok": True}, cookie="session=; Max-Age=0; Path=/")

        conn, ctx = self._require_auth()
        if not conn:
            return
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

        if self.path == "/api/pm/status":
            if not is_product_manager(ctx):
                return self._json({"error": "Forbidden"}, HTTPStatus.FORBIDDEN)
            cid = payload.get("control_id", "")
            status = payload.get("status", "").lower()
            if status not in PM_STATUSES:
                return self._json({"error": "Invalid status"}, 400)
            exists = conn.execute(
                "SELECT 1 FROM controls WHERE control_id=? AND status='released' AND is_visible_to_general_users=1 AND is_soft_deleted=0",
                (cid,),
            ).fetchone()
            if not exists:
                return self._json({"error": "Control not visible"}, 404)
            ts = now_iso()
            conn.execute(
                """
                INSERT INTO product_manager_control_status(product_manager_user_id,control_id,status,status_comment,last_updated_by,last_updated_at,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(product_manager_user_id,control_id)
                DO UPDATE SET status=excluded.status, status_comment=excluded.status_comment, last_updated_by=excluded.last_updated_by, last_updated_at=excluded.last_updated_at, updated_at=excluded.updated_at
                """,
                (ctx["id"], cid, status, payload.get("status_comment", ""), ctx["username"], ts, ts, ts),
            )
            conn.commit()
            return self._json({"ok": True})

        manager_paths = {"/api/controls/create", "/api/controls/edit", "/api/controls/soft-delete", "/api/controls/restore", "/api/controls/bulk-release", "/api/controls/bulk-hide", "/api/controls/deprecate"}
        if self.path in manager_paths and not can_manage(ctx):
            return self._json({"error": "Forbidden"}, HTTPStatus.FORBIDDEN)

        if self.path == "/api/controls/create":
            sub = payload.get("subcategory_code", "")
            srow = conn.execute("SELECT id, definition FROM subcategories WHERE code=?", (sub,)).fetchone()
            if not srow:
                return self._json({"error": "Invalid subcategory"}, 400)
            cid = payload.get("control_id") or sub
            txt = payload.get("control_text") or srow["definition"]
            st = payload.get("status", "hidden")
            visible = 1 if st == "released" else 0
            ts = now_iso()
            conn.execute(
                "INSERT INTO controls(control_id,subcategory_id,control_text,description,status,is_visible_to_general_users,is_soft_deleted,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (cid, srow["id"], txt, payload.get("description", ""), st, visible, 0, ctx["username"], ctx["username"], ts, ts),
            )
            audit(conn, cid, "created", ctx, "", st, payload.get("comment", ""))
            conn.commit()
            return self._json({"ok": True})

        if self.path == "/api/controls/edit":
            cid = payload.get("control_id")
            old = conn.execute("SELECT status, control_text, description FROM controls WHERE control_id=?", (cid,)).fetchone()
            if not old:
                return self._json({"error": "Control not found"}, 404)
            conn.execute("UPDATE controls SET control_text=?, description=?, updated_by=?, updated_at=? WHERE control_id=?", (payload.get("control_text", old["control_text"]), payload.get("description", old["description"]), ctx["username"], now_iso(), cid))
            audit(conn, cid, "edited", ctx, old["status"], old["status"], payload.get("comment", ""))
            conn.commit()
            return self._json({"ok": True})

        if self.path in {"/api/controls/bulk-release", "/api/controls/bulk-hide", "/api/controls/soft-delete", "/api/controls/restore", "/api/controls/deprecate"}:
            ids = payload.get("control_ids", [])
            if not ids:
                return self._json({"error": "No controls selected"}, 400)
            mapping = {
                "/api/controls/bulk-release": ("released", 1, 0, "released"),
                "/api/controls/bulk-hide": ("hidden", 0, 0, "hidden"),
                "/api/controls/soft-delete": ("soft_deleted", 0, 1, "soft_deleted"),
                "/api/controls/restore": ("hidden", 0, 0, "restored"),
                "/api/controls/deprecate": ("deprecated", 0, 0, "deprecated"),
            }
            new_status, visible, soft, action = mapping[self.path]
            for cid in ids:
                old = conn.execute("SELECT status FROM controls WHERE control_id=?", (cid,)).fetchone()
                if not old:
                    continue
                conn.execute("UPDATE controls SET status=?, is_visible_to_general_users=?, is_soft_deleted=?, updated_by=?, updated_at=? WHERE control_id=?", (new_status, visible, soft, ctx["username"], now_iso(), cid))
                audit(conn, cid, action, ctx, old["status"], new_status, payload.get("comment", ""))
            conn.commit()
            return self._json({"ok": True})

        return self._json({"error": "Not found"}, 404)


def run():
    init_db()
    server = HTTPServer(("0.0.0.0", 8000), Handler)
    print("Server running on http://localhost:8000")
    server.serve_forever()


if __name__ == "__main__":
    run()
