import hashlib
import json
import secrets
import sqlite3
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
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            function_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            FOREIGN KEY(function_id) REFERENCES functions(id)
        );
        CREATE TABLE IF NOT EXISTS subcategories (
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            category_id INTEGER NOT NULL,
            definition TEXT NOT NULL,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS functional_groups (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            access_level INTEGER NOT NULL,
            functional_group_id INTEGER NOT NULL,
            FOREIGN KEY(functional_group_id) REFERENCES functional_groups(id)
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role_id INTEGER NOT NULL,
            FOREIGN KEY(role_id) REFERENCES roles(id)
        );
        CREATE TABLE IF NOT EXISTS role_category_permissions (
            role_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            PRIMARY KEY(role_id, category_id),
            FOREIGN KEY(role_id) REFERENCES roles(id),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );
        """
    )

    # Cleanup legacy redundant table (older versions duplicated subcategory text in controls)
    cur.execute("DROP TABLE IF EXISTS controls")

    cur.executemany("INSERT OR IGNORE INTO functions(code,name,description) VALUES(?,?,?)", FUNCTIONS)
    function_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM functions")}

    cur.executemany(
        "INSERT OR IGNORE INTO categories(code,function_id,name,description) VALUES(?,?,?,?)",
        [(code, function_map[fcode], name, description) for code, fcode, name, description in CATEGORIES],
    )
    category_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM categories")}

    cur.executemany(
        "INSERT OR IGNORE INTO subcategories(code,category_id,definition) VALUES(?,?,?)",
        [(scode, category_map[ccode], definition) for scode, ccode, definition in CONTROLS],
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

    users = [
        ("alice", "password123", "compliance_officer"),
        ("ravi", "password123", "risk_officer"),
        ("priya", "password123", "product_manager"),
        ("ops1", "password123", "tech_ops"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO users(username,password_hash,role_id) VALUES(?,?,?)",
        [(u, hash_pw(p), role_map[r]) for u, p, r in users],
    )

    perms = {
        "compliance_officer": ["GV", "ID", "PR", "DE", "RS", "RC"],
        "risk_officer": ["GV", "ID", "DE", "RS", "RC"],
        "product_manager": ["GV", "ID", "PR"],
        "tech_ops": ["PR", "DE", "RS", "RC"],
    }
    function_cats = {}
    for r in cur.execute("SELECT c.id, f.code fcode FROM categories c JOIN functions f ON f.id=c.function_id"):
        function_cats.setdefault(r["fcode"], []).append(r["id"])

    role_permission_rows = []
    for role_name, function_codes in perms.items():
        for fcode in function_codes:
            for cid in function_cats.get(fcode, []):
                role_permission_rows.append((role_map[role_name], cid))
    cur.executemany("INSERT OR IGNORE INTO role_category_permissions(role_id,category_id) VALUES(?,?)", role_permission_rows)

    conn.commit()
    conn.close()


def get_session_user(headers):
    cookie = SimpleCookie(headers.get("Cookie"))
    token = cookie.get("session")
    return SESSIONS.get(token.value) if token else None


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def _serve_static(self, path):
        fpath = STATIC_DIR / path
        if not fpath.exists():
            return self.send_error(404)
        ctype = "text/html"
        if path.endswith(".css"):
            ctype = "text/css"
        if path.endswith(".js"):
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
            me = dict(
                conn.execute(
                    """
                    SELECT u.username, r.name role_name, r.access_level, fg.name functional_group
                    FROM users u
                    JOIN roles r ON r.id=u.role_id
                    JOIN functional_groups fg ON fg.id=r.functional_group_id
                    WHERE u.id=?
                    """,
                    (user["user_id"],),
                ).fetchone()
            )

            rows = conn.execute(
                """
                SELECT
                  f.id function_id, f.code function_code, f.name function_name, f.description function_definition,
                  c.id category_id, c.code category_code, c.name category_name, c.description category_definition,
                  s.id subcategory_id, s.code subcategory_code, s.definition subcategory_definition
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

            f_map = {}
            for r in rows:
                if r["function_id"] not in f_map:
                    f_map[r["function_id"]] = {
                        "id": r["function_id"],
                        "code": r["function_code"],
                        "name": r["function_name"],
                        "definition": r["function_definition"],
                        "categories": {},
                    }
                if r["category_id"] not in f_map[r["function_id"]]["categories"]:
                    f_map[r["function_id"]]["categories"][r["category_id"]] = {
                        "id": r["category_id"],
                        "code": r["category_code"],
                        "name": r["category_name"],
                        "definition": r["category_definition"],
                        "subcategories": [],
                    }
                if r["subcategory_id"]:
                    f_map[r["function_id"]]["categories"][r["category_id"]]["subcategories"].append(
                        {
                            "id": r["subcategory_id"],
                            "code": r["subcategory_code"],
                            "definition": r["subcategory_definition"],
                        }
                    )
            tree = []
            for f in f_map.values():
                f["categories"] = list(f["categories"].values())
                tree.append(f)

            return self._json({"me": me, "tree": tree})

        if parsed.path == "/api/controls":
            params = parse_qs(parsed.query)
            function_id = params.get("function_id", [None])[0]
            category_id = params.get("category_id", [None])[0]
            search = params.get("search", [""])[0]
            sort_by = params.get("sort_by", ["subcategory_code"])[0]
            sort_dir = params.get("sort_dir", ["asc"])[0].upper()
            page = int(params.get("page", [1])[0])
            page_size = min(100, int(params.get("page_size", [10])[0]))

            if sort_by not in {"subcategory_code", "category_code", "function_code"}:
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
                where.append("(s.code LIKE ? OR s.definition LIKE ? OR c.name LIKE ? OR f.name LIKE ?)")
                vals.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

            base = f"""
                FROM subcategories s
                JOIN categories c ON c.id=s.category_id
                JOIN functions f ON f.id=c.function_id
                JOIN role_category_permissions p ON p.category_id=c.id
                JOIN users u ON u.role_id=p.role_id
                WHERE {' AND '.join(where)}
            """
            total = conn.execute(f"SELECT COUNT(*) {base}", vals).fetchone()[0]
            offset = (page - 1) * page_size

            rows = conn.execute(
                f"""
                SELECT
                    f.code function_code, f.name function_name,
                    c.code category_code, c.name category_name,
                    s.code subcategory_code, s.definition subcategory_definition
                {base}
                ORDER BY {sort_by} {sort_dir}
                LIMIT ? OFFSET ?
                """,
                vals + [page_size, offset],
            ).fetchall()

            # normalized projection: control code is the subcategory code (no duplicate storage)
            items = []
            for r in rows:
                obj = dict(r)
                obj["control_code"] = r["subcategory_code"]
                obj["control_source"] = "NIST-CSF-2.0-Core"
                items.append(obj)
            return self._json({"items": items, "total": total, "page": page, "page_size": page_size})

        return self._json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/api/login":
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            conn = db_conn()
            user = conn.execute(
                "SELECT id, username FROM users WHERE username=? AND password_hash=?",
                (payload.get("username", ""), hash_pw(payload.get("password", ""))),
            ).fetchone()
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

        return self._json({"error": "Not found"}, 404)


def run():
    init_db()
    server = HTTPServer(("0.0.0.0", 8000), Handler)
    print("Server running on http://localhost:8000")
    server.serve_forever()


if __name__ == "__main__":
    run()
