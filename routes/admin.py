from flask import Flask, Blueprint,render_template, request, redirect, url_for, session,abort,flash, current_app,g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from models import db,Users,DriverProfile,SponsorCompany,SponsorProfile,DriverPointsHistory, DriverApplications,DriverCompanyLink
from helpers import *
import csv
from sqlalchemy import or_,not_
from decimal import Decimal
from audit import log_audit_event
from datetime import datetime
import os


admin_bp = Blueprint("admin",__name__,url_prefix="/admin")

@admin_bp.before_request
def restrict_to_admin():
    # Allow end_impersonation to be called by non-admins (they hold a real_admin_id in session)
    if request.endpoint == "admin.end_impersonation":
        real_admin_id = session.get("real_admin_id")
        if real_admin_id:
            return None  # Let it through
        abort(403)

    # User has to be logged in
    if not current_user.is_authenticated:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('auth.handle_login'))

    # User has to be an admin
    if current_user.role != "admin":
        flash("Access denied: Admins only.", "danger")
        return redirect(url_for('dashboard'))
    
    # User has to have a profile
    if not g.profile:
        print(f"DEBUG: Admin {current_user.username} has no profile in g.profile")
        flash("Admin profile not found. Please contact an admin.", "danger")
        return redirect(url_for('dashboard'))
    
# SETTINGS----
@admin_bp.route("/settings",methods=["GET","POST"])
def admin_settings():
    admin = g.profile
    if request.method == "POST":
        try:
            firstname = request.form.get("firstname").strip()
            lastname = request.form.get("lastname").strip()
            admin.firstname = firstname
            admin.lastname = lastname
            db.session.commit()
            flash("Settings updated successfully!", "success")
        except Exception as e:
            db.session.rollback()
            print(f"Error updating settings: {e}")
            flash("An error occurred while saving.", "danger")
    return render_template("admin/admin_personal.html", admin=admin)

@admin_bp.route("/master_signup", methods=["GET","POST"])
def master_signup():
    all_companies = SponsorCompany.query.all()
    if request.method == "POST":
        try:
            role = request.form.get("creation_type")
            if role == "company":
                name = request.form.get("org_name").strip()
                pv = request.form.get("point_value").strip()
                phone = request.form.get("phone").strip()
                email = request.form.get("org_email").strip()
                new_company = SponsorCompany(name=name,
                    email=email,
                    phone=phone,
                    points_conversion=Decimal(pv))
                db.session.add(new_company)
                db.session.commit()
                log_audit_event("company_created", user_id=current_user.id, username=current_user.username,
                                details=f"Company: {name}")
                print("Created Company")
                flash(f"Created Company: {name}", "success")
            else:
                firstname = request.form.get("firstname").strip()
                lastname = request.form.get("lastname").strip()
                email = request.form.get("email").strip()
                #password = request.form.get("password").strip()

                if role == "admin":
                    admin_create(email=email,firstname=firstname,
                        lastname=lastname,password="Password1")
                elif role == "sponsor":
                    company_id = request.form.get("company_id")
                    sponsor_create(email=email,firstname=firstname,lastname=lastname,
                        password="Password1",company_id=company_id)
                elif role == "driver":
                    driver_create_profile(email=email,firstname=firstname,lastname=lastname,
                        username=generate_unique_username(email),password="Password1")
                db.session.commit()
                log_audit_event("account_created", user_id=current_user.id, username=current_user.username,
                                details=f"Admin created {role}: {email}")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
            print(f"Error: {e}")
    return render_template("admin/admin_masteradd.html",all_companies=all_companies)

@admin_bp.route("/sponsor_list", methods=["GET","POST"])
def admin_sponsor_list():
    sponsors = SponsorProfile.query.all()
    return render_template("admin/admin_sponsor_list.html",sponsors=sponsors)

@admin_bp.route("/company_list", methods=["GET","POST"])
def all_companies_list():
    companies = SponsorCompany.query.all()
    return render_template("admin/admin_company_list.html",companies=companies)


@admin_bp.route("/company_settings/<int:company_id>",methods=["GET","POST"])
def company_settings(company_id):
    admin = g.profile
    company = SponsorCompany.query.filter_by(id=company_id).first()
    if request.method == "POST":
        try:
            points_conversion = request.form.get("point_conversion")
            if points_conversion:
                company.points_conversion = points_conversion
                db.session.commit()
                flash("Points Convert saved!", "success")
            if "sponsor_logo" in request.files:
                file = request.files["sponsor_logo"]

                if file.filename:
                    allowed_types = {"png","jpg","jpeg"}
                    extenstion = file.filename.rsplit(".",1)[1].lower() if "." in file.filename else None

                    if extenstion in allowed_types:
                        filename = secure_filename(file.filename)

                        unique_filename = f"logo_co_{company_id}_{filename}"
                        upload_path = os.path.join(current_app.static_folder, "images/uploads/logos")
                        os.makedirs(upload_path, exist_ok=True)

                        save_path = os.path.join(upload_path, unique_filename)
                        file.save(save_path)

                        if company:
                            company.logo_filename = f"images/uploads/logos/{unique_filename}"
                            db.session.commit()
                            flash("Logo uploaded successfully!", "success")
                        else:
                            flash("Error: No associated company found.", "danger")
                    return redirect(url_for("sponsor.sponsor_settings"))
            else:
                flash("Invalid file type. Only PNG, JPG, and JPEG allowed.", "warning")
                return redirect(url_for("sponsor.sponsor_settings"))
        except Exception as e:
            db.session.rollback()
            print(f"Error updating settings: {e}")
            flash("An error occurred while saving.", "danger")
    return render_template("admin/admin_company.html", company=company)


