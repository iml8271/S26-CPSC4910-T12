from flask import Flask, render_template, request, redirect, url_for, session,abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from functools import wraps
from datetime import datetime


# Initialize Flask app
app = Flask(__name__)
app.secret_key = "giggle-gang"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///usersdb.db"
app.config["SECRET_KEY"] = "giggle-gang"

# Initialize database and login manager
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User model
class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250),nullable=False)
    role = db.Column(db.String(250),nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime, nullable=False)

class Address(db.Model):
    email = db.Column(db.String(250), unique=True, nullable=False)
    fname = db.Column(db.String(250), nullable=False)
    lname = db.Column(db.String(250), nullable=False)
    house_no = db.Column(db.String(250), nullable=False)
    street = db.Column(db.String(250), nullable=False)
    city = db.Column(db.String(250), nullable=False)
    state = db.Column(db.String(250), nullable=False)
    zipcode = db.Column(db.String(250), nullable=False)
    country = db.Column(db.String(250), nullable=False)
    nickname = db.Column(db.String(250), nullable=False)



# Create database
with app.app_context():
    db.create_all()    

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

# Register Route:
# registering new users into the system, currently works for only creating new drivers
# as admins and sponsors will be added later or manually
@app.route('/signup', methods=["GET","POST"])
def handle_signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")

        if Users.query.filter_by(username=username).first():
            return render_template("signup.html",error="Username already taken!")
        
        hashed_password = generate_password_hash(password,method="pbkdf2:sha256")
        created_at = datetime.now()
        new_user = Users(username=username, password=hashed_password,role=role, creation_date = created_at)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("handle_login"))
    return render_template("signup.html")

# Login route
@app.route("/login", methods=["GET","POST"])
def handle_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = Users.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == "admin":
                return redirect(url_for("dashboard"))
            elif user.role == "sponsor":
                return redirect(url_for("dashboard"))
            else:
                return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html") 

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
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

# Home Route
@app.route("/")
def view_form():
    return render_template("login.html")

# Error Route
@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403

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



