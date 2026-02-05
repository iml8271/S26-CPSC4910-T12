from flask import Flask, render_template, request, redirect, url_for, session,abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from functools import wraps
from authentication import auth_bp
from models import db,Users,DriverProfile
from datetime import datetime


# Initialize Flask app
app = Flask(__name__)
app.secret_key = "giggle-gang"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///pointfleetdb.db"
app.config["SECRET_KEY"] = "giggle-gang"

#Bind db
db.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.handle_login"
# Register auth blueprint
app.register_blueprint(auth_bp)
# Create database
with app.app_context():
    db.create_all()    

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Users, int(user_id))


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

# ----- Sponsor Speficic--------------------
@app.route("/settings/sponsor")

# ------------ Protected dashboard Route --------------
@app.route("/admin/dashboard")
@role_required("admin")
def view_admin_dashboard():
    return render_template("admin_dashboard.html", username=current_user.username)

@app.route("/sponsor/dashboard")
@role_required("sponsor")
def view_sponsor_dashboard():
    return render_template("sponsor_dashboard.html", username=current_user.username)

@app.route("/driver/dashboard")
@role_required("driver")
def view_driver_dashboard():
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    points = profile.points if profile else 0
    return render_template("driver_dashboard.html", username=current_user.username,points=points)

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


if __name__ == "__main__":
    app.run(debug=True)


@app.route("/driver_profile")
@login_required
def profile():
    # current_user already holds the data from the DB
    return render_template("driver_profile.html", user=current_user)


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
    last_name = request.form.get("first_name")
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



