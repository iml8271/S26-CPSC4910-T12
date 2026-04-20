from flask import Flask, render_template, request, redirect, url_for, session,abort,flash, Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from authentication import auth_bp
from models import db,Users,DriverProfile,SponsorProfile,DriverPointsHistory,SponsorCompany, SupportRequest, DriverCompanyLink
from datetime import datetime, timedelta
import os

supp_bp = Blueprint("support",__name__)

@supp_bp.route('/submitted', methods=['POST'])
@login_required
def submit_req():
    sourceID = current_user.id
    sourceORG = DriverCompanyLink.query.filter_by(driver_id=current_user.id, is_active = True).first().company_id
    rType = request.form.get("request_type")
    details = request.form.get("details")

    new_req = SupportRequest(source_id = sourceID, source_org = sourceORG, req_type = rType, req_details = details)

    db.session.add(new_req)
    db.session.commit()
    return redirect(url_for('dashboard'))


@supp_bp.route('/admin/requests', methods=['GET'])
@login_required
def admin_view_requests():
    all_requests = SupportRequest.query.order_by(SupportRequest.creation_date.desc()).all()

    return render_template('support/admin_supp_req_view.html', requests=all_requests)

@supp_bp.route('/admin/requests/time', methods=['GET'])
@login_required
def admin_view_requests_prevDays():
    timeframe = request.args.get('prevDays', default=7, type=int)
    cutoff_date = datetime.utcnow() - timedelta(days=int(timeframe))

    filtered_requests = (SupportRequest.query.filter(SupportRequest.creation_date >= cutoff_date)
                         .order_by(SupportRequest.creation_date.desc()).all())

    return render_template('support/admin_supp_req_view.html', requests=filtered_requests)

@supp_bp.route('/admin/requests/open', methods=['GET'])
@login_required
def admin_view_requests_open():
    all_requests = SupportRequest.query.filter_by(status='Open').order_by(SupportRequest.creation_date.desc())

    return render_template('support/admin_supp_req_view.html', requests=all_requests)

@supp_bp.route('/admin/requests/sponsor', methods=['GET'])
@login_required
def admin_view_sponsor():
    org_id = request.args.get('org_id')
    all_requests = SupportRequest.query.filter_by(source_org=org_id, status='Open') \
        .order_by(SupportRequest.creation_date.desc())

    return render_template('admin_supp_req_view.html', requests=all_requests)

@supp_bp.route('/sponsor/requests', methods=['GET'])
@login_required
def sponsor_view_requests():
    all_requests = SupportRequest.query.filter_by(source_org=current_user.sponsor_profile.company_id).order_by(SupportRequest.creation_date.desc())

    return render_template('support/sponsor_supp_req_view.html', requests=all_requests)

@supp_bp.route('/sponsor/requests/open', methods=['GET'])
@login_required
def sponsor_view_requests_open():
    all_requests = SupportRequest.query.filter_by(source_org=current_user.sponsor_profile.company_id, status='Open')\
                                                    .order_by(SupportRequest.creation_date.desc())

    return render_template('support/sponsor_supp_req_view.html', requests=all_requests)



@supp_bp.route('/requests/close/<int:request_id>', methods=['POST'])
@login_required
def close_request(request_id):
    support_req = SupportRequest.query.get(request_id)
    support_req.status = 'Closed'
    db.session.commit()
    return redirect(url_for('support.admin_view_requests'))

@supp_bp.route('/supportRequest')
def support_form():
    return render_template("support/support_request_submission_form.html")

@supp_bp.route('/requestDetails/<int:req_id>', methods=['GET'])
def view_req_details(req_id):
    support_req = SupportRequest.query.get(req_id)
    return render_template("support/request_details.html", request=support_req)

@supp_bp.route('/admin/requestDetails', methods=['GET'])
def admin_support_list():
    return render_template("support/admin_supp_req_view.html")

@supp_bp.route('/user/requests', methods=['GET'])
@login_required
def user_view_requests():
    all_requests = SupportRequest.query.filter_by(source_id=current_user.id)\
                                                    .order_by(SupportRequest.creation_date.desc())

    return render_template('support/req_by_user.html', requests=all_requests)

@supp_bp.route('/user/requests/open', methods=['GET'])
@login_required
def user_view_requests_open():
    all_requests = SupportRequest.query.filter_by(source_id=current_user.id, status='Open')\
                                                    .order_by(SupportRequest.creation_date.desc())\
                                                    .all()

    return render_template('support/req_by_user.html', requests=all_requests)
@supp_bp.route('/orgs', methods=['GET'])
@login_required
def get_orgs():
    sponsors = SponsorCompany.query.all()
    return sponsors





