from flask import Flask, Blueprint,render_template, request, redirect, url_for, session,abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from models import db,Users,DriverProfile
from datetime import datetime

auth_bp = Blueprint("auth",__name__)

# Login route
@auth_bp.route("/login", methods=["GET","POST"])
def handle_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = Users.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            dashboards = {
                "admin": "admin_dashboard",
                "sponsor": "sponsor_dashboard",
                "driver": "driver_dashboard"
            }
            return redirect(url_for(dashboards.get(user.role, "driver_dashboard")))
        else:
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html") 

# Signup Route:
# registering new users into the system, currently works for only creating new drivers
# as admins and sponsors will be added later or manually
@auth_bp.route('/signup', methods=["GET","POST"])
def handle_signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")
        role = request.form.get("role")

        # Checks if username already exists
        if Users.query.filter_by(username=username).first():
            return render_template("signup.html",error="Username already taken!")
        
        # Checks if password meets minimum requirements:
        # minimum 8 characters,no whitespaces,
        # 1 Uppercase, 1 lowercase, 1 number
        if not password:
            return render_template("signup.html", error="Password required")

        if not get_password_strength(password):
            return render_template("signup.html", error="Password does not meet minimums")
        
        #Email Checker
        #tba
        
        hashed_password = generate_password_hash(password,method="pbkdf2:sha256")
        created_at = datetime.now()
        new_user = Users(username=username, password=hashed_password,email=email,role=role,creation_date = created_at)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("auth.handle_login"))
    return render_template("signup.html")

# Signup Driver
@auth_bp.route('/signup_driver', methods=["GET","POST"])
def handle_driver_signup():
    if request.method == "POST":
        firstname = request.form.get("firstname")
        lastname = request.form.get("lastname")
        streetname = request.form.get("streetname")
        city = request.form.get("city")
        zipcode = request.form.get("zipcode")
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")
        role = "driver"
        sponsor = request.form.get("sponsor")

        #First Name Checker
        #tba

        #Last Name Checker
        #tba

        #Address Checker
        #tba

        # Checks if username already exists
        if Users.query.filter_by(username=username).first():
            return render_template("driver_signup.html",error="Username already taken!")
        
        # Checks if password meets minimum requirements:
        # minimum 8 characters,no whitespaces,
        # 1 Uppercase, 1 lowercase, 1 number
        if not password:
            return render_template("signup.html", error="Password required")

        if not get_password_strength(password):
            return render_template("signup.html", error="Password does not meet minimums")
        
        hashed_password = generate_password_hash(password,method="pbkdf2:sha256")
        
        #Email Checker
        #tba

        #Sponsor Link
        
        #Creation Time
        created_at = datetime.now()


        new_user = Users(username=username, password=hashed_password,email=email,role=role,creation_date = created_at)
        db.session.add(new_user)
        db.session.flush()
        new_driver = DriverProfile(user_id=new_user.id,firstname=firstname,lastname=lastname,streetname=streetname,city=city,zipcode=zipcode,sponsor=sponsor)
        db.session.add(new_driver)
        db.session.commit()
        return redirect(url_for("auth.handle_login"))
    return render_template("driver_signup.html")



# Forgot Password
@auth_bp.route("/forgot_password", methods=["GET","POST"])
def handle_forgot_password():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = Users.query.filter_by(username=username).first()
        if not user:
            return render_template("signup.html",error="Username not found!")

        # Checks if password meets minimum requirements:
        # minimum 8 characters,no whitespaces,
        # 1 Uppercase, 1 lowercase, 1 number
        if not password:
            return render_template("forgotpassword.html", error="Password required")

        if not get_password_strength(password):
            return render_template("forgotpassword.html", error="Password does not meet minimums")
        
        if user:
            user.password = generate_password_hash(password,method="pbkdf2:sha256")
            db.session.commit()

        return redirect(url_for("auth.handle_login"))
    return render_template("forgotpassword.html")

# Password Strength Calculator
def get_password_strength(password):
    if len(password) < 8:
        return False
    if any(char.isspace() for char in password):
        return False
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)

    return has_upper and has_lower and has_digit
    

# Logout Route
@auth_bp.route("/logout")
@login_required
def handle_logout():
    logout_user()
    return redirect(url_for("auth.handle_login")) 