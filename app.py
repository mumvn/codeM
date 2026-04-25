import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
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
        CREATE TABLE IF NOT EXISTS functions (
            id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, function_id INTEGER NOT NULL,
            name TEXT NOT NULL, description TEXT NOT NULL,
            FOREIGN KEY(function_id) REFERENCES functions(id)
        );
        CREATE TABLE IF NOT EXISTS subcategories (
            id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, category_id INTEGER NOT NULL,
            definition TEXT NOT NULL,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );
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
        CREATE TABLE IF NOT EXISTS functional_groups (
            id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, access_level INTEGER NOT NULL,
            functional_group_id INTEGER NOT NULL,
            FOREIGN KEY(functional_group_id) REFERENCES functional_groups(id)
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            role_id INTEGER NOT NULL,
            FOREIGN KEY(role_id) REFERENCES roles(id)
        );
        CREATE TABLE IF NOT EXISTS role_category_permissions (
            role_id INTEGER NOT NULL, category_id INTEGER NOT NULL,
            PRIMARY KEY(role_id, category_id),
            FOREIGN KEY(role_id) REFERENCES roles(id),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            control_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            performed_by TEXT NOT NULL,
            user_role TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            previous_status TEXT,
            new_status TEXT,
            comment TEXT
        );
        """
    )

    cur.executemany("INSERT OR IGNORE INTO functions(code,name,description) VALUES(?,?,?)", FUNCTIONS)
    function_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM functions")}

    cur.executemany(
        "INSERT OR IGNORE INTO categories(code,function_id,name,description) VALUES(?,?,?,?)",
        [(code, function_map[fcode], name, desc) for code, fcode, name, desc in CATEGORIES],
    )
    category_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM categories")}

    cur.executemany(
        "INSERT OR IGNORE INTO subcategories(code,category_id,definition) VALUES(?,?,?)",
        [(scode, category_map[ccode], definition) for scode, ccode, definition in CONTROLS],
    )

    ts = now_iso()
    sub_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM subcategories")}
    cur.executemany(
        """
        INSERT OR IGNORE INTO controls(control_id,subcategory_id,control_text,description,status,is_visible_to_general_users,is_soft_deleted,created_by,updated_by,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        [(code, sub_map[code], definition, definition, "released", 1, 0, "system", "system", ts, ts) for code, _, definition in CONTROLS],
    )

    groups = [
        ("Compliance", "Compliance officers and auditors"),
        ("Risk", "Risk officers and governance teams"),
        ("Product", "IT product management"),
        ("Operations", "Technical operations and SOC teams"),
        ("ReadOnly", "General read-only users"),
    ]
    cur.executemany("INSERT OR IGNORE INTO functional_groups(name,description) VALUES(?,?)", groups)
    gmap = {r["name"]: r["id"] for r in cur.execute("SELECT id,name FROM functional_groups")}

    roles = [
        ("compliance_officer", 4, gmap["Compliance"]),
        ("risk_officer", 4, gmap["Risk"]),
        ("product_manager", 2, gmap["Product"]),
        ("tech_ops", 2, gmap["Operations"]),
        ("readonly_user", 1, gmap["ReadOnly"]),
    ]
    cur.executemany("INSERT OR IGNORE INTO roles(name,access_level,functional_group_id) VALUES(?,?,?)", roles)
    rmap = {r["name"]: r["id"] for r in cur.execute("SELECT id,name FROM roles")}

    users = [
        ("alice", "password123", "compliance_officer"),
        ("ravi", "password123", "risk_officer"),
        ("priya", "password123", "product_manager"),
        ("ops1", "password123", "tech_ops"),
        ("viewer", "password123", "readonly_user"),
    ]
    cur.executemany("INSERT OR IGNORE INTO users(username,password_hash,role_id) VALUES(?,?,?)", [(u, hash_pw(p), rmap[r]) for u, p, r in users])

    # Everyone can navigate all functions; category permissions still enforce control visibility scope.
    perms = {k: ["GV", "ID", "PR", "DE", "RS", "RC"] for k in rmap.keys()}
    fcats = {}
    for row in cur.execute("SELECT c.id, f.code fcode FROM categories c JOIN functions f ON c.function_id=f.id"):
        fcats.setdefault(row["fcode"], []).append(row["id"])
    perm_rows = []
    for role, fn_codes in perms.items():
        for fn in fn_codes:
            for cid in fcats.get(fn, []):
                perm_rows.append((rmap[role], cid))
    cur.executemany("INSERT OR IGNORE INTO role_category_permissions(role_id,category_id) VALUES(?,?)", perm_rows)

    conn.commit()
    conn.close()


