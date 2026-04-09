from models import db, AuditLog
from flask import request

def log_audit_event(event_type, user_id=None, username=None, details=None):
    entry = AuditLog(
        event_type=event_type,
        user_id=user_id,
        username=username,
        ip_address=request.remote_addr if request else None,
        details=details
    )
    db.session.add(entry)
    db.session.commit()