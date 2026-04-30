import json
import os
import sys
import threading
import time
import urllib.request
import http.cookiejar

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import app


def call(opener, method, path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"http://127.0.0.1:8010{path}", data=data, headers=headers, method=method)
    try:
        r = opener.open(req)
        return r.getcode(), json.loads(r.read().decode() or "{}")
    except Exception:
        return 403, {}


def main():
    if os.path.exists("csf.db"):
        os.remove("csf.db")
    app.init_db()
    server = app.HTTPServer(("127.0.0.1", 8010), app.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.2)

    users = [
        ("admin", "password123", "L4"),
        ("compliance_user", "password123", "L3"),
        ("product_manager", "password123", "L2"),
        ("viewer_user", "password123", "L1"),
    ]
    print("user,level,dashboard,reg_overview,reg_articles,reg_detail,obligation_release,obligation_commit")
    for username, password, level in users:
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        call(op, "POST", "/api/login", {"username": username, "password": password})
        dash, _ = call(op, "GET", "/api/dashboard")
        ro, _ = call(op, "GET", "/api/regulation-overview")
        ra, list_data = call(op, "GET", "/api/regulation-articles?page=1&page_size=1")
        aid = (list_data.get("items") or [{}])[0].get("article_id", "ART-001")
        rd, detail = call(op, "GET", f"/api/regulation-article-detail?article_id={aid}")
        oid = (detail.get("obligations") or [{"obligation_id": "AI-ART-001-001"}])[0]["obligation_id"]
        rel, _ = call(op, "POST", "/api/regulation-obligations/status", {"obligation_id": oid, "status": "released_visible", "comments": "release"})
        com, _ = call(op, "POST", "/api/regulation-obligations/status", {"obligation_id": oid, "status": "committed", "comments": "commit"})
        print(f"{username},{level},{dash},{ro},{ra},{rd},{rel},{com}")

    server.shutdown()
    server.server_close()


if __name__ == "__main__":
    main()
