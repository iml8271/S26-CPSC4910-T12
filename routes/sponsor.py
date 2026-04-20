from flask import Flask, Blueprint,render_template, request, redirect, url_for, session,abort,flash, current_app,g, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db,Users,DriverProfile,SponsorCompany,SponsorProfile,DriverPointsHistory, DriverApplications, DriverCompanyLink,SponsorCompanyRules
from datetime import datetime
from functools import wraps
import csv
import io
from helpers import *
import os
import requests
from sqlalchemy import func
from models import AuditLog, DriverCompanyLink

sponsor_bp = Blueprint("sponsor",__name__,url_prefix="/sponsor")

@sponsor_bp.before_request
def restrict_to_sponsors():
    if request.endpoint == "sponsor.end_impersonation":
        real_sponsor_id = session.get("real_sponsor_id")
        if real_sponsor_id:
            return None  # Let it through
        abort(403)
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
        try:
            firstname = request.form.get("firstname").strip()
            lastname = request.form.get("lastname").strip()
            sponsor.firstname = firstname
            sponsor.lastname = lastname
            db.session.commit()
            flash("Settings updated successfully!", "success")
        except Exception as e:
            db.session.rollback()
            print(f"Error updating settings: {e}")
            flash("An error occurred while saving.", "danger")
    return render_template("sponsor/sponsor_personal.html", sponsor=sponsor)

@sponsor_bp.route("/company_settings",methods=["GET","POST"])
def company_settings():
    sponsor = g.profile
    if request.method == "POST":
        try:
            points_conversion = request.form.get("point_conversion")
            if points_conversion:
                points_conversion = float(points_conversion)
                if sponsor.company.points_conversion != points_conversion:
                    sponsor.company.points_conversion = points_conversion
                    db.session.commit()
                    flash("Points Convert saved!", "success")
            if "sponsor_logo" in request.files:
                file = request.files["sponsor_logo"]

                if file.filename != "":
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
            else:
                flash("Invalid file type. Only PNG, JPG, and JPEG allowed.", "warning")
                return redirect(url_for("sponsor.company_settings"))
        except Exception as e:
            db.session.rollback()
            print(f"Error updating settings: {e}")
            flash("An error occurred while saving.", "danger")
        return redirect(url_for("sponsor.company_settings"))
    return render_template("sponsor/sponsor_settings.html", sponsor=sponsor)

## ACTIVE DRIVER_LIST --------------------------------
@sponsor_bp.route("/driver_list", methods=["GET","POST"])
def view_drivers():
    active_drivers = DriverCompanyLink.query.filter_by(
        company_id=g.profile.company_id,
        is_active=True ).join(DriverProfile).all()
    return render_template("sponsor/sponsor_view_drivers.html",drivers=active_drivers)

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

@sponsor_bp.route("/driver_list/update_points/<int:driver_id>", methods=["POST"])
def update_points(driver_id):
    try:
        sponsor_profile = g.profile
        points = request.form.get("points",0)
        reason = request.form.get("reason", "Processed by Sponsor")
        driver_change_points(driver_id=driver_id,
            company_id=sponsor_profile.company_id,
            points=int(points),
            sponsor_id=sponsor_profile.user.id,
            reason=reason)
        db.session.commit()
        flash("Points updated successfully!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating points: {str(e)}", "danger")
        
    return redirect(url_for('sponsor.view_drivers'))

@sponsor_bp.route("/remove_link/<int:driver_id>", methods=["POST"])
def sponsor_remove_link(driver_id):
    link = DriverCompanyLink.query.filter_by(
        driver_id=driver_id,
        company_id=g.profile.company.id).first()
    remove_link(link_id=link.id,remover_id=g.profile.user_id)
    return redirect(request.referrer or url_for('sponsor.view_drivers'))

