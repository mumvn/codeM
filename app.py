import hashlib
import json
import secrets
import sqlite3
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from data.csf_seed import FUNCTIONS, CATEGORIES, CONTROLS

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "csf.db"
STATIC_DIR = BASE_DIR / "static"

SESSIONS = {}


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
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE,
            name TEXT,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE,
            function_id INTEGER,
            name TEXT,
            description TEXT,
            FOREIGN KEY(function_id) REFERENCES functions(id)
        );

        CREATE TABLE IF NOT EXISTS subcategories (
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE,
            category_id INTEGER,
            name TEXT,
            definition TEXT,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS controls (
            id INTEGER PRIMARY KEY,
            subcategory_id INTEGER,
            control_code TEXT,
            control_type TEXT,
            details TEXT,
            FOREIGN KEY(subcategory_id) REFERENCES subcategories(id)
        );

        CREATE TABLE IF NOT EXISTS functional_groups (id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT);
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            access_level INTEGER,
            functional_group_id INTEGER,
            FOREIGN KEY(functional_group_id) REFERENCES functional_groups(id)
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            role_id INTEGER,
            FOREIGN KEY(role_id) REFERENCES roles(id)
        );
        CREATE TABLE IF NOT EXISTS role_category_permissions (
            role_id INTEGER,
            category_id INTEGER,
            PRIMARY KEY(role_id, category_id),
            FOREIGN KEY(role_id) REFERENCES roles(id),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );
        """
    )


    # Backward-compatible migration for older local DBs
    controls_cols = {row[1] for row in cur.execute("PRAGMA table_info(controls)").fetchall()}
    expected_controls_cols = {"id", "subcategory_id", "control_code", "control_type", "details"}
    if controls_cols and controls_cols != expected_controls_cols:
        cur.executescript(
            """
            DROP TABLE IF EXISTS controls;
            CREATE TABLE controls (
                id INTEGER PRIMARY KEY,
                subcategory_id INTEGER,
                control_code TEXT,
                control_type TEXT,
                details TEXT,
                FOREIGN KEY(subcategory_id) REFERENCES subcategories(id)
            );
            """
        )

    subcat_cols = {row[1] for row in cur.execute("PRAGMA table_info(subcategories)").fetchall()}
    expected_subcat_cols = {"id", "code", "category_id", "name", "definition"}
    if subcat_cols and subcat_cols != expected_subcat_cols:
        cur.executescript(
            """
            DROP TABLE IF EXISTS subcategories;
            CREATE TABLE subcategories (
                id INTEGER PRIMARY KEY,
                code TEXT UNIQUE,
                category_id INTEGER,
                name TEXT,
                definition TEXT,
                FOREIGN KEY(category_id) REFERENCES categories(id)
            );
            """
        )

    cur.executemany("INSERT OR IGNORE INTO functions(code,name,description) VALUES(?,?,?)", FUNCTIONS)
    function_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM functions")}

    cur.executemany(
        "INSERT OR IGNORE INTO categories(code,function_id,name,description) VALUES(?,?,?,?)",
        [(c, function_map[f], n, d) for c, f, n, d in CATEGORIES],
    )
    cat_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM categories")}

    # Subcategories are CSF Core outcomes from Appendix A (CONTROLS seed list)
    subcat_rows = []
    control_rows = []
    for code, cat_code, definition in CONTROLS:
        subcat_rows.append((code, cat_map[cat_code], code, definition))
    cur.executemany(
        "INSERT OR IGNORE INTO subcategories(code,category_id,name,definition) VALUES(?,?,?,?)",
        subcat_rows,
    )

    subcat_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM subcategories")}
    for code, _cat_code, definition in CONTROLS:
        control_rows.append((subcat_map[code], code, "NIST-CSF-2.0-Core", definition))

    cur.executemany(
        "INSERT OR IGNORE INTO controls(subcategory_id,control_code,control_type,details) VALUES(?,?,?,?)",
        control_rows,
    )

    groups = [
        ("Compliance", "Compliance officers and auditors"),
        ("Risk", "Risk officers and governance teams"),
        ("Product", "IT product management"),
        ("Operations", "Technical operations and SOC teams"),
    ]
    cur.executemany("INSERT OR IGNORE INTO functional_groups(name,description) VALUES(?,?)", groups)
    group_map = {r["name"]: r["id"] for r in cur.execute("SELECT id,name FROM functional_groups")}

    roles = [
        ("compliance_officer", 4, group_map["Compliance"]),
        ("risk_officer", 3, group_map["Risk"]),
        ("product_manager", 2, group_map["Product"]),
        ("tech_ops", 1, group_map["Operations"]),
    ]
    cur.executemany("INSERT OR IGNORE INTO roles(name,access_level,functional_group_id) VALUES(?,?,?)", roles)
    role_map = {r["name"]: r["id"] for r in cur.execute("SELECT id,name FROM roles")}

    default_users = [
        ("alice", "password123", "compliance_officer"),
        ("ravi", "password123", "risk_officer"),
        ("priya", "password123", "product_manager"),
        ("ops1", "password123", "tech_ops"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO users(username,password_hash,role_id) VALUES(?,?,?)",
        [(u, hash_pw(p), role_map[r]) for u, p, r in default_users],
    )

    perms = {
        "compliance_officer": ["GV", "ID", "PR", "DE", "RS", "RC"],
        "risk_officer": ["GV", "ID", "DE", "RS", "RC"],
        "product_manager": ["GV", "ID", "PR"],
        "tech_ops": ["PR", "DE", "RS", "RC"],
    }
    function_cats = {}
    for r in cur.execute("SELECT c.id, f.code AS fcode FROM categories c JOIN functions f ON c.function_id=f.id"):
        function_cats.setdefault(r["fcode"], []).append(r["id"])

    rows = []
    for role_name, fn_codes in perms.items():
        for fcode in fn_codes:
            for cid in function_cats.get(fcode, []):
                rows.append((role_map[role_name], cid))
    cur.executemany("INSERT OR IGNORE INTO role_category_permissions(role_id,category_id) VALUES(?,?)", rows)

    conn.commit()
    conn.close()


def get_session_user(headers):
    cookie = SimpleCookie(headers.get("Cookie"))
    token = cookie.get("session")
    if not token:
        return None
    return SESSIONS.get(token.value)


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def _serve_static(self, path="index.html"):
        fpath = STATIC_DIR / path
        if not fpath.exists():
            self.send_error(404)
            return

        ctype = "text/html"
        if path.endswith(".css"):
            ctype = "text/css"
        elif path.endswith(".js"):
            ctype = "application/javascript"

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(fpath.read_bytes())

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ["/", "/index.html"]:
            return self._serve_static("index.html")
        if parsed.path in ["/styles.css", "/app.js"]:
            return self._serve_static(parsed.path[1:])

        user = get_session_user(self.headers)
        if not user:
            return self._json({"error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)

        conn = db_conn()

        if parsed.path == "/api/bootstrap":
            me_q = """
                SELECT u.username, r.name role_name, r.access_level, fg.name functional_group
                FROM users u
                JOIN roles r ON u.role_id=r.id
                JOIN functional_groups fg ON r.functional_group_id=fg.id
                WHERE u.id=?
            """
            me = dict(conn.execute(me_q, (user["user_id"],)).fetchone())

            rows = conn.execute(
                """
                SELECT
                    f.id AS function_id, f.code AS function_code, f.name AS function_name, f.description AS function_definition,
                    c.id AS category_id, c.code AS category_code, c.name AS category_name, c.description AS category_definition,
                    s.id AS subcategory_id, s.code AS subcategory_code, s.name AS subcategory_name, s.definition AS subcategory_definition
                FROM functions f
                JOIN categories c ON c.function_id=f.id
                JOIN role_category_permissions p ON p.category_id=c.id
                JOIN users u ON u.role_id=p.role_id
                LEFT JOIN subcategories s ON s.category_id=c.id
                WHERE u.id=?
                ORDER BY f.id, c.code, s.code
                """,
                (user["user_id"],),
            ).fetchall()

            fn_map = {}
            for r in rows:
                fkey = r["function_id"]
                if fkey not in fn_map:
                    fn_map[fkey] = {
                        "id": r["function_id"],
                        "code": r["function_code"],
                        "name": r["function_name"],
                        "definition": r["function_definition"],
                        "categories": {},
                    }
                ckey = r["category_id"]
                if ckey not in fn_map[fkey]["categories"]:
                    fn_map[fkey]["categories"][ckey] = {
                        "id": r["category_id"],
                        "code": r["category_code"],
                        "name": r["category_name"],
                        "definition": r["category_definition"],
                        "subcategories": [],
                    }
                if r["subcategory_id"]:
                    fn_map[fkey]["categories"][ckey]["subcategories"].append(
                        {
                            "id": r["subcategory_id"],
                            "code": r["subcategory_code"],
                            "name": r["subcategory_name"],
                            "definition": r["subcategory_definition"],
                        }
                    )

            tree = []
            for f in fn_map.values():
                f["categories"] = list(f["categories"].values())
                tree.append(f)

            return self._json({"me": me, "tree": tree})

        if parsed.path == "/api/controls":
            params = parse_qs(parsed.query)
            category_id = params.get("category_id", [None])[0]
            function_id = params.get("function_id", [None])[0]
            search = params.get("search", [""])[0]
            sort_by = params.get("sort_by", ["subcategory_code"])[0]
            sort_dir = params.get("sort_dir", ["asc"])[0].upper()
            page = int(params.get("page", [1])[0])
            page_size = min(int(params.get("page_size", [10])[0]), 100)
            if sort_by not in {"subcategory_code", "subcategory_name", "control_code"}:
                sort_by = "subcategory_code"
            if sort_dir not in {"ASC", "DESC"}:
                sort_dir = "ASC"

            where = ["u.id=?"]
            vals = [user["user_id"]]
            if function_id:
                where.append("f.id=?")
                vals.append(function_id)
            if category_id:
                where.append("c.id=?")
                vals.append(category_id)
            if search:
                where.append("(s.code LIKE ? OR s.definition LIKE ? OR c.name LIKE ?)")
                vals.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

            where_sql = " AND ".join(where)
            base = f"""
                FROM controls ctrl
                JOIN subcategories s ON ctrl.subcategory_id=s.id
                JOIN categories c ON s.category_id=c.id
                JOIN functions f ON c.function_id=f.id
                JOIN role_category_permissions p ON p.category_id=c.id
                JOIN users u ON u.role_id=p.role_id
                WHERE {where_sql}
            """
            total = conn.execute(f"SELECT COUNT(*) {base}", vals).fetchone()[0]
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"""
                SELECT
                    f.code function_code, f.name function_name,
                    c.code category_code, c.name category_name,
                    s.code subcategory_code, s.name subcategory_name, s.definition subcategory_definition,
                    ctrl.control_code, ctrl.control_type, ctrl.details
                {base}
                ORDER BY {sort_by} {sort_dir}
                LIMIT ? OFFSET ?
                """,
                vals + [page_size, offset],
            ).fetchall()

            return self._json({"items": [dict(r) for r in rows], "total": total, "page": page, "page_size": page_size})

        return self._json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/api/login":
            content_len = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(content_len) or b"{}")
            username = payload.get("username", "")
            password = payload.get("password", "")

            conn = db_conn()
            row = conn.execute(
                "SELECT id, username FROM users WHERE username=? AND password_hash=?",
                (username, hash_pw(password)),
            ).fetchone()
            if not row:
                return self._json({"error": "Invalid credentials"}, HTTPStatus.UNAUTHORIZED)
            token = secrets.token_hex(24)
            SESSIONS[token] = {"user_id": row["id"], "username": row["username"]}
            return self._json({"ok": True}, cookie=f"session={token}; HttpOnly; Path=/; SameSite=Lax")

        if self.path == "/api/logout":
            cookie = SimpleCookie(self.headers.get("Cookie"))
            token = cookie.get("session")
            if token:
                SESSIONS.pop(token.value, None)
            return self._json({"ok": True}, cookie="session=; Max-Age=0; Path=/")

        return self._json({"error": "Not found"}, 404)


def run():
    init_db()
    server = HTTPServer(("0.0.0.0", 8000), Handler)
    print("Server running on http://localhost:8000")
    server.serve_forever()


if __name__ == "__main__":
    run()
