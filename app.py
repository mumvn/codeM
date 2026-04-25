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
        CREATE TABLE IF NOT EXISTS functions (id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, description TEXT);
        CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, code TEXT UNIQUE, function_id INTEGER, name TEXT, description TEXT,
            FOREIGN KEY(function_id) REFERENCES functions(id));
        CREATE TABLE IF NOT EXISTS controls (id INTEGER PRIMARY KEY, code TEXT UNIQUE, category_id INTEGER, statement TEXT,
            FOREIGN KEY(category_id) REFERENCES categories(id));

        CREATE TABLE IF NOT EXISTS functional_groups (id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT);
        CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY, name TEXT UNIQUE, access_level INTEGER, functional_group_id INTEGER,
            FOREIGN KEY(functional_group_id) REFERENCES functional_groups(id));
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role_id INTEGER,
            FOREIGN KEY(role_id) REFERENCES roles(id));
        CREATE TABLE IF NOT EXISTS role_category_permissions (role_id INTEGER, category_id INTEGER,
            PRIMARY KEY(role_id, category_id),
            FOREIGN KEY(role_id) REFERENCES roles(id),
            FOREIGN KEY(category_id) REFERENCES categories(id));
        """
    )

    cur.executemany("INSERT OR IGNORE INTO functions(code,name,description) VALUES(?,?,?)", FUNCTIONS)
    function_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM functions")}
    cur.executemany(
        "INSERT OR IGNORE INTO categories(code,function_id,name,description) VALUES(?,?,?,?)",
        [(c, function_map[f], n, d) for c, f, n, d in CATEGORIES],
    )
    cat_map = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM categories")}
    cur.executemany(
        "INSERT OR IGNORE INTO controls(code,category_id,statement) VALUES(?,?,?)",
        [(code, cat_map[cat], text) for code, cat, text in CONTROLS],
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

    default_users = [("alice", "password123", "compliance_officer"), ("ravi", "password123", "risk_officer"), ("priya", "password123", "product_manager"), ("ops1", "password123", "tech_ops")]
    cur.executemany("INSERT OR IGNORE INTO users(username,password_hash,role_id) VALUES(?,?,?)", [(u, hash_pw(p), role_map[r]) for u, p, r in default_users])

    # Permissions (least privilege by function focus)
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
        ctype = "text/html" if path.endswith(".html") else "text/css" if path.endswith(".css") else "application/javascript"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(fpath.read_bytes())

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            return self._serve_static("index.html")
        if parsed.path in ["/styles.css", "/app.js"]:
            return self._serve_static(parsed.path[1:])

        user = get_session_user(self.headers)
        if not user:
            return self._json({"error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)

        conn = db_conn()
        if parsed.path == "/api/bootstrap":
            q = """
            SELECT u.username, r.name role_name, r.access_level, fg.name functional_group
            FROM users u JOIN roles r ON u.role_id=r.id JOIN functional_groups fg ON r.functional_group_id=fg.id
            WHERE u.id=?
            """
            me = dict(conn.execute(q, (user["user_id"],)).fetchone())
            cats = conn.execute(
                """
                SELECT c.id, c.code, c.name, f.code function_code, f.name function_name
                FROM categories c
                JOIN functions f ON c.function_id=f.id
                JOIN role_category_permissions p ON p.category_id=c.id
                JOIN users u ON u.role_id=p.role_id
                WHERE u.id=?
                ORDER BY f.id, c.code
                """,
                (user["user_id"],),
            ).fetchall()
            functions = conn.execute(
                "SELECT DISTINCT f.id, f.code, f.name, f.description FROM functions f JOIN categories c ON c.function_id=f.id JOIN role_category_permissions p ON p.category_id=c.id JOIN users u ON u.role_id=p.role_id WHERE u.id=? ORDER BY f.id",
                (user["user_id"],),
            ).fetchall()
            return self._json({"me": me, "functions": [dict(x) for x in functions], "categories": [dict(x) for x in cats]})

        if parsed.path == "/api/controls":
            params = parse_qs(parsed.query)
            category_id = params.get("category_id", [None])[0]
            search = params.get("search", [""])[0]
            sort_by = params.get("sort_by", ["code"])[0]
            sort_dir = params.get("sort_dir", ["asc"])[0].upper()
            page = int(params.get("page", [1])[0])
            page_size = min(int(params.get("page_size", [10])[0]), 100)
            if sort_by not in {"code", "statement"}:
                sort_by = "code"
            if sort_dir not in {"ASC", "DESC"}:
                sort_dir = "ASC"

            where = ["u.id=?"]
            vals = [user["user_id"]]
            if category_id:
                where.append("c.category_id=?")
                vals.append(category_id)
            if search:
                where.append("(c.code LIKE ? OR c.statement LIKE ?)")
                vals.extend([f"%{search}%", f"%{search}%"])
            where_sql = " AND ".join(where)
            base = f"FROM controls c JOIN role_category_permissions p ON p.category_id=c.category_id JOIN users u ON u.role_id=p.role_id WHERE {where_sql}"
            total = conn.execute(f"SELECT COUNT(*) {base}", vals).fetchone()[0]
            offset = (page - 1) * page_size
            rows = conn.execute(f"SELECT DISTINCT c.id, c.code, c.statement, c.category_id {base} ORDER BY c.{sort_by} {sort_dir} LIMIT ? OFFSET ?", vals + [page_size, offset]).fetchall()
            return self._json({"items": [dict(r) for r in rows], "total": total, "page": page, "page_size": page_size})

        self._json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/api/login":
            content_len = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(content_len) or b"{}")
            username = payload.get("username", "")
            password = payload.get("password", "")
            conn = db_conn()
            row = conn.execute("SELECT id, username FROM users WHERE username=? AND password_hash=?", (username, hash_pw(password))).fetchone()
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

        self._json({"error": "Not found"}, 404)


def run():
    init_db()
    server = HTTPServer(("0.0.0.0", 8000), Handler)
    print("Server running on http://localhost:8000")
    server.serve_forever()


if __name__ == "__main__":
    run()
