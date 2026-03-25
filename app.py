from statistics import median

from flask import Flask, render_template, request, redirect, url_for, session,abort,flash,g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
import requests
from functools import wraps
from authentication import auth_bp
from support import supp_bp
from reports import report_bp
from routes.sponsor import sponsor_bp
from routes.driver import driver_bp
from routes.admin import admin_bp
from models import db, Users, DriverProfile, SponsorProfile, DriverPointsHistory, SponsorCompany, SupportRequest, \
    SponsorCompanyRules, DriverCompanyLink
from datetime import datetime
from flask_migrate import Migrate
import os


# Initialize Flask app
app = Flask(__name__)
app.secret_key = "giggle-gang"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///pointfleetdb.db"
app.config["SECRET_KEY"] = "giggle-gang"

#Bind db
db.init_app(app)
migrate = Migrate(app,db)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.handle_login"
# Register auth blueprint
app.register_blueprint(auth_bp)
app.register_blueprint(supp_bp)
app.register_blueprint(report_bp)
app.register_blueprint(sponsor_bp)
app.register_blueprint(driver_bp)
app.register_blueprint(admin_bp)
# Create database
with app.app_context():
    db.create_all()    

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Users, int(user_id))

# Load User
@app.before_request
def load_user_context():
    print(f"DEBUG: Current Endpoint is: {request.endpoint}")
    g.profile = None
    # Guest Access pages - No profile needed
    public_endpoints = [
        "static",
        "homepage",
        "terms",
        "about",
        "auth.handle_signup",
        "auth.handle_login",
        "auth.handle_driver_signup",
        "auth.handle_sponsor_signup",
        "auth.handle_forgot_password"
    ]

    if request.endpoint in public_endpoints:
        return None
    
    # If user is logged in, attach to the profile
    if current_user.is_authenticated:
        if current_user.role == "driver":
            g.profile = current_user.driver_profile
        elif current_user.role == "sponsor":
            g.profile = current_user.sponsor_profile
        elif current_user.role == "admin":
            g.profile = current_user.admin_profile

        if g.profile is None and current_user.role != "admin":
            flash("Profile not found. Please log in again.", "danger")
            return redirect(url_for("auth.logout"))

#------------ Universal Routes--------------
# Home Route
@app.route("/")
def homepage():
    if app.debug:
        return redirect(url_for("debugmenu"))
    return render_template("homepage.html")

# Error Route
@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403

# Terms
@app.route("/terms")
def terms():
    return render_template("terms.html")

# About
@app.route("/about")
def about():
    return render_template("about.html")

# Protected dashboard Route
@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "driver":
        active_links = [link for link in g.profile.company_links if link.is_active]
        return render_template(
            "driver/driver_dashboard.html", username=current_user.username,links=active_links,profile=g.profile)
    elif current_user.role == "sponsor":
        return render_template("sponsor/sponsor_dashboard.html", username=current_user.username,firstname=g.profile.firstname)
    elif current_user.role == "admin":
        return render_template("admin/admin_dashboard.html", username=current_user.username)
    else:
        return redirect(url_for('auth.handle_logout'))

# DEBUG TASKS --------------------
@app.route("/debug")
def debugmenu():
    return render_template("debugmenu.html")

@app.route("/debug/login-driver")
def debug_driver_login():
    debug_user = Users.query.filter_by(role="driver").first()
    
    if debug_user:
        login_user(debug_user)
        flash(f"Debug Mode: Logged in as {debug_user.username}", "info")
        return redirect(url_for("dashboard"))
    
    flash("No driver found in database to log in!", "danger")
    return redirect(url_for('debugmenu'))
@app.route("/debug/login-sponsor")
def debug_sponsor_login():
    debug_user = Users.query.filter_by(role="sponsor").first()
    
    if debug_user:
        login_user(debug_user)
        flash(f"Debug Mode: Logged in as {debug_user.username}", "info")
        return redirect(url_for("dashboard"))
    
    flash("No driver found in database to log in!", "danger")
    return redirect(url_for('debugmenu'))
@app.route("/debug/login-admin")
def debug_admin_login():
    debug_user = Users.query.filter_by(role="admin").first()
    
    if debug_user:
        login_user(debug_user)
        flash(f"Debug Mode: Logged in as {debug_user.username}", "info")
        return redirect(url_for("dashboard"))
    
    flash("No driver found in database to log in!", "danger")
    return redirect(url_for('debugmenu'))


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
# ----- Admin Soeficifc --------------------
@app.route("/admin/sponsor_list", methods=["GET","POST"])
@role_required("admin")
def admin_sponsor_list():
    sponsors = SponsorProfile.query.all()
    return render_template("admin/admin_sponsor_list.html",sponsors=sponsors)


