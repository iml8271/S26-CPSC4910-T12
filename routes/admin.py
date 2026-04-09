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


admin_bp = Blueprint("admin",__name__,url_prefix="/admin")

@admin_bp.before_request
def restrict_to_admin():
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
                password = request.form.get("password").strip()

                if role == "admin":
                    admin_create(email=email,firstname=firstname,
                        lastname=lastname,password=password)
                elif role == "sponsor":
                    company_id = request.form.get("company_id")
                    sponsor_create(email=email,firstname=firstname,lastname=lastname,
                        password=password,company_id=company_id)
                elif role == "driver":
                    driver_create_profile(email=email,firstname=firstname,lastname=lastname,
                        username=generate_unique_username(email),password=password)
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

@admin_bp.route("/directory", methods=["GET", "POST"])
@admin_bp.route("/directory/<role>/<int:company_id>", methods=["GET", "POST"])
def directory(role=None, company_id=None):
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
    if request.method == "POST":
        # Check if the key exists in the request
        if "bulk_upload_file" not in request.files:
            flash("File part missing in the request.", "danger")
            return redirect(request.url)

        bulk_file = request.files["bulk_upload_file"]

        # Check if user actually selected a file
        if bulk_file.filename == "":
            flash("No file selected.", "warning")
            return redirect(request.url)

        # Clean the filename and check the extension
        filename = secure_filename(bulk_file.filename)
        if not filename.lower().endswith('.txt'):
            flash('Invalid file type. Only .txt files are permitted.', 'danger')
            return redirect(request.url)
    
        try: 
            
            bulk_file.stream.seek(0)

            data_stream = (line.decode('utf-8').strip() for line in bulk_file.stream)
            # Remove empty strings
            valid_lines = (line for line in data_stream if line)

            reader = csv.reader(
                valid_lines,
                delimiter='|',
                quoting=csv.QUOTE_NONE,
            )
            print(f"DEBUG: Filename is {bulk_file.filename}")

            error_log = []
            success_count = 0

            print("--- Starting File Processing ---")
            for line_num, row in enumerate(reader, start=1):
                print(f"DEBUG: Line {line_num} content: {row}")
                # Cleaning
                row = [field.strip() for field in row]

                # Field Count Validation
                if len(row) < 2:
                    print(f"DEBUG: Line {line_num} failed field count: {len(row)}")
                    error_log.append(f"Line {line_num}: Too few fields (got {len(row)})")
                    continue

                # Extraction
                user_type = row[0].upper()
                org_name  = row[1].strip()

                # Extraction Validation -----------------
                if user_type not in ("D","S","O"):
                    error_log.append(f"Line {line_num}: Invalid type (must be D,S,or O). Skipped.")
                    continue 

                if not org_name:
                    error_log.append(f"Line {line_num}: Must contain organization name field. Continue.")
                    continue

                company = SponsorCompany.query.filter(SponsorCompany.name.ilike(org_name)).first()

                # ORGANIZATION ----------------------
                if user_type == "O":
                    # Field Count Validation
                    if len(row) < 2:
                        print(f"DEBUG: Line {line_num} failed field count: {len(row)}")
                        error_log.append(f"Line {line_num}: Too few fields (got {len(row)})")
                        continue   
                    '''
                    # Data Validation: no other fields
                    if firstname or lastname or email or points_field or reason:
                        error_log.append(f"Line {line_num}: New Organzation cannot continue other information. Skipped.")
                        continue
                    '''
                    if company:
                        error_log.append(f"Line {line_num}: '{org_name}' already exists. Skipped.")
                        continue
                    #if company already exists, exit line
                    try: 
                        # Add Organization
                        new_org = SponsorCompany(name=org_name,
                                                 email=None,
                                                 phone=None)
                        db.session.add(new_org)
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        error_log.append(f"Line {line_num}: Error creating org: {str(e)}")
                    continue

                # Data Validation
                firstname = row[2]
                lastname  = row[3]
                email = row[4].lower()
                points_field = row[5] if len(row) > 5 else ''
                reason = row[6] if len(row) > 6 else ''
                # Field Count Validation
                if len(row) < 5:
                    print(f"DEBUG: Line {line_num} failed field count: {len(row)}")
                    error_log.append(f"Line {line_num}: Too few fields (got {len(row)})")
                    continue
                
                if not company:
                    error_log.append(f"Line {line_num}: '{org_name}' does not exist. Skipped.")
                    continue

                if not firstname or not lastname or not email:
                    error_log.append(f"Line {line_num}: Missing personal info. Skipped.")
                    continue

                # Search for User
                user = Users.query.filter_by(email=email).first()

                # Add New Sponsor ---------------------
                if user_type == "S":
                    # Data Validation: optional fields
                    if points_field or reason:
                        error_log.append(f"Line {line_num}: Sponsors cannot have points. Continue.")
                    
                    # Case: User + Profile already exists
                    if user:
                        if user.driver_profile or user.admin_profile:
                            error_log.append(f"Line {line_num}: User {email} exists for but is not sponsor. Skipped.")
                        if user.sponsor_profile:
                            error_log.append(f"Line {line_num}: Sponsor {email} already exists. Skipped.")
                        continue

                    # Case: User exists only
                    try:
                        sponsor_profile = SponsorProfile(
                            firstname=firstname,
                            lastname = lastname,
                            company = company
                        )
                        db.session.add(sponsor_profile)
                        db.session.commit()
                        continue
                    except Exception as e:
                        db.session.rollback()
                        error_log.append(f"Line {line_num}: Error creating sponsor: {str(e)}")
                    # Case: No User & No Profile, new person
                    try: 
                        sponsor_create(
                            email=email,
                            firstname=firstname,
                            lastname=lastname,
                            company_id=int(company.id)
                        )
                        success_count += 1
                    except Exception as e:
                        db.session.rollback()
                        error_log.append(f"Line {line_num}: Error creating sponsor: {str(e)}")
                    continue
                # driver Spefici ---------------------
                elif user_type == "D":
                    if bool(points_field) != bool(reason):
                        error_log.append(f"Line {line_num}: Both points and reason are required if either is provided. Skipped.")
                        continue
                    try:
                        # Data Validation: in case of no data given
                        points_field = int(points_field or 0)
                        reason = (reason or "Bulk Upload")

                        DriverService.sync_driver_relationship(
                            email=email,
                            fname=firstname,
                            lname=lastname,
                            company_id=company.id,
                            points=points_field,
                            reason=reason,
                            sponsor_id=current_user.id
                        )
                        success_count += 1
                    except ValueError as ve:
                        db.session.rollback()
                        error_log.append(f"Line {line_num}: Invalid data: {str(ve)}")
                        continue
                    except Exception as e:
                        db.session.rollback()
                        error_log.append(f"Line {line_num}: Processing failed: {str(e)}")
                        continue
                else:      
                    error_log.append(f"Line {line_num}: Invalid type '{user_type}'. Skipped.")
                    continue
        
        except UnicodeDecodeError:
            flash("Error reading file: Ensure it is saved in UTF-8 encoding.", "danger")
            return redirect(request.url)
        
        return render_template(
        "admin/admin_bulk_upload.html", 
        error_log=error_log, 
        success_count=success_count,
        processed=True  # A flag to show the results div
        )
    return render_template("admin/admin_bulk_upload.html")


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