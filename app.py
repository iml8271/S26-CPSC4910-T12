from flask import Flask, render_template, request, redirect, url_for, session,abort,flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from authentication import auth_bp
from support import supp_bp
from reports import report_bp
from models import db,Users,DriverProfile,SponsorProfile,DriverPointsHistory,SponsorCompany, SupportRequest
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
# Create database
with app.app_context():
    db.create_all()    

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Users, int(user_id))

# LOGO UPLOAD
UPLOAD_FOLDER = os.path.join(app.static_folder, "images/uploads/logos")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


# Logout Route
@app.route("/logout")
@login_required
def handle_logout():
    logout_user()
    return render_template("login.html")   

# Protected dashboard Route
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=current_user.username)

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

# ----- Sponsor Speficic--------------------
@app.route("/sponsor/settings",methods=["GET","POST"])
@role_required("sponsor")
def sponsor_settings():
    sponsor = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    if request.method == "POST":
        if "sponsor_logo" not in request.files:
            flash("No file selected.")
            return redirect(url_for("sponsor_settings"))

        file = request.files["sponsor_logo"]

        if file.filename == "":
            flash("No file selected.")
            return redirect(url_for("sponsor_settings"))

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Optional: make filename unique
            unique_filename = f"{sponsor.company_id}_{filename}"

            save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
            file.save(save_path)

            # Store relative path in DB
            sponsor.company.logo_filename = f"images/uploads/logos/{unique_filename}"
            db.session.commit()

            flash("Logo uploaded successfully.")
            return redirect(url_for("sponsor_settings"))
        else:
            flash("Invalid file type. Only PNG and JPG allowed.")
            return redirect(url_for("sponsor_settings"))

    return render_template(
        "sponsor/sponsor_settings.html",
        sponsor=sponsor)

def allowed_file(filename):
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/sponsor/driver_list", methods=["GET","POST"])
@role_required("sponsor")
def sponsor_view_drivers():
    sponsor = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    if not sponsor:
        return redirect(url_for("view_sponsor_dashboard"))
    drivers = DriverProfile.query.filter_by(company_id=sponsor.company_id).all()
    return render_template("sponsor/sponsor_view_drivers.html",drivers=drivers)

@app.route("/sponsor/adjust_points", methods=["POST"])
@role_required("sponsor")
def adjust_points():
    driver_id_raw = request.form.get("driver_id")
    try:
        driver_id = int(driver_id_raw.strip())
    except (TypeError, ValueError):
        flash("Invalid driver ID.")
        return redirect(url_for("sponsor/sponsor_view_drivers"))
    print(f"Updated Driver ID:{driver_id}")
    sponsor = SponsorProfile.query.filter_by(user_id=current_user.id).first()
    if not sponsor:
        flash("Sponsor profile not found.")
        return redirect(url_for("sponsor/sponsor_view_drivers"))

    driver = DriverProfile.query.filter_by(
        user_id=driver_id,
        company_id=sponsor.company_id
    ).first()

    
    if not driver:
        flash("Error: Driver not found.")
        return redirect(url_for("sponsor_view_drivers"))
    points_change = int(request.form.get("points_change"))
    reason = request.form.get("reason")
    
    # Calculate new total points
    new_total = driver.points + points_change
    
    # Save New total points
    new_log = DriverPointsHistory(
        user_id=driver.user_id,
        points_change=points_change,
        current_points=new_total,
        reason=reason,
        sponsor_user_id=sponsor.user_id,
    )
    try:
        db.session.add(new_log)
        print("NEW LOG:", new_log.user_id, new_log.points_change, new_log.current_points)
        db.session.commit()
        db.session.refresh(driver)
        flash(f"Successfully adjusted points for {driver.firstname}!")
    except Exception as e:
        db.session.rollback()
        print(f"DATABASE ERROR: {e}")
        flash("An error occurred while saving to the database.")
    
    return redirect(url_for("sponsor/sponsor_view_drivers"))

# Hardcoded catalog
catalog_items = [
    {"name": "Jar Of Dirt", "description": "A mysterious jar of dirt", "price": 1},
    {"name": "CB Radio", "description": "Stay connected on the road", "price": 1500},
    {"name": "$50 Taco Bell Gift Card", "description": "Redeemable at any location", "price": 3000},
]
@app.route("/sponsor/sponsor_catalog_editor")
@role_required("sponsor")
def sponsor_catalog_editor():
    return render_template("sponsor/sponsor_catalog_editor.html", items=catalog_items)

@app.route("/sponsor/sponsor_catalog_editor/add", methods=["POST"])
@role_required("sponsor")
def sponsor_catalog_add():
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
    if 0 <= item_index < len(catalog_items):
        catalog_items[item_index] = {
            "name": request.form.get("name"),
            "description": request.form.get("description"),
            "price": int(request.form.get("price"))
        }
        flash("Item updated sucessfuly")
    return redirect(url_for("sponsor_catalog_editor"))

@app.route("/sponsor/sponsor_catalog_editor/delete/<int:item_index>", methods=["POST"])
@role_required("sponsor")
def sponsor_catalog_delete(item_index):
    if 0 <= item_index < len(catalog_items):
        catalog_items.pop(item_index)
        flash("Item deleted successfully yay!")
    return redirect(url_for("sponsor_catalog_editor"))

# ------- Driver Speficics ------------------
@app.route("/driver/settings", methods=["GET","POST"])
@role_required("driver")
def driver_settings():
    driver = DriverProfile.query.filter_by(user_id=current_user.id).first()
    if request.method=="POST":
        #Address Checker
        streetname = request.form.get("streetname")
        city = request.form.get("city")
        zipcode = request.form.get("zipcode")
        #tba

        if not streetname or not city or not zipcode:
            flash("All address fields are required.")
            return redirect(url_for("driver_settings"))
        
        if (driver.streetname == streetname and
            driver.city == city and
            driver.zipcode == zipcode):
            
            flash("No changes detected.")
            return redirect(url_for("driver_settings"))

        # Only update changed fields
        driver.streetname = streetname
        driver.city = city
        driver.zipcode = zipcode

        db.session.commit()
        flash("Address updated successfully.")
        return redirect(url_for("driver_settings"))
    return render_template("driver/driver_settings.html", driver=driver,username=current_user.username)

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

#------------ Universal Routes--------------
# Home Route
@app.route("/")
def view_form():
    return redirect(url_for("auth.handle_login"))

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

@app.route("/driver/dashboard/driver_catalog")
@login_required
def driver_catalog():
    #we can remove these after we make a catalog for sponors
    items = [
        {"name": "Jar Of Dirt", "price": 1},
        {"name": "CV Radio", "price": 1500},
        {"name": "$50 Taco Bell Gift Card", "price": 3000},
    ]
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

@app.route("/driver/dashboard/driver_faq")
@login_required
def driver_faq():
    return render_template("driver/driver_faq.html")

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




if __name__ == "__main__":
    app.run(debug=True)