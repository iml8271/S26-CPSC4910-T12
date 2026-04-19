from flask import Flask, render_template, request, redirect, url_for, session,abort,flash, Blueprint
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from authentication import auth_bp
from models import db,Users,DriverProfile,SponsorProfile,DriverPointsHistory,SponsorCompany, SupportRequest, DriverCompanyLink
from datetime import datetime
import os

report_bp = Blueprint("report",__name__)

# this code doesn't work as '/' is only meant for the landing page/homepage
# - Karina
@report_bp.route("/reports")
@login_required
def display_landing():
    return render_template("admin/reports/admin_reports_landing.html")

@report_bp.route("/reports/supportrequests",methods=["GET"])
@login_required
def supportrequests():
    stats = (db.session.query(SupportRequest.req_type,func.count(SupportRequest.req_id))
             .group_by(SupportRequest.req_type).all())
    tallied_requests = {item[0]: item[1] for item in stats}

    return render_template("admin/reports/admin_reports_supp_req.html", tallies=tallied_requests)

@report_bp.route("/reports/drivers",methods=["GET"])
@login_required
def driver_report():
    stats = (db.session.query(SponsorCompany.name, func.count(DriverProfile.user_id))
             .join(DriverCompanyLink, SponsorCompany.id == DriverCompanyLink.company_id)
             .join(DriverProfile, DriverCompanyLink.driver_id == DriverProfile.user_id)
             .group_by(SponsorCompany.name)
             .all())


    tallied_requests = {item[0]: item[1] for item in stats}

    return render_template("admin/reports/admin_reports_drivers.html", tallies=tallied_requests)

@report_bp.route("/reports/points", methods=["GET"])
@login_required
def points_report():
    request = db.session.query(DriverPointsHistory) \
        .join(DriverCompanyLink) \
        .join(DriverProfile) \
        .all()

    return render_template("admin/reports/admin_points_report.html", history=request)

@report_bp.route("/audit-log")
def audit_log():
    from models import AuditLog
    from datetime import datetime
    page = request.args.get('page', 1, type=int)
    per_page = 25
    event_filter = request.args.get('event_type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = AuditLog.query.order_by(AuditLog.timestamp.desc())

    if event_filter:
        query = query.filter(AuditLog.event_type == event_filter)
    if date_from:
        query = query.filter(AuditLog.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(AuditLog.timestamp <= datetime.strptime(date_to + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    event_types = db.session.query(AuditLog.event_type).distinct().order_by(AuditLog.event_type).all()
    event_types = [e[0] for e in event_types]

    return render_template("admin/reports/audit_log.html",
                           logs=pagination.items,
                           pagination=pagination,
                           event_types=event_types,
                           current_filter=event_filter,
                           date_from=date_from,
                           date_to=date_to)