@admin_bp.route("/directory", methods=["GET", "POST"])
@admin_bp.route("/directory/<role>/<int:company_id>", methods=["GET", "POST"])
def directory(role=None, company_id=None):
    '''
    query = Users.query.filter(or_(Users.role == "driver", Users.role == "sponsor"))
    if role and role != "all":
        query.filter_by(role=role)
    if company_id and company_id != 0:
        query = query.join(DriverCompanyLink).filter_by(company_id=company_id)
    # 4. Filter by Search (Optional: Real-time via URL)
    search = request.args.get('search', '')
    if search:
        query = query.filter(or_(
            Users.username.ilike(f"%{search}%"),
            Users.email.ilike(f"%{search}%")
        ))

    users = query.all()
    companies = SponsorCompany.query.all()

    return render_template('directory.html', 
                           users=users, 
                           companies=companies, 
                           current_role=role, 
                           current_company=company_id)
    '''
    all_users = Users.query.all()
    return render_template('directory.html',users=all_users)

@admin_bp.route("/profile-card/<int:user_id>", methods=["GET","POST"])
def view_profilecard(user_id):
    
    user = Users.query.get_or_404(user_id)
    
    # 2. Get all companies so we can show the "Apply" list
    all_companies = SponsorCompany.query.all()
    
    return render_template('usercard.html', profile=user, all_companies=all_companies)

@admin_bp.route("/profile-card/<int:user_id>/apply/<int:company_id>", methods=["POST"])
def apply_driver(user_id,company_id):
    try:
        ext_driver_auto_link(driver_id=user_id,company_id=company_id)
    except Exception as e:
        # flash(f"Error: {str(e)}", "danger")
        print(f"Error: {e}")
    return redirect(url_for('admin.view_profilecard',user_id=user_id))


