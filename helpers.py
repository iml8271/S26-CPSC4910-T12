from __future__ import annotations

from models import db,Users,DriverProfile,DriverApplications,DriverPointsHistory,SponsorProfile
from werkzeug.security import generate_password_hash
from sqlalchemy.orm.exc import DetachedInstanceError
from functools import wraps
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask import Flask, Blueprint,render_template, request, redirect, url_for, session,abort,flash, current_app
from datetime import datetime

# Universal ---------
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

def generate_unique_username(email):
    base = email.split('@')[0]
    username = base
    counter = 1
    while Users.query.filter_by(username=username).first():
        username = f"{base}{counter}"
        counter += 1
    return username

def validate_model(obj, model_name="Object"):
    if obj is None:
        raise ValueError(f"{model_name} not found.")
    if obj not in db.session:
        db.session.add(obj)
    return obj

# DRIVER ------------------
def driver_create(
    email: str,
    firstname: str,
    lastname: str,
    streetname: str = "",
    city: str = "",
    zipcode: str = "",
    username: str | None = None,
    password: str | None = None,
    points_to_add: int = 0,
    points_reason: str = "New Driver Registration",
    status: str = "pending",
    application_reason: str = "New Driver Registration",
    sponsor_user_id: int | None = None,
    company_id: set[int] = None
) -> Users:
    """
    Creates a driver user, profile, and application record.
    """
    # Check Email uniqueness : email is unique identifier
    if Users.query.filter_by(email=email).first():
        raise ValueError(f"Email {email} is already registered to a user")
    
    # Username handling
    username = username or generate_unique_username(email)
    if username and Users.query.filter_by(username=username).first():
        raise ValueError(f"Username {username} is already taken")

    # Password handling
    # temp password until user creates new password
    password = password or "Password1"
    hashed_password = generate_password_hash(password,method="pbkdf2:sha256") if password else None

    # Check activeness
    is_active = (status.lower() == "accepted")

    try:
        # Create core user
        new_user = Users(
            username=username,
            password=hashed_password,
            email=email,
            role="driver"
        )

        # Create driver profile
        new_user.driver_profile = DriverProfile(
            firstname=firstname,
            lastname=lastname,
            streetname=streetname,
            city=city,
            zipcode=zipcode,
            is_active = is_active
        )

        db.session.add(new_user)
        db.session.flush()

        # Create application record
        if company_id:
            for c_id in company_id:
                # Application Record
                application = DriverApplications(
                    driver_profile = new_user.driver_profile,
                    company_id=c_id,
                    status=status,
                    status_reason = application_reason,
                    status_date = datetime.now()
                )
                db.session.add(application)

                if is_active:
                    # Add Relationship 
                    driver_add_link(driver_profile=new_user.driver_profile
                                ,company_id=c_id
                                ,reason=points_reason
                                ,sponsor_user_id=sponsor_user_id
                                ,initial_points=points_to_add)

        db.session.commit()
        return new_user
    
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to create driver: {str(e)}") from e

def driver_add_link(
    driver_profile: DriverProfile,
    company_id: int,
    reason: str = "New Link",
    sponsor_user_id: int | None = None,
    initial_points: int = 0
) -> DriverCompanyLink:
    
    try:
        # Add Linkage
        # Query to check for previous relationship
        link = DriverCompanyLink.query.filter_by(
            driver_id=driver_profile.user_id
            ,company_id=company_id).first()
        if not link:
            link = DriverCompanyLink(
                driver_profile = driver_profile,
                company_id = company_id
            )
        link.is_active = True
        link.status_date = datetime.now()
        db.session.add(link)

        # Add New Points Record
        new_record = DriverPointsHistory(
            link = link,
            points_change = initial_points,
            current_points = initial_points,
            reason = reason,
            sponsor_user_id = sponsor_user_id
        )
        db.session.add(new_record)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to link driver to company: {str(e)}") from e

def driver_remove_link(
    driver_profile: DriverProfile,
    company_id: int,
    sponsor_user_id: int | None = None,
) -> DriverCompanyLink:
    
    try:
        link = DriverCompanyLink.query.filter_by(
            driver_id=driver_profile.user_id
            ,company_id=company_id).first()
        if not link:
            raise ValueError(f"Link is not found")
        if not link.is_active:
            return link
        
        link.is_active = False
        link.status_date = datetime.now()
        db.session.add(link)

        # Add Final Points Record
        closeout_record = DriverPointsHistory(
            link = link,
            points_change = 0,
            current_points = link.current_points,
            reason = "Link Ended",
            sponsor_user_id = sponsor_user_id
        )
        db.session.add(closeout_record)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to remove driver from company: {str(e)}") from e

