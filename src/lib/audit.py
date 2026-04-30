from src.lib.db import get_conn
from datetime import datetime

def log_audit(entity_type: str, entity_id: str, action: str, actor: str, payload: str = ""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_logs(entity_type, entity_id, action, actor, payload, created_at) VALUES(?,?,?,?,?,?)",
        (entity_type, entity_id, action, actor, payload, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
