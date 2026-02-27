from flask import Flask, Blueprint,render_template, request, redirect, url_for, session,abort,flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from models import db,Users,DriverProfile,SponsorCompany,SponsorProfile,DriverPointsHistory, DriverApplications
from datetime import datetime
from functools import wraps
import csv
import io
from helpers import driver_create,driver_update_points,sponsor_create

sponsor_bp = Blueprint("sponsor",__name__,url_prefix="/sponsor")

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

ALLOWED_EXTENSIONS = {'txt'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
"""
@sponsor_bp.route("/driver_list/add", methods=["GET","POST"])
@login_required
@role_required("sponsor")
def sponsor_add_drivers():
    sponsor_profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    if not sponsor_profile:
        return redirect(url_for("view_sponsor_dashboard"))
    
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
        if not allowed_file(filename):
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
                                user_id = driver_profile.user_id,
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
                    next 
        
        except UnicodeDecodeError:
            flash("Error reading file: Ensure it is saved in UTF-8 encoding.", "danger")
            return redirect(request.url)
        
        return render_template(
        "sponsor/sponsor_add_drivers.html", 
        error_log=error_log, 
        success_count=success_count,
        processed=True  # A flag to show the results div
        )

        for line_num, row in enumerate(reader, start=1):
            # Cleaning
            row = [field.strip() for field in row]

            # Field Count Validation
            if len(row) < 5:
                error_log.append(f"Line {line_num}: Too few fields (got {len(row)})")
                continue

            # Extraction
            type = row[0].upper()
            org  = row[1]
            first_name = row[2]
            last_name  = row[3]
            email     = row[4]
            points = row[5] if len(row) > 5 else ''
            reason    = row[6] if len(row) > 6 else ""

            # Bulk Upload Rules
            if org != "":
                error_log.append(f"Line {line_num}: Must omit the organization name field. Continue.")

            if type == "O":
                error_log.append(f"Line {line_num}: Type 'O' is restricted. Skipped.")
                continue
            elif type == "S":
                if points != '':
                     error_log.append(f"Line {line_num}: Sponsors cannot have points. Continue.")
                     
                if sponsor email exist in server:
                    if points exist:
                        flag error 
                        skip
                if sponsor email not in server:
                    add sponsor
            elif type == "D":
                #Assumes type=="D"
                driver_profile = NULL

                # Driver Checker
                Check if first_name, last_name and email empty:
                    if empty, skip line and log error
                Query driver table for driver profile
                if profile exists:
                    if reason is empty:
                        reason = f"Bulk Upload by Sponsor {sponsor_profile.first_name}"    
                    query drive prfile exisitng points
                    if points exists:
                        new total = points + exisitng points
                    commit new driver points
                
                elif not(first_name,last name and email match a record):
                    create the driver profile
                    driver_profile = new profile
                    if reason is empty:
                        reason = "New Driver"
                    if points is empty: 
                        points = 0
                    upload new driver wiht points
            else:      
                error_log.append(f"Line {line_num}: Invalid type '{type}'. Skipped.")
                skip entire line    


        return redirect(url_for("sponsor_add_drivers"))
    return render_template("sponsor/sponsor_add_drivers.html")
"""
