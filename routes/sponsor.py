from flask import Flask, Blueprint,render_template, request, redirect, url_for, session,abort,flash, current_app,g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from models import db,Users,DriverProfile,SponsorCompany,SponsorProfile,DriverPointsHistory, DriverApplications, DriverCompanyLink
from datetime import datetime
from functools import wraps
import csv
import io
from helpers import *
import os

sponsor_bp = Blueprint("sponsor",__name__,url_prefix="/sponsor")

@sponsor_bp.before_request
def restrict_to_sponsors():
    # User has to be logged in
    if not current_user.is_authenticated:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('auth.handle_login'))

    # User has to be a sponsor
    if current_user.role != "sponsor" and current_user.role != "admin":
        flash("Access denied: Sponsors only.", "danger")
        return redirect(url_for('auth.handle_login'))
    if current_user.role == "admin":
        return None
    
    # User has to have a profile
    if not g.profile:
        flash("Sponsor profile not found. Please contact an admin.", "danger")
        return redirect(url_for('auth.logout'))

# Roles
def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        @login_required
        def decorated_view(*args, **kwargs):
            print("Current user role:", current_user.role)
            print("Allowed roles:", roles)
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

## SETTINGS ----------------------------------
@sponsor_bp.route("/settings",methods=["GET","POST"])
def sponsor_settings():
    sponsor = g.profile
    if request.method == "POST":
        if "sponsor_logo" not in request.files:
            flash("No file selected.")
            return redirect(url_for("sponsor_settings"))

        file = request.files["sponsor_logo"]

        if file.filename == "":
            flash("No file selected.")
            return redirect(url_for("sponsor_settings"))
        
        allowed_types = {"png","jpg","jpeg"}
        extenstion = file.filename.rsplit(".",1)[1].lower() if "." in file.filename else None

        if extenstion in allowed_types:
            filename = secure_filename(file.filename)

            unique_filename = f"logo_co_{sponsor.company_id}_{filename}"
            upload_path = os.path.join(current_app.static_folder, "images/uploads/logos")
            os.makedirs(upload_path, exist_ok=True)

            save_path = os.path.join(upload_path, unique_filename)
            file.save(save_path)

            if sponsor.company:
                sponsor.company.logo_filename = f"images/uploads/logos/{unique_filename}"
                db.session.commit()
                flash("Logo uploaded successfully!", "success")
            else:
                flash("Error: No associated company found.", "danger")
            
            return redirect(url_for("sponsor.sponsor_settings"))
        else:
            flash("Invalid file type. Only PNG, JPG, and JPEG allowed.", "warning")
            return redirect(url_for("sponsor.sponsor_settings"))

    return render_template("sponsor/sponsor_settings.html", sponsor=sponsor)

## ACTIVE DRIVER_LIST --------------------------------
@sponsor_bp.route("/driver_list", methods=["GET","POST"])
def view_drivers():
    drivers = DriverProfile.query.join(DriverCompanyLink).filter(
        DriverCompanyLink.company_id == g.profile.company_id,
        DriverCompanyLink.is_active == True,
        DriverProfile.is_active == True
    ).all()
    return render_template("sponsor/sponsor_view_drivers.html",drivers=drivers)

@sponsor_bp.route("/adjust_points", methods=["POST"])
def adjust_points(sponsor_profile,driver_id):
    try:
        sponsor_profile = g.profile
        driver_profile = DriverProfile.query.join(DriverCompanyLink).filter(
            DriverProfile.user_id == driver_id,
            DriverCompanyLink.company_id == sponsor_profile.company_id
            ).first()
        if not driver_profile:
            flash("Error: Driver not found.")
            return redirect(url_for("sponsor.view_drivers"))
        
        raw_points = request.form.get("points_change", "0")
        points_change = int(raw_points) if raw_points else 0
        reason = request.form.get("reason","").strip() or "Manual adjustment by sponsor"

        driver_update_points(
            driver_profile=driver_profile,
            company_id=sponsor_profile.company_id,
            points_to_add = points_change,
            points_reason = reason,
            sponsor_user_id= sponsor_profile.user_id,
        )
        db.session.refresh(driver_profile)
        flash(f"Successfully adjusted points for {driver_profile.firstname}!")
    except ValueError as ve:
        db.session.rollback()
        flash(f"Update failed: {str(ve)}")
    except Exception as e: 
        db.session.rollback()
        print(f"Adjust Points Error: {e}")
        flash(f"Unable to adjust points for Driver")

    return redirect(url_for("sponsor.view_drivers"))

