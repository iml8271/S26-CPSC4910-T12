from flask import Flask, render_template, request, redirect, url_for, session,abort,flash, Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from authentication import auth_bp
from models import db,Users,DriverProfile,SponsorProfile,DriverPointsHistory,SponsorCompany, SupportRequest
from datetime import datetime
from flask_migrate import Migrate
import os

supp_bp = Blueprint("support",__name__)

@supp_bp.route('/submitted', methods=['POST'])
@login_required
def submit_req():
    sourceID = current_user.id
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    sourceORG = profile.company_id
    rType = request.form.get("request_type")
    details = request.form.get("details")

    new_req = SupportRequest(source_id = sourceID, source_org = sourceORG, req_type = rType, req_details = details)

    db.session.add(new_req)
    db.session.commit()
    return redirect(url_for('view_driver_dashboard'))


@supp_bp.route('/admin/requests', methods=['GET'])
@login_required
def admin_view_requests():
    all_requests = SupportRequest.query.order_by(SupportRequest.creation_date.desc()).all()

    return render_template('support/admin_supp_req_view.html', requests=all_requests)

@supp_bp.route('/sponsor/requests', methods=['GET'])
@login_required
def sponsor_view_requests():
    all_requests = SupportRequest.query.filter_by(source_org=current_user.company_id).order_by(SupportRequest.creation_date.desc())

    return render_template('support_supp_req_view.html', requests=all_requests)

@supp_bp.route('/admin/requests/open', methods=['GET'])
@login_required
def admin_view_requests_open():
    all_requests = SupportRequest.query.filter_by(status='Open').order_by(SupportRequest.creation_date.desc())

    return render_template('support/admin_supp_req_view.html', requests=all_requests)

@supp_bp.route('/sponsor/requests/open', methods=['GET'])
@login_required
def sponsor_view_requests_open():
    all_requests = SupportRequest.query.filter_by(source_org=current_user.company_id, status='Open')\
                                                    .order_by(SupportRequest.creation_date.desc())

    return render_template('support_supp_req_view.html', requests=all_requests)

@supp_bp.route('/requests/close', methods=['POST'])
@login_required
def close_request():
    req_id = request.form.get("request_id")
    support_req = SupportRequest.query.get(req_id)
    support_req.status = 'Closed'
    db.session.commit()

@supp_bp.route('/supportRequest')
def support_form():
    return render_template("support/support_request_submission_form.html")

@supp_bp.route('/requestDetails', methods=['GET'])
def view_req_details():
    support_req = SupportRequest.query.get(req_id)
    return render_template("support/request_details.html")

@supp_bp.route('/admin/requestDetails', methods=['GET'])
def admin_support_list():
    return render_template("support/admin_supp_req_view.html")





