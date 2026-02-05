from flask import Flask, render_template, request, redirect, url_for, session,abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from functools import wraps
from authentication import auth_bp
from models import db,Users


# Initialize Flask app
app = Flask(__name__)
app.secret_key = "giggle-gang"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///usersdb.db"
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
    return Users.query.get(int(user_id))


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

# Protected dashboard Route
@app.route("/dashboard/admin")
@role_required("admin")
def admin_dashboard():
    return render_template("admin_dashboard.html", username=current_user.username)

@app.route("/dashboard/sponsor")
@role_required("sponsor")
def sponsor_dashboard():
    return render_template("sponsor_dashboard.html", username=current_user.username)

@app.route("/dashboard/driver")
@role_required("driver")
def driver_dashboard():
    return render_template("driver_dashboard.html", username=current_user.username)

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