@sponsor_bp.route("/driver_list/add", methods=["GET","POST"])
def add_drivers():
    sponsor_profile = g.profile
    
    company = sponsor_profile.company
    if not company:
        flash('No associated company found.', 'danger')
        return redirect(request.url)
    
    
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
                if len(row) < 5:
                    print(f"DEBUG: Line {line_num} failed field count: {len(row)}")
                    error_log.append(f"Line {line_num}: Too few fields (got {len(row)})")
                    continue

                # Extraction
                user_type = row[0].upper()
                org_name  = row[1]
                firstname = row[2]
                lastname  = row[3]
                email = row[4]
                points_field = row[5] if len(row) > 5 else ''
                reason = row[6] if len(row) > 6 else ''

                # Extraction Validation -----------------
                if user_type not in ("D","S"):
                    error_log.append(f"Line {line_num}: Invalid type (must be D or S). Skipped.")
                    continue 

                if org_name:
                    error_log.append(f"Line {line_num}: Must omit the organization name field. Continue.")

                if not firstname or not lastname or not email:
                    error_log.append(f"Line {line_num}: Missing personal info. Skipped.")
                    continue

                # Sponsor Specific ---------------------
                if user_type == "S":
                    if points_field:
                        error_log.append(f"Line {line_num}: Sponsors cannot have points. Continue.")
                        
                    user = Users.query.filter_by(email=email).first()
                    if user:
                        if user.sponsor_profile:
                            error_log.append(f"Line {line_num}: Sponsor {email} already exists. Skipped.")
                        else:
                            error_log.append(f"Line {line_num}: User {email} exists for but is not sponsor. Skipped.")
                        continue

                    # Create new sponsor
                    try: 
                        sponsor_create(
                            email=email,
                            firstname=firstname,
                            lastname=lastname,
                            company_id=int(company.id)
                        )
                        success_count += 1
                    except Exception as e:
                        error_log.append(f"Line {line_num}: Error creating sponsor: {str(e)}")
                    continue
                # driver Spefici ---------------------
                elif user_type == "D":
                    try:
                        points_field = int(points_field or 0)
                        reason = (reason or "Bulk Upload")
                        status = "approved"

                        user = Users.query.filter_by(email=email).first()

                        # If the email is in the user and driver profile database,
                        # Only will update the points
                        #If the email is tied to a user, but not a driver
                        # Create new driver profile ONLY and update points
                        if user:
                            # Case : User exists but no driver profile ->
                            # Log error, Create profile + application, continue
                            if not user.driver_profile:
                                error_log.append(f"Line {line_num}: User {email} exists but has no driver profile. Continue.")
                                # create driver profile
                                driver_profile = DriverProfile(
                                    user_id=user.id,
                                    firstname=firstname,
                                    lastname=lastname,
                                    company_id=int(company.id),
                                    is_active=True #auto-activate
                                )
                                db.session.add(driver_profile)

                                # Create application record
                                application = DriverApplications(
                                    user_id=user.id,
                                    company_id=company.id,
                                    status=status,
                                    reason=reason
                                )
                                db.session.add(application)
                                db.session.flush()

                            driver_profile = user.driver_profile

                            # Case: Wrong Company -> Skip Line 
                            if driver_profile.company_id != company.id:
                                error_log.append(f"Line {line_num}: Driver profile doesn't work for {company.name}. Skipped.")
                                continue

                            # Case: Has User Profile & Driver Profile ->
                            # Update Points only
                            driver_update_points(
                                driver_profile = driver_profile,
                                points_to_add = points_field,
                                points_reason = reason,
                                sponsor_user_id= sponsor_profile.user_id,
                            )
                        # Case: Completely new ->
                        # Full Create
                        else:
                            driver_create(
                                email = email,
                                firstname=firstname,
                                lastname=lastname,
                                company_id=int(company.id),
                                points_to_add=points_field,
                                points_reason=reason,
                                status=status,
                                application_reason= reason,
                                sponsor_user_id=sponsor_profile.user_id
                            )
                        db.session.commit()
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
        "sponsor/sponsor_add_drivers.html", 
        error_log=error_log, 
        success_count=success_count,
        processed=True  # A flag to show the results div
        )
    return render_template("sponsor/sponsor_add_drivers.html")

