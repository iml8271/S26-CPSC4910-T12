from flask import Flask, Blueprint,render_template, request, redirect, url_for, session,abort,flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from models import db,Users,DriverProfile,SponsorCompany,SponsorProfile
from datetime import datetime
from functools import wraps
import csv
import io

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

ALLOWED_EXTENSIONS = {'txt', 'csv'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        #Check file
        if "bulk_upload_file" not in request.files:
            flash("No file selected.")
            return redirect(url_for("sponsor_add_drivers"))
        bulk_file = request.files["bulk_upload_file"]
        if bulk_file.filename == "":
            flash("No file selected.")
            return redirect(url_for("sponsor_settings"))
        if not allowed_file(bulk_file.filename):
            flash('Invalid file type. Only .txt and .csv allowed.', 'danger')
            return redirect(request.url)
        
        error_log = []
        success_count = 0

        bulk_file.stream.seek(0)
        reader = csv.reader(
            (line.decode('utf-8') for line in bulk_file.stream),
            delimiter='|',
            quoting=csv.QUOTE_NONE,
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
                     
                if email exist in server:
                    if points exist:
                        flag error 
                        skip
                if email not in server:
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