def get_session(headers):
    cookie = SimpleCookie(headers.get("Cookie"))
    token = cookie.get("session")
    return SESSIONS.get(token.value) if token else None


def get_user_context(conn, user_id):
    row = conn.execute(
        """
        SELECT u.id, u.username, r.name role_name, r.access_level, fg.name functional_group
        FROM users u
        JOIN roles r ON r.id=u.role_id
        JOIN functional_groups fg ON fg.id=r.functional_group_id
        WHERE u.id=?
        """,
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def can_manage(ctx):
    return ctx["role_name"] in MANAGER_ROLES


def audit(conn, control_id, action_type, ctx, previous_status, new_status, comment=""):
    conn.execute(
        """
        INSERT INTO audit_log(control_id,action_type,performed_by,user_role,timestamp,previous_status,new_status,comment)
        VALUES(?,?,?,?,?,?,?,?)
        """,
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
        file_path = STATIC_DIR / path
        if not file_path.exists():
            return self.send_error(404)
        ctype = "text/html" if path.endswith(".html") else "text/css" if path.endswith(".css") else "application/javascript"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def _require_auth(self):
        sess = get_session(self.headers)
        if not sess:
            self._json({"error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return None, None
        conn = db_conn()
        ctx = get_user_context(conn, sess["user_id"])
        return conn, ctx

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
            return self._json({"me": ctx, "can_manage": can_manage(ctx), "functions": [dict(x) for x in functions]})

        if parsed.path == "/api/controls":
            params = parse_qs(parsed.query)
            function_id = params.get("function_id", [None])[0]
            category_code = params.get("category_code", [""])[0].strip()
            subcategory_code = params.get("subcategory_code", [""])[0].strip()
            control_id = params.get("control_id", [""])[0].strip()
            search = params.get("search", [""])[0].strip()
            status_filter = params.get("status", [""])[0].strip()
            sort_by = params.get("sort_by", ["control_id"])[0]
            sort_dir = params.get("sort_dir", ["asc"])[0].upper()
            page = int(params.get("page", [1])[0])
            page_size = min(100, int(params.get("page_size", [12])[0]))
            if sort_by not in {"control_id", "subcategory_code", "category_code", "function_code", "status"}:
                sort_by = "control_id"
            if sort_dir not in {"ASC", "DESC"}:
                sort_dir = "ASC"

            where = ["u.id=?"]
            vals = [ctx["id"]]
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
                where.append("(ctrl.control_id LIKE ? OR ctrl.control_text LIKE ? OR s.definition LIKE ? OR c.name LIKE ?)")
                vals.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
            if can_manage(ctx):
                if status_filter:
                    where.append("ctrl.status=?")
                    vals.append(status_filter)
            else:
                where.extend(["ctrl.status='released'", "ctrl.is_visible_to_general_users=1", "ctrl.is_soft_deleted=0"])

            where_sql = " AND ".join(where)
            base = f"""
                FROM controls ctrl
                JOIN subcategories s ON s.id=ctrl.subcategory_id
                JOIN categories c ON c.id=s.category_id
                JOIN functions f ON f.id=c.function_id
                JOIN role_category_permissions p ON p.category_id=c.id
                JOIN users u ON u.role_id=p.role_id
                WHERE {where_sql}
            """

            total = conn.execute(f"SELECT COUNT(*) {base}", vals).fetchone()[0]
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"""
                SELECT ctrl.id, ctrl.control_id, ctrl.control_text, ctrl.description, ctrl.status,
                       ctrl.is_visible_to_general_users, ctrl.is_soft_deleted,
                       f.code function_code, f.name function_name,
                       c.code category_code, c.name category_name,
                       s.code subcategory_code, s.definition subcategory_definition
                {base}
                ORDER BY {sort_by} {sort_dir}
                LIMIT ? OFFSET ?
                """,
                vals + [page_size, offset],
            ).fetchall()

            opt_where = ["u.id=?"]
            opt_vals = [ctx["id"]]
            if function_id:
                opt_where.append("f.id=?")
                opt_vals.append(function_id)
            opt_sql = " AND ".join(opt_where)
            categories = conn.execute(
                f"""
                SELECT DISTINCT c.code, c.name
                FROM categories c
                JOIN functions f ON f.id=c.function_id
                JOIN role_category_permissions p ON p.category_id=c.id
                JOIN users u ON u.role_id=p.role_id
                WHERE {opt_sql}
                ORDER BY c.code
                """,
                opt_vals,
            ).fetchall()
            subcategories = conn.execute(
                f"""
                SELECT DISTINCT s.code
                FROM subcategories s
                JOIN categories c ON c.id=s.category_id
                JOIN functions f ON f.id=c.function_id
                JOIN role_category_permissions p ON p.category_id=c.id
                JOIN users u ON u.role_id=p.role_id
                WHERE {opt_sql}
                ORDER BY s.code
                """,
                opt_vals,
            ).fetchall()

            return self._json({
                "items": [dict(r) for r in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
                "can_manage": can_manage(ctx),
                "filter_options": {"categories": [dict(x) for x in categories], "subcategories": [dict(x) for x in subcategories]},
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
            user = conn.execute("SELECT id, username FROM users WHERE username=? AND password_hash=?", (payload.get("username", ""), hash_pw(payload.get("password", "")))).fetchone()
            if not user:
                return self._json({"error": "Invalid credentials"}, HTTPStatus.UNAUTHORIZED)
            token = secrets.token_hex(24)
            SESSIONS[token] = {"user_id": user["id"], "username": user["username"]}
            return self._json({"ok": True}, cookie=f"session={token}; HttpOnly; Path=/; SameSite=Lax")

        if self.path == "/api/logout":
            cookie = SimpleCookie(self.headers.get("Cookie"))
            token = cookie.get("session")
            if token:
                SESSIONS.pop(token.value, None)
            return self._json({"ok": True}, cookie="session=; Max-Age=0; Path=/")

        conn, ctx = self._require_auth()
        if not conn:
            return
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

        if self.path in {"/api/controls/create", "/api/controls/edit", "/api/controls/soft-delete", "/api/controls/restore", "/api/controls/bulk-release", "/api/controls/bulk-hide", "/api/controls/deprecate"} and not can_manage(ctx):
            return self._json({"error": "Forbidden"}, HTTPStatus.FORBIDDEN)

        if self.path == "/api/controls/create":
            sub_code = payload.get("subcategory_code", "")
            row = conn.execute("SELECT id, definition FROM subcategories WHERE code=?", (sub_code,)).fetchone()
            if not row:
                return self._json({"error": "Invalid subcategory"}, 400)
            control_id = payload.get("control_id") or sub_code
            text = payload.get("control_text") or row["definition"]
            status = payload.get("status", "hidden")
            visible = 1 if status == "released" else 0
            ts = now_iso()
            conn.execute(
                """
                INSERT INTO controls(control_id,subcategory_id,control_text,description,status,is_visible_to_general_users,is_soft_deleted,created_by,updated_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (control_id, row["id"], text, payload.get("description", ""), status, visible, 0, ctx["username"], ctx["username"], ts, ts),
            )
            audit(conn, control_id, "created", ctx, "", status, payload.get("comment", ""))
            conn.commit()
            return self._json({"ok": True})

        if self.path == "/api/controls/edit":
            cid = payload.get("control_id")
            old = conn.execute("SELECT status, control_text, description FROM controls WHERE control_id=?", (cid,)).fetchone()
            if not old:
                return self._json({"error": "Control not found"}, 404)
            conn.execute(
                "UPDATE controls SET control_text=?, description=?, updated_by=?, updated_at=? WHERE control_id=?",
                (payload.get("control_text", old["control_text"]), payload.get("description", old["description"]), ctx["username"], now_iso(), cid),
            )
            audit(conn, cid, "edited", ctx, old["status"], old["status"], payload.get("comment", ""))
            conn.commit()
            return self._json({"ok": True})

        if self.path in {"/api/controls/bulk-release", "/api/controls/bulk-hide", "/api/controls/soft-delete", "/api/controls/restore", "/api/controls/deprecate"}:
            ids = payload.get("control_ids", [])
            if not ids:
                return self._json({"error": "No controls selected"}, 400)
            action_map = {
                "/api/controls/bulk-release": ("released", 1, 0, "released"),
                "/api/controls/bulk-hide": ("hidden", 0, 0, "hidden"),
                "/api/controls/soft-delete": ("soft_deleted", 0, 1, "soft_deleted"),
                "/api/controls/restore": ("hidden", 0, 0, "restored"),
                "/api/controls/deprecate": ("deprecated", 0, 0, "deprecated"),
            }
            new_status, visible, soft_deleted, action_name = action_map[self.path]
            for cid in ids:
                old = conn.execute("SELECT status FROM controls WHERE control_id=?", (cid,)).fetchone()
                if not old:
                    continue
                conn.execute(
                    "UPDATE controls SET status=?, is_visible_to_general_users=?, is_soft_deleted=?, updated_by=?, updated_at=? WHERE control_id=?",
                    (new_status, visible, soft_deleted, ctx["username"], now_iso(), cid),
                )
                audit(conn, cid, action_name, ctx, old["status"], new_status, payload.get("comment", ""))
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
