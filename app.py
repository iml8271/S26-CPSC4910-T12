from statistics import median

from flask import Flask, render_template, request, redirect, url_for, session,abort,flash,g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from functools import wraps
from authentication import auth_bp
from support import supp_bp
from reports import report_bp
from routes.sponsor import sponsor_bp
from routes.driver import driver_bp
from routes.admin import admin_bp
from models import db,Users,SponsorCompany,DriverApplications
from flask_migrate import Migrate
from routes_invoice import invoice_bp
import os




# Initialize Flask app
app = Flask(__name__)
app.secret_key = "giggle-gang"
#app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://team12:Team12Password@cpsc4910-s26.cobd8enwsupz.us-east-1.rds.amazonaws.com:3306/Team12_DB'
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
app.register_blueprint(invoice_bp)
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
        if not active_links:
            pending = DriverApplications.query.filter_by(user_id=current_user.id, status='pending').all()
            return render_template("driver/driver_waitingroom.html", username=current_user.driver_profile.firstname, pending_apps=pending)
        return render_template(
            "driver/driver_dashboard.html", username=current_user.username,links=active_links,profile=g.profile)
    elif current_user.role == "sponsor":
        return render_template("sponsor/sponsor_dashboard.html", username=current_user.username,firstname=g.profile.firstname,profile=g.profile)
    elif current_user.role == "admin":
        return render_template("admin/admin_dashboard.html", profile=g.profile,username=current_user.username)
    else:
        return redirect(url_for('auth.handle_logout'))

# DEBUG TASKS --------------------
@app.route("/debug")
def debugmenu():
    if app.debug :
        return render_template("debugmenu.html")
    return redirect(url_for("homepage"))

@app.route("/debug/login-driver")
def debug_driver_login():
    if app.debug:
        debug_user = Users.query.filter_by(role="driver").first()
        
        if debug_user:
            login_user(debug_user)
            flash(f"Debug Mode: Logged in as {debug_user.username}", "info")
            return redirect(url_for("dashboard"))
        
        flash("No driver found in database to log in!", "danger")
        return redirect(url_for('debugmenu'))
    return redirect(url_for("homepage"))

@app.route("/debug/login-sponsor")
def debug_sponsor_login():
    if app.debug:
        debug_user = Users.query.filter_by(role="sponsor").first()
        
        if debug_user:
            login_user(debug_user)
            flash(f"Debug Mode: Logged in as {debug_user.username}", "info")
            return redirect(url_for("dashboard"))
        
        flash("No driver found in database to log in!", "danger")
        return redirect(url_for('debugmenu'))
    return redirect(url_for("homepage"))

@app.route("/debug/login-admin")
def debug_admin_login():
    if app.debug:
        debug_user = Users.query.filter_by(role="admin").first()
        
        if debug_user:
            login_user(debug_user)
            flash(f"Debug Mode: Logged in as {debug_user.username}", "info")
            return redirect(url_for("dashboard"))
        
        flash("No driver found in database to log in!", "danger")
        return redirect(url_for('debugmenu'))
    return redirect(url_for("homepage"))


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


@app.route("/company/view/<int:company_id>")
@login_required
def view_company_profile(company_id):
    # Fetch the company or return a 404 if it doesn't exist
    company = SponsorCompany.query.get_or_404(company_id)
    
    return render_template("company/company_viewcard.html", company=company)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000,debug=True)