@sponsor_bp.route("/driver_list/add", methods=["GET","POST"])
def add_drivers():
    sponsor_profile = g.profile
    company = sponsor_profile.company
    if not company:
        flash('No associated company found.', 'danger')
        return redirect(url_for('sponsor.driver_list'))

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

                        # Sponsors cannot use O type
                        if user_type == "O":
                            error_log.append(f"Line {line_num}: Sponsors cannot use 'O' type. Skipped.")
                            continue

                        if user_type not in ("D", "S"):
                            error_log.append(f"Line {line_num}: Invalid type '{user_type}' (must be D or S). Skipped.")
                            continue

                        if len(row) < 5:
                            error_log.append(f"Line {line_num}: Too few fields (got {len(row)}). Skipped.")
                            continue

                        org_name     = row[1]
                        firstname    = row[2]
                        lastname     = row[3]
                        email        = row[4].lower()
                        points_field = row[5].strip() if len(row) > 5 else ''
                        reason_field = row[6].strip() if len(row) > 6 else ''

                        if org_name:
                            error_log.append(f"Line {line_num}: Cannot contain company name. Skipped.")
                            continue

                        # Points validation before calling helper
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
                            if not reason_field:
                                error_log.append(f"Line {line_num}: Points provided but reason is missing. Skipped.")
                                continue
                            reason = reason_field

                        prev_error_count = len(error_log)

                        error_log = bulk_line_upload(
                            line_num, error_log,
                            type=user_type,
                            company_name=company.name,
                            firstname=firstname,
                            lastname=lastname,
                            email=email,
                            points=points,
                            reason=reason
                        )

                        # If no new errors were added, the line succeeded
                        if len(error_log) == prev_error_count:
                            success_count += 1

                except UnicodeDecodeError:
                    error_log.append("Error reading file: Ensure it is saved in UTF-8 encoding.")

    return render_template(
        "sponsor/sponsor_add_drivers.html",
        error_log=error_log,
        success_count=success_count,
        processed=processed
    )

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

@sponsor_bp.route("/impersonate/<int:user_id>", methods=["POST"])
def impersonate_user(user_id):
    target = Users.query.get_or_404(user_id)

    if target.role == "admin":
        flash("Cannot impersonate admin.", "danger")
        return redirect(url_for("dashboard"))

    # Store the real admin's ID in session before switching
    session["impersonating_as"] = target.id
    session["real_sponsor_id"] = current_user.id
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


@sponsor_bp.route("/impersonate/end", methods=["POST"])
def end_impersonation():
    real_sponsor_id = session.pop("real_sponsor_id", None)
    session.pop("impersonating_as", None)

    if not real_sponsor_id:
        flash("No impersonation session found.", "danger")
        return redirect(url_for("dashboard"))

    real_sponsor = Users.query.get(real_sponsor_id)
    if not real_sponsor or real_sponsor.role != "sponsor":
        flash("Could not restore sponsor session.", "danger")
        print("Could not restore sponsor session.")
        return redirect(url_for("auth.handle_login"))

    '''
    log_audit_event(
        "impersonation_end",
        user_id=real_admin.id,
        username=real_admin.username,
        details=f"Ended impersonation of user ID: {session.get('impersonating_as', 'unknown')}"
    )
    '''
    login_user(real_sponsor)
    flash("Impersonation ended. You are back as yourself.", "success")
    return redirect(url_for("dashboard"))

# ORGANIZATION RULES --------------------------------------
@sponsor_bp.route("/organization/rules", methods=["GET"])
def view_org_rules():
    profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    sourceORG = profile.company_id
    good_request = SponsorCompanyRules.query.filter_by(company_id = sourceORG, nature = "good").all()
    bad_request =  SponsorCompanyRules.query.filter_by(company_id = sourceORG, nature = "bad").all()
    return render_template("/sponsor/sponsor_view_rules.html", request1 = good_request, request2 = bad_request)

@sponsor_bp.route("/organization/rules", methods=["POST"])
def delete_rule():
    #get the right rule
    id = request.form.get("rr_target")
    rule = SponsorCompanyRules.query.get(id)
    #delete the rule
    db.session.delete(rule)
    db.session.commit()
    return redirect(url_for("sponsor.view_org_rules"))


@sponsor_bp.route("/sponsor/organization/rules/new_rule")
def new_rule():
    return render_template("/sponsor/sponsor_add_rule.html")