@app.route("/sponsor/organization/rules", methods=["GET"])
def view_org_rules():
    profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    sourceORG = profile.company_id
    good_request = SponsorCompanyRules.query.filter_by(company_id = sourceORG, nature = "good").all()
    bad_request =  SponsorCompanyRules.query.filter_by(company_id = sourceORG, nature = "bad").all()
    return render_template("/sponsor/sponsor_view_rules.html", request1 = good_request, request2 = bad_request)

@app.route("/sponsor/organization/rules", methods=["POST"])
def delete_rule():
    #get the right rule
    id = request.form.get("rr_target")
    rule = SponsorCompanyRules.query.get(id)
    #delete the rule
    db.session.delete(rule)
    db.session.commit()
    return redirect(url_for("view_org_rules"))


@app.route("/sponsor/organization/rules/new_rule")
def new_rule():
    return render_template("/sponsor/sponsor_add_rule.html")

@app.route("/sponsor/organization/rules/submit", methods=["POST"])
def submit_rule():
    profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    sourceORG = profile.company_id
    rType = request.form.get("rule_type")
    details = request.form.get("details")

    new_rule = SponsorCompanyRules(company_id=sourceORG, nature=rType, rule=details)

    db.session.add(new_rule)
    db.session.commit()
    return redirect(url_for("view_org_rules"))

# Hardcoded catalog
catalog_items = [
    {"name": "Jar Of Dirt", "description": "A mysterious jar of dirt", "price": 1},
    {"name": "CB Radio", "description": "Stay connected on the road", "price": 1500},
    {"name": "$50 Taco Bell Gift Card", "description": "Redeemable at any location", "price": 3000},
]
catalog_price_range = {"min": 0, "max": 10000}
@app.route("/sponsor/sponsor_catalog_editor")
@role_required("sponsor")
def sponsor_catalog_editor():
    return render_template("sponsor/sponsor_catalog_editor.html", items=catalog_items)
@app.route('/sponsor/sponsor_catalog/set-price-range', methods=['POST'])
def sponsor_catalog_set_price_range():
    min_price = int(request.form.get("min_price", 0))
    max_price = int(request.form.get("max_price", 10000))

    if min_price > max_price:
        flash('error min price greater than max')
        return redirect(url_for('sponsor_catalog'))

    catalog_price_range["min"] = min_price
    catalog_price_range["max"] = max_price

    flash(f'Point range: {min_price} - {max_price} pts')
    return redirect(url_for('sponsor_catalog_editor'))

@app.route("/sponsor/sponsor_catalog_editor/add", methods=["POST"])
@role_required("sponsor")
def sponsor_catalog_add():
    price = int(request.form.get("price"))
    if price < catalog_price_range["min"] or price > catalog_price_range["max"]:
        flash(f"Price must be between {catalog_price_range['min']} and {catalog_price_range['max']} pts.")
        return redirect(url_for("sponsor_catalog_editor"))

    catalog_items.append({
        "name": request.form.get("name"),
        "description": request.form.get("description"),
        "price": int(request.form.get("price"))
    })
    flash("item added successfully")
    return redirect(url_for("sponsor_catalog_editor"))

@app.route("/sponsor/sponsor_catalog_editor/edit/<int:item_index>", methods=["POST"])
@role_required("sponsor")
def sponsor_catalog_edit(item_index):
    price = int(request.form.get("price"))
    if price < catalog_price_range["min"] or price > catalog_price_range["max"]:
        flash(f"Price must be between {catalog_price_range['min']} and {catalog_price_range['max']} pts.")
        return redirect(url_for("sponsor_catalog_editor"))

    if 0 <= item_index < len(catalog_items):
        catalog_items[item_index] = {
            "name": request.form.get("name"),
            "description": request.form.get("description"),
            "price": int(request.form.get("price"))
        }
        flash("Item price changed sucessfuly")
    return redirect(url_for("sponsor_catalog_editor"))

@app.route("/sponsor/sponsor_catalog_editor/delete/<int:item_index>", methods=["POST"])
@role_required("sponsor")
def sponsor_catalog_delete(item_index):
    if 0 <= item_index < len(catalog_items):
        catalog_items.pop(item_index)
        flash("Item deleted successfully yay!")
    return redirect(url_for("sponsor_catalog_editor"))

@app.route("/sponsor/reports/points",methods=["GET"])
@login_required
def points_report():
    profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    target_id = profile.company_id
    request = db.session.query(DriverPointsHistory).join(SponsorProfile).filter(SponsorProfile.company_id == target_id).all()
    return render_template("admin/reports/admin_points_report.html", history = request)