## PENDING DRIVER_LIST ----------------------------------
@sponsor_bp.route("/driver_list/applications/pending", methods=["GET","POST"])
def pending_drivers():
    sponsor_profile = g.profile
    applications = DriverApplications.query.filter_by(
        company_id=sponsor_profile.company_id,
        status="pending").all()
    return render_template("sponsor/sponsor_pending_drivers.html",applications=applications)

@sponsor_bp.route("/driver_list/applications/process/<int:app_id>", methods=["POST"])
def process_application(app_id):
    application = DriverApplications.query.get_or_404(app_id)
    action = request.form.get("action")

    try:
        if action == "accept":
            driver_accept_application(
                driver_profile=application.driver_profile,
                company_id=application.company_id,
                sponsor_user_id=g.profile.user_id
            )
            flash("Driver accepted and linked successfully!")
        
        elif action == "reject":
            reason = request.form.get("reason", "Processed by Sponsor")
            driver_reject_application(
                driver_profile=application.driver_profile,
                company_id=application.company_id,
                reason=reason
            )
            flash("Application rejected.")

    except Exception as e:
        db.session.rollback()
        flash(f"Error processing application: {str(e)}")

    return redirect(url_for("sponsor.pending_drivers"))

@sponsor_bp.route("/driver_list/accept/<int:app_id>", methods=["POST"])
def driver_accept(app_id):
    application = DriverApplications.query.get_or_404(app_id)
    action = request.form.get("action")
    reason = request.form.get("reason", "Processed by Sponsor")
    try:
        sponsor_profile = g.profile
        reason = request.form.get("reason").strip() or "Sponsor Accepted"

        if not application:
            flash("Application not found.", "danger")
        
        application.status = "accepted"
        application.status_reason = reason
        application.response_date = datetime.now()
        
        if application:
            application.status = "accepted"
            if application.driver_profile:
                application.driver_profile.is_active = True
            db.session.commit()
            flash("Driver accepted!", "success")
        else:
            flash("Application not found.", "danger")
    except Exception as e:
        db.session.rollback()
        print(f"Accept Error: {e}")
        flash(f"Unable to accept Driver")
    
    return redirect(url_for("sponsor.pending_drivers"))

@sponsor_bp.route("/driver_list/reject", methods=["POST"])
def driver_reject():
    driver_id= request.form.get("driver_id")
    reason = request.form.get("reason").strip()
    
    try:
        application = DriverApplications.query.filter_by(user_id=driver_id).first()
        
        if application:
            application.status = "rejected"
            application.reason = reason
            
            if application.driver_profile:
                application.driver_profile.is_active = False
                
            db.session.commit()
            flash("Driver rejected.", "warning")
            
    except Exception as e:
        db.session.rollback()
        flash("Unable to process rejection.", "danger")

    return redirect(url_for("sponsor.pending_drivers"))