@sponsor_bp.route("/sponsor/organization/rules/submit", methods=["POST"])
def submit_rule():
    profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    sourceORG = profile.company_id
    rType = request.form.get("rule_type")
    details = request.form.get("details")

    new_rule = SponsorCompanyRules(company_id=sourceORG, nature=rType, rule=details)

    db.session.add(new_rule)
    db.session.commit()
    return redirect(url_for("sponsor.view_org_rules"))

# Hardcoded catalog

catalog_price_range = {"min": 0, "max": 10000}
@sponsor_bp.route("/sponsor/sponsor_catalog_editor")
def sponsor_catalog_editor():
    return render_template("sponsor/sponsor_catalog_editor.html", items=catalog_items)

@sponsor_bp.route('/sponsor/sponsor_catalog/set-price-range', methods=['POST'])
def sponsor_catalog_set_price_range():
    min_price = int(request.form.get("min_price", 0))
    max_price = int(request.form.get("max_price", 10000))

    if min_price > max_price:
        flash('error min price greater than max')
        return redirect(url_for('sponsor_catalog'))

    catalog_price_range["min"] = min_price
    catalog_price_range["max"] = max_price

    flash(f'Point range: {min_price} - {max_price} pts')
    return redirect(url_for('sponsor.sponsor_catalog_editor'))

@sponsor_bp.route("/sponsor/sponsor_catalog_editor/add", methods=["POST"])
def sponsor_catalog_add():
    price = int(request.form.get("price"))
    if price < catalog_price_range["min"] or price > catalog_price_range["max"]:
        flash(f"Price must be between {catalog_price_range['min']} and {catalog_price_range['max']} pts.")
        return redirect(url_for("sponsor.sponsor_catalog_editor"))

    catalog_items.append({
        "name": request.form.get("name"),
        "description": request.form.get("description"),
        "price": int(request.form.get("price"))
    })
    flash("item added successfully")
    return redirect(url_for("sponsor.sponsor_catalog_editor"))

@sponsor_bp.route("/sponsor/sponsor_catalog_editor/edit/<int:item_index>", methods=["POST"])
def sponsor_catalog_edit(item_index):
    price = int(request.form.get("price"))
    if price < catalog_price_range["min"] or price > catalog_price_range["max"]:
        flash(f"Price must be between {catalog_price_range['min']} and {catalog_price_range['max']} pts.")
        return redirect(url_for("sponsor.sponsor_catalog_editor"))

    if 0 <= item_index < len(catalog_items):
        catalog_items[item_index] = {
            "name": request.form.get("name"),
            "description": request.form.get("description"),
            "price": int(request.form.get("price"))
        }
        flash("Item price changed sucessfuly")
    return redirect(url_for("sponsor.sponsor_catalog_editor"))

@sponsor_bp.route("/sponsor/sponsor_catalog_editor/delete/<int:item_index>", methods=["POST"])
def sponsor_catalog_delete(item_index):
    if 0 <= item_index < len(catalog_items):
        catalog_items.pop(item_index)
        flash("Item deleted successfully yay!")
    return redirect(url_for("sponsor.sponsor_catalog_editor"))

@sponsor_bp.route("/sponsor/reports/points",methods=["GET"])
def points_report():
    profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    target_id = profile.company_id
    request = db.session.query(DriverPointsHistory).join(SponsorProfile).filter(SponsorProfile.company_id == target_id).all()
    return render_template("admin/reports/admin_points_report.html", history = request)

# CATALOG --------------------
@sponsor_bp.route("/search_api",methods=["GET"])
def search_api():
    explicitVal = "No"
    itunes_url = "https://itunes.apple.com/search"
    params = {
        "term": "Michael+Jackson",
        "media": "all",
        "limit": 50,
        "explicit": explicitVal
    }

    results = requests.get(itunes_url, params=params)
    data = results.json()

    return render_template("sponsor/sponsor_catalog_editor.html", items=data['results'])

