from flask import Flask, Blueprint,render_template, request, redirect, url_for, session,abort,flash, current_app,g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from models import db,Users,DriverProfile,SponsorCompany,SponsorProfile,DriverPointsHistory, DriverApplications
from datetime import datetime
from functools import wraps
import csv
import io
from helpers import role_required,driver_create,driver_update_points,sponsor_create
import os

driver_bp = Blueprint("driver",__name__,url_prefix="/driver")

@driver_bp.before_request
def restrict_to_driver():
    # User has to be logged in
    if not current_user.is_authenticated:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('auth.handle_login'))

    # User has to be a driver
    if current_user.role != "driver" and current_user.role != "admin":
        flash("Access denied: Drivers only.", "danger")
        return redirect(url_for('auth.handle_login'))
    if current_user.role == "admin":
        return None
    
    # User has to have a profile
    if not g.profile:
        flash("Driver profile not found. Please contact an admin.", "danger")
        return redirect(url_for('auth.logout'))

@driver_bp.route("/settings", methods=["GET","POST"])
def driver_settings():
    driver = g.profile
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
            return redirect(url_for("driver.driver_settings"))

        # Only update changed fields
        driver.streetname = streetname
        driver.city = city
        driver.zipcode = zipcode

        db.session.commit()
        flash("Address updated successfully.")
        return redirect(url_for("driver.driver_settings"), driver=driver,username=current_user.username)
    return render_template("driver/driver_settings.html", driver=driver,username=current_user.username)


@driver_bp.route("/driver_faq")
def faq():
    return render_template("driver/driver_faq.html")


@driver_bp.route("/my_sponsors", methods=["GET"])
def mysponsors():
     active_links = [link for link in g.profile.company_links if link.is_active]
     return render_template("driver/driver_mysponsors.html",profile=g.profile,links=active_links)

@driver_bp.route("/my_sponsors/status", methods=["GET"])
def mysponsors_status():
    all_companies = SponsorCompany.query.all()
    active_links = {link.company_id: link for link in g.profile.company_links if link.is_active}
    
    # Map of Company ID -> Status (for non-active links)
    apps = DriverApplications.query.filter_by(user_id=g.profile.user_id).all()
    app_statuses = {app.company_id: app.status for app in apps}

    return render_template(
        "driver/driver_mysponsors_status.html",
        companies=all_companies,
        active_links=active_links,
        app_statuses=app_statuses
    )

@driver_bp.route("/my_sponsors/apply/<int:company_id>", methods=["POST"])
def mysponsors_apply(company_id):
    existing = DriverApplications.query.filter_by(
        user_id=g.profile.user_id, 
        company_id=company_id
    ).first()

    if not existing:
        new_app = DriverApplications(
            user_id=g.profile.user_id,
            company_id=company_id,
            status="pending"
        )
        db.session.add(new_app)
        db.session.commit()
        flash("Application submitted successfully!")
    else:
        flash("You already have an application for this company.")

    return redirect(url_for('driver.mysponsors_status'))