# ------- Driver Speficics ------------------

@app.route("/driver/organization/rules", methods=["GET"])
def driver_view_org_rules():
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    sourceORG = profile.company_id
    good_request = SponsorCompanyRules.query.filter_by(company_id = sourceORG, nature = "good").all()
    bad_request =  SponsorCompanyRules.query.filter_by(company_id = sourceORG, nature = "bad").all()
    return render_template("/driver/driver_view_rules.html", request1 = good_request, request2 = bad_request)

# ------------ Protected dashboard Route --------------
@app.route("/admin/dashboard")
@role_required("admin")
def view_admin_dashboard():
    return render_template("admin/admin_dashboard.html", username=current_user.username)

@app.route("/sponsor/dashboard")
@role_required("sponsor")
def view_sponsor_dashboard():
    sponsor_profile = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    return render_template("sponsor/sponsor_dashboard.html", username=current_user.username,firstname=sponsor_profile.firstname)

@app.route("/driver/dashboard")
@role_required("driver")
def view_driver_dashboard():
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    points = profile.points if profile else 0
    return render_template("driver/driver_dashboard.html", username=current_user.username,points=points,profile=profile)


@app.route("/driver/dashboard/driver_catalog", methods=["GET"])
@login_required
def driver_catalog():
    #we can remove these after we make a catalog for sponors
    driver = DriverCompanyLink.query.filter_by(driver_id=current_user.id, is_active = True).first()
    company = SponsorCompany.query.filter_by(company_id=driver.company_id).first()
    priceMax = company.priceMax
    explicit = company.explicit
    explicitVal = "No"
    itunes_url = "https://itunes.apple.com/search"
    if explicit:
        explicitVal = "Yes"


    params = {
        "term": "Michael+Jackson",
        "media": "all",
        "limit": 50,
        "explicit": explicitVal
    }

    results = requests.get(itunes_url, params=params)
    data = results.json()

    return render_template("driver/driver_catalog.html", items=data['results'])

@app.route("/driver/dashboard/driver_catalog/search", methods=["GET", "POST"])
@login_required
def driver_catalog_search():
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


    return render_template("driver/driver_catalog.html", items=items)

@app.route("/driver/dashboard/driver_order_history")
@login_required
def driver_order_history():
    #we can remove these after we update database
    items = [
        {"name": "Jar Of Dirt", "price": 1, "date": "02/09/26"},
        {"name": "CV Radio", "price": 1500, "date": "06/21/87"},
        {"name": "$50 Taco Bell Gift Card", "price": 3000, "date": "09/01/20"},
    ]
    return render_template("driver/driver_order_history.html", items=items)

@app.route("/driver/dashboard/driver_points_review")
@login_required
def driver_points_review():
    #filler for now, will use db when added.
    points_log = [
        {"date": "2024-01-15", "points": 100, "description": "Max Points, No Infractions"},
        {"date": "2024-01-20", "points": 50, "description": "50 Points Deducted for Speeding"},
        {"date": "2024-02-05", "points": 100, "description": "Max Points, No Infractions"},
    ]
    return render_template("driver/driver_points_review.html",points_log=points_log)



@app.route("/driver_profile")
@login_required
def profile():
    # current_user already holds the data from the DB
    return render_template("driver/driver_profile.html", user=current_user)


@app.route("/update-email", methods=["POST"])
@login_required
def update_email():
    new_email = request.form.get("email")

    if not new_email:
        return redirect(url_for("dashboard", error="Email cannot be empty"))

    current_user.email = new_email
    db.session.commit()

    return redirect(url_for("dashboard", message="Email updated successfully!"))

@app.route("/add-shipping-info", methods=["POST"])
@login_required
def add_shipping_info():
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    house_num = request.form.get("house_num")
    street_name = request.form.get("street_name")
    city_name = request.form.get("city_name")
    state = request.form.get("state")
    zip_code = request.form.get("zip_code")
    country = request.form.get("country")
    nickname = request.form.get("nickname")
    email = current_user.email

    new_address = Address(fname = first_name, lname = last_name, house_no = house_num, street = street_name,
                          city = city_name, state = state, zipcode = zip_code, country = country, nickname = nickname,
                          email = email)
    db.session.add(new_address)


@app.route("/company/view/<int:company_id>")
@login_required
def view_company_profile(company_id):
    # Fetch the company or return a 404 if it doesn't exist
    company = SponsorCompany.query.get_or_404(company_id)
    
    return render_template("company/company_viewcard.html", company=company)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)