@sponsor_bp.route("/search_api_specific", methods=["GET", "POST"])
def search_api_specific():
    term = request.form.get("user_search")
    term = term.replace(" ", "+")
    mediaType = request.form.get("media_type")
    sortType = request.form.get("sort_type")
    itunes_url = "https://itunes.apple.com/search"

    params = {
        "term": term,
        "media": mediaType,
        "limit": 50,
        "explicit": "No"
    }

    results = requests.get(itunes_url, params=params)
    data = results.json()
    items = data.get('results', [])

    if sortType == "Price (Asc)":
        items = sorted(items, key=lambda x: x.get('trackPrice', x.get('collectionPrice', 0)))
    elif sortType == "Price (Desc)":
        # Sort high to low
        items = sorted(items, key=lambda x: x.get('trackPrice', x.get('collectionPrice', 0)), reverse=True)
    elif sortType == "Best Selling":
        sales_query = db.session.query(Order_Items.product_name,
                                       func.sum(Order_Items.quantity).label('total_sold')).group_by(
            Order_Items.product_name).all()

        sales_map = {name: total for name, total in sales_query}
        items = sorted(items,
                       key=lambda x: sales_map.get(x.get('trackName', x.get('collectionName')), 0),
                       reverse=True)

    return render_template("sponsor/sponsor_catalog_editor.html", items=items)


