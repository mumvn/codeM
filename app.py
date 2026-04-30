import json
import secrets
import sqlite3
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "mvp.db"
STATIC_DIR = BASE_DIR / "static"
SESSIONS = {}


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT, name TEXT, role TEXT);
        CREATE TABLE IF NOT EXISTS properties(id INTEGER PRIMARY KEY, name TEXT, address TEXT, property_type TEXT, ownership_status TEXT, construction_year INTEGER, notes TEXT);
        CREATE TABLE IF NOT EXISTS floors(id INTEGER PRIMARY KEY, property_id INTEGER, name TEXT);
        CREATE TABLE IF NOT EXISTS rooms(id INTEGER PRIMARY KEY, floor_id INTEGER, name TEXT, room_type TEXT);
        CREATE TABLE IF NOT EXISTS assets(id INTEGER PRIMARY KEY, room_id INTEGER, name TEXT, asset_type TEXT);
        CREATE TABLE IF NOT EXISTS asset_parts(id INTEGER PRIMARY KEY, asset_id INTEGER, name TEXT);
        CREATE TABLE IF NOT EXISTS vendors(id INTEGER PRIMARY KEY, name TEXT, category TEXT, contact_details TEXT, service_area TEXT, notes TEXT);
        CREATE TABLE IF NOT EXISTS responsibilities(id INTEGER PRIMARY KEY, target_type TEXT, target_id INTEGER, assigned_to_type TEXT, assigned_to_id INTEGER, responsibility_type TEXT, assignment_date TEXT, due_date TEXT, notes TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS issues(id INTEGER PRIMARY KEY, title TEXT, description TEXT, severity TEXT, priority TEXT, status TEXT, property_id INTEGER, floor_id INTEGER, room_id INTEGER, asset_id INTEGER, part_id INTEGER, responsible_id INTEGER, due_date TEXT, estimated_cost REAL, actual_cost REAL);
        CREATE TABLE IF NOT EXISTS issue_status_history(id INTEGER PRIMARY KEY, issue_id INTEGER, from_status TEXT, to_status TEXT, changed_at TEXT, note TEXT);
        CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, name TEXT, document_type TEXT, linked_type TEXT, linked_id INTEGER, expiry_date TEXT, upload_date TEXT, file_path TEXT);
        CREATE TABLE IF NOT EXISTS costs(id INTEGER PRIMARY KEY, amount REAL, currency TEXT, category TEXT, invoice_number TEXT, tax_relevant INTEGER, payment_status TEXT, linked_type TEXT, linked_id INTEGER, document_id INTEGER);
        CREATE TABLE IF NOT EXISTS government_checklist(id INTEGER PRIMARY KEY, property_id INTEGER, item_name TEXT, status TEXT, reference_number TEXT, external_link TEXT);
        CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, notif_type TEXT, message TEXT, status TEXT, related_type TEXT, related_id INTEGER, created_at TEXT);
        CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY, entity_type TEXT, entity_id TEXT, action TEXT, actor TEXT, payload TEXT, created_at TEXT);
        """
    )
    cur.execute("INSERT OR IGNORE INTO users(id,email,password,name,role) VALUES(1,'owner@example.com','password','Owner User','Property Owner')")
    if cur.execute("SELECT COUNT(*) c FROM properties").fetchone()[0] == 0:
        seed(cur)
    conn.commit()
    conn.close()


def seed(cur):
    cur.execute("INSERT INTO properties(name,address,property_type,ownership_status,construction_year,notes) VALUES(?,?,?,?,?,?)", ("Sample Family House", "123 Lakeview Ave", "House", "Owned", 2012, "Demo property"))
    pid = cur.lastrowid
    cur.execute("INSERT INTO floors(property_id,name) VALUES(?,?)", (pid, "Ground Floor"))
    gf = cur.lastrowid
    cur.execute("INSERT INTO floors(property_id,name) VALUES(?,?)", (pid, "First Floor"))
    ff = cur.lastrowid
    rooms = [(gf, "Bathroom 1", "Bathroom"), (gf, "Kitchen", "Kitchen"), (gf, "Living Room", "Living"), (ff, "Bedroom 1", "Bedroom"), (ff, "Balcony", "Balcony")]
    room_ids = {}
    for f, n, t in rooms:
        cur.execute("INSERT INTO rooms(floor_id,name,room_type) VALUES(?,?,?)", (f, n, t)); room_ids[n] = cur.lastrowid
    assets = [("Bathroom window", room_ids["Bathroom 1"]), ("Shower mixer", room_ids["Bathroom 1"]), ("Toilet flush", room_ids["Bathroom 1"]), ("Kitchen sink", room_ids["Kitchen"]), ("Bedroom window", room_ids["Bedroom 1"]), ("Main door", room_ids["Living Room"]), ("Electrical sockets", room_ids["Living Room"]), ("Water pipe", room_ids["Bathroom 1"]), ("Roof drainage", room_ids["Balcony"])]
    for n, r in assets: cur.execute("INSERT INTO assets(room_id,name,asset_type) VALUES(?,?,?)", (r, n, "Component"))
    for v in ["Plumber", "Electrician", "Carpenter", "Interior contractor", "Painter"]:
        cur.execute("INSERT INTO vendors(name,category,contact_details,service_area,notes) VALUES(?,?,?,?,?)", (v, v, "N/A", "Local", "seed"))
    cur.execute("INSERT INTO issues(title,description,severity,priority,status,property_id) VALUES(?,?,?,?,?,?)", ("Bathroom leakage", "Leak near shower mixer", "High", "High", "IN_PROGRESS", pid))


def json_response(handler, data, status=200, cookie=None):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    if cookie:
        handler.send_header("Set-Cookie", cookie)
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode())


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path in ["/app.js", "/styles.css", "/index.html"]:
            f = "index.html" if path == "/" else path.lstrip("/")
            ctype = "text/html" if f.endswith("html") else ("application/javascript" if f.endswith("js") else "text/css")
            self.send_response(200); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write((STATIC_DIR / f).read_bytes()); return
        if path == "/api/bootstrap":
            conn = db_conn()
            data = {
                "properties": [dict(r) for r in conn.execute("SELECT * FROM properties")],
                "issues": [dict(r) for r in conn.execute("SELECT * FROM issues")],
                "vendors": [dict(r) for r in conn.execute("SELECT * FROM vendors")],
                "documents": [dict(r) for r in conn.execute("SELECT * FROM documents")],
                "costs": [dict(r) for r in conn.execute("SELECT * FROM costs")],
                "checklist": [dict(r) for r in conn.execute("SELECT * FROM government_checklist")],
            }
            conn.close(); return json_response(self, data)
        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or "{}")
        conn = db_conn(); cur = conn.cursor()
        if path == "/api/login":
            u = cur.execute("SELECT * FROM users WHERE email=? AND password=?", (body.get("email"), body.get("password"))).fetchone()
            if not u: conn.close(); return json_response(self, {"error": "Invalid credentials"}, 401)
            t = secrets.token_hex(16); SESSIONS[t] = u["id"]; conn.close(); return json_response(self, {"ok": True}, cookie=f"session={t}; Path=/")
        if path == "/api/properties":
            cur.execute("INSERT INTO properties(name,address,property_type,ownership_status,construction_year,notes) VALUES(?,?,?,?,?,?)", (body["name"], body.get("address"), body.get("property_type"), body.get("ownership_status"), body.get("construction_year"), body.get("notes"))); pid = cur.lastrowid
            cur.execute("INSERT INTO audit_logs(entity_type,entity_id,action,actor,created_at) VALUES(?,?,?,?,?)", ("property", str(pid), "created", "owner@example.com", datetime.utcnow().isoformat()))
        elif path == "/api/issues":
            cur.execute("INSERT INTO issues(title,description,severity,priority,status,property_id,room_id,asset_id,due_date,estimated_cost) VALUES(?,?,?,?,?,?,?,?,?,?)", (body["title"], body.get("description"), body.get("severity","Medium"), body.get("priority","Medium"), "NEW", body.get("property_id"), body.get("room_id"), body.get("asset_id"), body.get("due_date"), body.get("estimated_cost",0)))
        elif path == "/api/issues/status":
            issue = cur.execute("SELECT status FROM issues WHERE id=?", (body["issue_id"],)).fetchone(); old = issue[0]
            cur.execute("UPDATE issues SET status=? WHERE id=?", (body["status"], body["issue_id"]))
            cur.execute("INSERT INTO issue_status_history(issue_id,from_status,to_status,changed_at,note) VALUES(?,?,?,?,?)", (body["issue_id"], old, body["status"], datetime.utcnow().isoformat(), body.get("note","")))
        elif path == "/api/documents":
            cur.execute("INSERT INTO documents(name,document_type,linked_type,linked_id,expiry_date,upload_date,file_path) VALUES(?,?,?,?,?,?,?)", (body["name"], body["document_type"], body.get("linked_type"), body.get("linked_id"), body.get("expiry_date"), datetime.utcnow().isoformat(), body.get("file_path","mock://file")))
        elif path == "/api/costs":
            cur.execute("INSERT INTO costs(amount,currency,category,invoice_number,tax_relevant,payment_status,linked_type,linked_id,document_id) VALUES(?,?,?,?,?,?,?,?,?)", (body["amount"], body.get("currency","USD"), body.get("category"), body.get("invoice_number"), 1 if body.get("tax_relevant") else 0, body.get("payment_status","PENDING"), body.get("linked_type"), body.get("linked_id"), body.get("document_id")))
        conn.commit(); conn.close(); return json_response(self, {"ok": True})


if __name__ == "__main__":
    init_db()
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