@admin_bp.route("/profile-card/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    user = Users.query.get_or_404(user_id)
    
    try:
        db.session.delete(user)
        db.session.commit()
        log_audit_event("account_deleted", user_id=current_user.id, username=current_user.username,
                        details=f"Deleted user: {user.username} (ID: {user_id})")
        # flash(f"User {user.username} deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        # flash(f"Error deleting user: {str(e)}", "danger")
        print("Delete Errdor")
    return redirect(url_for('admin.directory'))

@admin_bp.route("/bulk_upload", methods=["GET","POST"])
def bulk_upload():
    error_log = []
    success_count = 0
    processed = False

    if request.method == "POST":
        if "bulk_upload_file" not in request.files:
            error_log.append("File part missing in the request.")

        else:
            bulk_file = request.files["bulk_upload_file"]

            if bulk_file.filename == "":
                error_log.append("No file selected.")

            elif not secure_filename(bulk_file.filename).lower().endswith('.txt'):
                error_log.append("Invalid file type. Only .txt files are permitted.")

            else:
                try:
                    bulk_file.stream.seek(0)
                    data_stream = (line.decode('utf-8').strip() for line in bulk_file.stream)
                    valid_lines = (line for line in data_stream if line)
                    reader = csv.reader(valid_lines, delimiter='|', quoting=csv.QUOTE_NONE)
                    processed = True

                    for line_num, row in enumerate(reader, start=1):
                        row = [field.strip() for field in row]

                        if len(row) < 1:
                            error_log.append(f"Line {line_num}: Empty line. Skipped.")
                            continue

                        user_type = row[0].upper()

                        # Validate type
                        if user_type not in ("D", "S", "O"):
                            error_log.append(f"Line {line_num}: Invalid type '{row[0]}'. Must be D, S, or O. Skipped.")
                            continue

                        # O type — only needs org name, no user fields
                        if user_type == "O":
                            if len(row) < 2 or not row[1]:
                                error_log.append(f"Line {line_num}: O type missing organization name. Skipped.")
                                continue
                            # O type should have no user fields
                            if len(row) > 2 and any(row[2:]):
                                error_log.append(f"Line {line_num}: O type should not have user fields. Skipped.")
                                continue
                            org_name = row[1]
                            prev_error_count = len(error_log)
                            error_log = bulk_line_upload(
                                line_num, error_log,
                                type=user_type,
                                company_name=org_name
                            )
                            if len(error_log) == prev_error_count:
                                success_count += 1
                            continue

                        # D and S — need at least 5 fields
                        if len(row) < 5:
                            error_log.append(f"Line {line_num}: Too few fields (got {len(row)}). Skipped.")
                            continue

                        org_name  = row[1]
                        firstname = row[2]
                        lastname  = row[3]
                        email     = row[4].lower()
                        points_field = row[5].strip() if len(row) > 5 else ''
                        reason_field = row[6].strip() if len(row) > 6 else ''

                        # For admin uploads, org name is required for D and S
                        if user_type in ("D", "S") and not org_name:
                            error_log.append(f"Line {line_num}: Organization name is required for admins. Skipped.")
                            continue

                        # Points and reason must come together
                        points_present = bool(points_field)
                        reason_present = bool(reason_field)
                        if points_present != reason_present:
                            error_log.append(f"Line {line_num}: Both points and reason are required if either is provided. Skipped.")
                            continue

                        points = None
                        reason = None
                        if points_field:
                            try:
                                points = int(points_field)
                            except ValueError:
                                error_log.append(f"Line {line_num}: Points value '{points_field}' is not a valid integer. Skipped.")
                                continue
                            reason = reason_field

                        prev_error_count = len(error_log)
                        error_log = bulk_line_upload(
                            line_num, error_log,
                            type=user_type,
                            company_name=org_name,
                            firstname=firstname,
                            lastname=lastname,
                            email=email,
                            points=points,
                            reason=reason
                        )
                        if len(error_log) == prev_error_count:
                            success_count += 1

                except UnicodeDecodeError:
                    error_log.append("Error reading file: Ensure it is saved in UTF-8 encoding.")
                except Exception as e:
                    db.session.rollback()
                    error_log.append(f"An unexpected error occurred: {str(e)}")

    return render_template(
        "admin/admin_bulk_upload.html",
        error_log=error_log,
        success_count=success_count,
        processed=processed
    )

@admin_bp.route("/remove_link/<int:link_id>", methods=["POST"])
def admin_remove_link(link_id):
    remove_link(link_id=link_id,remover_id=g.profile.user_id)
    return redirect(request.referrer or url_for('admin.directory'))

@admin_bp.route("/update_points/<int:driver_id>", methods=["POST"])
def update_points(driver_id):
    try:
        admin_profile = g.profile
        points = request.form.get("points",0)
        reason = request.form.get("reason", "Processed by Sponsor")
        company_id = request.form.get("company_id")
        driver_change_points(driver_id=driver_id,
            company_id=int(company_id),
            points=int(points),
            sponsor_id=admin_profile.user.id,
            reason=reason)
        db.session.commit()
        flash("Points updated successfully!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating points: {str(e)}", "danger")
        
    return redirect(request.referrer or url_for('admin.directory'))




## IMPERSONATE--------------------------
## IMPERSONATE --------------------------

@admin_bp.route("/impersonate/<int:user_id>", methods=["POST"])
def impersonate_user(user_id):
    target = Users.query.get_or_404(user_id)

    if target.role == "admin":
        flash("Cannot impersonate another admin.", "danger")
        return redirect(url_for("admin.directory"))

    # Store the real admin's ID in session before switching
    session["impersonating_as"] = target.id
    session["real_admin_id"] = current_user.id
    session["real_user_role"] = current_user.role

    '''
    log_audit_event(
        "impersonation_start",
        user_id=current_user.id,
        username=current_user.username,
        details=f"Impersonating user: {target.username} (ID: {target.id})"
    )
    '''

    login_user(target)
    flash(f"You are now impersonating {target.username}. Click 'End Impersonation' to return.", "warning")
    return redirect(url_for("dashboard"))


@admin_bp.route("/impersonate/end", methods=["POST"])
def end_impersonation():
    real_admin_id = session.pop("real_admin_id", None)
    session.pop("impersonating_as", None)

    if not real_admin_id:
        flash("No impersonation session found.", "danger")
        return redirect(url_for("dashboard"))

    real_admin = Users.query.get(real_admin_id)
    if not real_admin or real_admin.role != "admin":
        flash("Could not restore admin session.", "danger")
        return redirect(url_for("auth.handle_login"))

    '''
    log_audit_event(
        "impersonation_end",
        user_id=real_admin.id,
        username=real_admin.username,
        details=f"Ended impersonation of user ID: {session.get('impersonating_as', 'unknown')}"
    )
    '''
    login_user(real_admin)
    flash("Impersonation ended. You are back as yourself.", "success")
    return redirect(url_for("dashboard"))

@admin_bp.route("/audit-log")
def view_audit_log():
    from models import AuditLog
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

    return render_template("admin/audit_log.html",
                           logs=pagination.items,
                           pagination=pagination,
                           event_types=event_types,
                           current_filter=event_filter,
                           date_from=date_from,
                           date_to=date_to)