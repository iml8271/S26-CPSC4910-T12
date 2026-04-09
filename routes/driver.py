from flask import Flask, Blueprint,render_template, request, redirect, url_for, session,abort,flash, current_app,g, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from models import db, Users, DriverProfile, SponsorCompany, SponsorProfile, DriverPointsHistory, DriverApplications, \
    Driver_Org_RelationShip,SponsorCompanyRules
from datetime import datetime
from functools import wraps
import csv
import io
from helpers import *
import os
from models import Order, Order_Items
from sqlalchemy import func
import requests

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

@driver_bp.route("/company_application", methods=["GET","POST"])
def company_application():
    compID = request.form.get("company_id")
    companytarget = SponsorCompany.query.filter_by(id=compID).first()
    application = DriverApplications(
        user_id=current_user.id,
        company_id=companytarget.id,  # Use the ID (Integer)
        company=companytarget.name,
        status='pending',
        reason=''
    )
    db.session.add(application)
    db.session.commit()


@driver_bp.route("/my-sponsor", methods=["GET"])
def mysponsor():
    member = Driver_Org_RelationShip.query.filter_by(user_id=current_user.id).all()
    request = SponsorCompany.query.all()
    return render_template("driver/driver_mysponsor.html",profile=g.profile,company=g.profile.company.name, companies = request, member = member)
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

# ORGANIZATION RULES ------------------------------------
@driver_bp.route("/organization/rules", methods=["GET"])
def driver_view_org_rules():
    profile = DriverProfile.query.filter_by(user_id=current_user.id).first()
    sourceORG = profile.company_id
    good_request = SponsorCompanyRules.query.filter_by(company_id = sourceORG, nature = "good").all()
    bad_request =  SponsorCompanyRules.query.filter_by(company_id = sourceORG, nature = "bad").all()
    return render_template("/driver/driver_view_rules.html", request1 = good_request, request2 = bad_request)

# CATALOG ------------------------------------------------
@driver_bp.route("/dashboard/driver_catalog", methods=["GET"])
def driver_catalog():
    #we can remove these after we make a catalog for sponors
    driver = DriverCompanyLink.query.filter_by(driver_id=current_user.id, is_active = True).first()
    company = SponsorCompany.query.filter_by(id=driver.company_id).first()
    priceMax = company.priceMax
    explicit = company.explicit
    explicitVal = "No"
    driver_points = driver.current_points
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

    return render_template("driver/driver_catalog.html",profile=g.profile, items=data['results'], points = driver_points)

@driver_bp.route("/driver_catalog/search", methods=["GET", "POST"])
def driver_catalog_search():
    driver = DriverCompanyLink.query.filter_by(driver_id=current_user.id, is_active=True).first()
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
    driver_points = driver.current_points
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

    return render_template("driver/driver_catalog.html",profile=g.profile, items=items, points = driver_points)

@driver_bp.route("/driver_order_history")
def driver_order_history():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.date.desc()).all()


    return render_template("driver/driver_order_history.html", orders=orders, profile=g.profile)

@driver_bp.route("/driver_points_review")
def driver_points_review():
    try:
        driver_profile = g.profile
        link_ids = [link.id for link in driver_profile.company_links]

        pts_history = DriverPointsHistory.query.filter(DriverPointsHistory.link_id.in_(link_ids)
        ).order_by(DriverPointsHistory.update_date.desc()).all()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to find points: {str(e)}") from e
    return render_template("driver/driver_points_review.html",pts_history=pts_history)


@driver_bp.route('/place_order', methods=['POST'])
def place_order():
    data = request.get_json()
    driver_link = DriverCompanyLink.query.filter_by(
        driver_id=current_user.id,
        is_active=True
    ).first()
    if driver_link.current_points < data['total_points']:
        return jsonify({"status": "error", "message": "Insufficient points balance."})


    new_order = Order(
        user_id=current_user.id,
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

    driver_link.current_points -= data['total_points']

    db.session.commit()
    return jsonify({"status": "success", "order_id": new_order.order_id})