@sponsor_bp.route('/add-to-catalog', methods=['POST'])
def add_to_catalog():
    profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    org_id = profile.company_id
    data = request.get_json()
    items = data.get('items', [])

    if not items:
        return jsonify({"message": "No items provided"}), 400

    try:
        for item in items:
            unique_id = item.get('trackId') or item.get('collectionId')

            existing_entry = SponsorCatalog.query.filter(
                SponsorCatalog.company_id == org_id,
                (SponsorCatalog.item_info['trackId'].as_string() == unique_id) |
                (SponsorCatalog.item_info['collectionId'].as_string() == unique_id)
            ).first()

            if existing_entry:
                if not existing_entry.is_active:
                    existing_entry.is_active = True
                continue


            new_catalog_item = SponsorCatalog(
                company_id=org_id,
                item_info=item,
                is_active=True
            )
            db.session.add(new_catalog_item)

        db.session.commit()
        return jsonify({"message": f"Successfully updated catalog with {len(items)} items."}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error adding to catalog: {str(e)}")
        return jsonify({"message": "Internal server error occurred."}), 500

@sponsor_bp.route('/current_catalog', methods=['GET'])
def current_catalog():
    items = SponsorCatalog.query.filter_by(is_active=True, company_id = current_user.sponsor_profile.company_id).all()

    return render_template("sponsor/sponsor_catalog.html", items=items)

@sponsor_bp.route('/remove_from_catalog,<int:target>', methods=['GET', 'POST'])
def remove_from_catalog(target):
    item = SponsorCatalog.query.get(target)
    item.is_active = False
    db.session.commit()
    return redirect(url_for('sponsor.current_catalog'))

@sponsor_bp.route('/sponsor_driver_cat/<int:id_driver>', methods=['GET'])
def sponsor_driver_catalog(id_driver):
    driver_link = DriverCompanyLink.query.filter_by(driver_id=id_driver, is_active=True).first()
    catalog_entries = SponsorCatalog.query.filter_by(company_id=driver_link.company_id, is_active=True).all()

    items_to_display = [entry.item_info for entry in catalog_entries]

    return render_template("sponsor/sponsor_driver_catalog.html", profile=driver_link, points=driver_link.current_points,
                           items=items_to_display)


@sponsor_bp.route('/sponsor_driver_cat/sort/<int:id_driver>', methods=['GET', 'POST'])
def sponsor_driver_catalog_sort(id_driver):
    sort_type = request.form.get("sort_type")
    driver_link = DriverCompanyLink.query.filter_by(driver_id=id_driver, is_active=True).first()
    if not driver_link:
        return redirect(url_for('dashboard'))

    catalog_entries = SponsorCatalog.query.filter_by(company_id=driver_link.company_id, is_active=True).all()
    items = [entry.item_info for entry in catalog_entries]

    if sort_type == "Price (Asc)":
        items.sort(key=lambda x: x.get('trackPrice') or x.get('collectionPrice') or 0)

    elif sort_type == "Price (Desc)":
        items.sort(key=lambda x: x.get('trackPrice') or x.get('collectionPrice') or 0, reverse=True)

    elif sort_type == "Best Selling":
        sales_query = db.session.query(
            Order_Items.product_name,
            func.sum(Order_Items.quantity).label('total_sold')
        ).group_by(Order_Items.product_name).all()

        sales_map = {name: total for name, total in sales_query}
        items.sort(
            key=lambda x: sales_map.get(x.get('trackName') or x.get('collectionName'), 0),
            reverse=True
        )
    return render_template("sponsor/sponsor_driver_catalog.html", profile=driver_link, items=items,
                           points=driver_link.current_points)

@sponsor_bp.route('/place_order/<int:id_driver>', methods=['POST'])
def place_order(id_driver):
    data = request.get_json()
    driver_link = DriverCompanyLink.query.filter_by(
        driver_id=id_driver,
        is_active=True
    ).first()
    if driver_link.current_points < data['total_points']:
        return jsonify({"status": "error", "message": "Insufficient points balance."})

    new_order = Order(
        user_id=id_driver,
        org_id=driver_link.company_id,
        dollar_price=data['total_dollars'],
        point_price=data['total_points'],
        date=datetime.now()
    )
    db.session.add(new_order)
    db.session.flush()

    for item in data['items']:
        new_item = Order_Items(
            order_id=new_order.order_id,
            product_name=item['name'],
            quantity=item['qty'],
            unit_price_dollars=item['price_usd'],
            unit_price_points=item['price_pts']
        )
        db.session.add(new_item)

    points_spent = data['total_points']


    history_entry = DriverPointsHistory(
        link_id=driver_link.id,
        points_change=-points_spent,
        current_points=driver_link.current_points,
        reason=f"Order #{new_order.order_id} placed",
        update_date=datetime.now(),
        sponsor_user_id=None
    )
    db.session.add(history_entry)

    db.session.commit()
    return jsonify({"status": "success", "order_id": new_order.order_id})


@sponsor_bp.route("/audit_log", methods=["GET"])
def sponsor_audit_log():
    sponsor = g.profile
    company_id = sponsor.company_id

    # Driver user_ids linked to this company
    linked_driver_ids = db.session.query(DriverCompanyLink.driver_id).filter_by(
        company_id=company_id
    ).join(Users, Users.id == DriverCompanyLink.driver_id).filter(
        Users.role == "driver"
    ).all()
    linked_driver_ids = [r[0] for r in linked_driver_ids]

    # Sponsor user_ids for this company
    linked_sponsor_ids = db.session.query(SponsorProfile.user_id).filter_by(
        company_id=company_id
    ).all()
    linked_sponsor_ids = [r[0] for r in linked_sponsor_ids]

    # Combine both lists
    all_linked_ids = linked_driver_ids + linked_sponsor_ids

    # Filter parameters
    event_type = request.args.get("event_type", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    page = request.args.get("page", 1, type=int)

    query = AuditLog.query.filter(AuditLog.user_id.in_(all_linked_ids))

    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if date_from:
        query = query.filter(AuditLog.timestamp >= datetime.strptime(date_from, "%Y-%m-%d"))
    if date_to:
        query = query.filter(AuditLog.timestamp <= datetime.strptime(date_to, "%Y-%m-%d"))

    query = query.order_by(AuditLog.timestamp.desc())
    pagination = query.paginate(page=page, per_page=25, error_out=False)
    logs = pagination.items

    event_types = db.session.query(AuditLog.event_type.distinct()).filter(
        AuditLog.user_id.in_(all_linked_ids)
    ).all()
    event_types = [et[0] for et in event_types]

    return render_template(
        "sponsor/sponsor_audit_log.html",
        logs=logs,
        pagination=pagination,
        event_types=event_types,
        current_filter=event_type,
        date_from=date_from,
        date_to=date_to
    )