def driver_update_points(
    driver_profile: DriverProfile,
    company_id: int,
    points_to_add = 0,
    points_reason = "No Reason Given",
    sponsor_user_id: int | None = None,
):
    if points_to_add == 0:
        raise ValueError("No points to add (change is zero)")

    try:
        driver_profile = validate_model(driver_profile)

        company_link = DriverCompanyLink.query.with_for_update().filter_by(
            driver_id=driver_profile.user_id
            ,company_id=company_id).first()
        
        new_total = (company_link.current_points or 0) + points_to_add
        if new_total < 0:
            raise ValueError(f"Insufficient points. Current: {company_link.current_points}, Attempted change: {points_to_add}")

        points_history = DriverPointsHistory(
            link = company_link,
            points_change = points_to_add,
            current_points = new_total,
            reason = points_reason,
            sponsor_user_id = sponsor_user_id
        )
        db.session.add(points_history)
        db.session.commit()

        return driver_profile
    
    except DetachedInstanceError:
        db.session.rollback()
        raise RuntimeError("Database error: Driver profile is detached from session.")
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Database error while updating points: {str(e)}") from e

def driver_update_address(
    driver_profile:DriverProfile,
    streetname: str ,
    city: str,
    zipcode: str,
) -> DriverProfile:    
    if not streetname.strip():
        raise ValueError("Street name cannot be empty")
    if not city.strip():
        raise ValueError("City cannot be empty")
    if not zipcode.strip():
        raise ValueError("Zip code cannot be empty")
    
    try:
        driver_profile = validate_model(driver_profile)

        driver_profile.streetname = streetname.strip()
        driver_profile.city = city.strip()
        driver_profile.zipcode = zipcode.strip()

        db.session.commit()
        db.session.refresh(driver_profile)

        return driver_profile
    except DetachedInstanceError:
        db.session.rollback()
        raise RuntimeError("Database error: Driver profile is detached from session.")
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to update driver address: {str(e)}")

def driver_accept_application(
    driver_profile: DriverProfile,
    company_id: int,
    sponsor_user_id: int | None = None
):
    try:
        application = DriverApplications.query.filter_by(
            user_id=driver_profile.user_id
            ,company_id=company_id
            ,status = "pending").first()
        if not application:
            raise ValueError(f"No application found")
        
        application.status = "accepted"
        application.status_reason = "Application Approved"
        application.status_date = datetime.now()

        driver_add_link(
            driver_profile=driver_profile,
            company_id=company_id,
            reason="Application Approved",
            sponsor_user_id=sponsor_user_id
        )

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to accept driver: {str(e)}") from e
    
def driver_reject_application(
    driver_profile: DriverProfile,
    company_id: int,
    reason: str,
):
    try:
        application = DriverApplications.query.filter_by(
            user_id=driver_profile.user_id
            ,company_id=company_id
            ,status = "pending").first()
        if not application:
            raise ValueError(f"No application found")
        
        application.status = "rejected"
        application.status_reason = reason
        application.status_date = datetime.now()

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to reject driver: {str(e)}") from e


# SPONSOR ------------------------------------
def sponsor_create(
    email: str,
    firstname: str,
    lastname: str,
    company_id: int,
    username: str | None = None,
    password: str | None = None,
) -> Users:
    """
    Creates a sponsor user, profile record.
    """
    # Check uniqueness
    if Users.query.filter_by(email=email).first():
        raise ValueError(f"Email {email} is already registered")

    # Username handling
    username = username or generate_unique_username(email)
    if username and Users.query.filter_by(username=username).first():
        raise ValueError(f"Username {username} is already taken")

    # Password handling
    # temp password until user creates new password
    password= password or "Password1"
    hashed_password = generate_password_hash(password,method="pbkdf2:sha256") if password else None

    try:
        # Create core user
        new_user = Users(
            username=username,
            password=hashed_password,
            email=email,
            role="sponsor"
        )
        # Create sponsor profile
        new_user.sponsor_profile = SponsorProfile(
            firstname=firstname,
            lastname=lastname,
            company_id=company_id
        )
        db.session.add(new_user)
        db.session.commit()
        return new_user
    
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to create sponsor: {str(e)}") from e

# ADMIN ---------
def admin_create(
    email: str,
    username: str | None = None,
    password: str | None = None,
) -> Users:
    """
    Creates an admin user, profile record.
    """
    # Check uniqueness
    if Users.query.filter_by(email=email).first():
        raise ValueError(f"Email {email} is already registered")

    # Username handling
    if username and Users.query.filter_by(username=username).first():
        raise ValueError(f"Username {username} is already taken")

    # Password handling
    hashed_password = generate_password_hash(password,method="pbkdf2:sha256") if password else None

    try:
        # Create core user
        new_user = Users(
            username=username,
            password=hashed_password,
            email=email,
            role="sponsor"
        )
        db.session.add(new_user)

        db.session.commit()
        db.session.refresh(new_user)
        return new_user
    
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to create sponsor: {str(e)}") from e