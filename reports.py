from flask import Flask, render_template, request, redirect, url_for, session,abort,flash, Blueprint
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from authentication import auth_bp
from models import db,Users,DriverProfile,SponsorProfile,DriverPointsHistory,SponsorCompany, SupportRequest
from datetime import datetime
from flask_migrate import Migrate
import os

report_bp = Blueprint("report",__name__)

@report_bp.route("/")
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
def supportrequests():
    stats = (db.session.query(DriverProfile.company,func.count(DriverProfile.id))
             .group_by(DriverProfile.company).all())
    tallied_requests = {item[0]: item[1] for item in stats}

    return render_template("admin/reports/admin_reports_drivers.html", tallies=tallied_requests)
