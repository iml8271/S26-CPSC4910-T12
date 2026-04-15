from __future__ import annotations

from models import *
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
#trusts everything has been checked
def driver_create_profile(email,firstname,lastname,username,password)->Users:
    hashed_password = generate_password_hash(password,method="pbkdf2:sha256") if password else None
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
        )

        db.session.add(new_user)
        db.session.flush()
        return new_user
    
    except Exception as e:
        raise RuntimeError(f"Failed to create driver: {str(e)}") from e
def driver_create_application(driver_id,company_id):
    #defaults to "pending"
    try:
        app = DriverApplications(
            user_id=driver_id,
            company_id=company_id,
            status_date=datetime.now()
        )
        db.session.add(app)
        db.session.flush()
    except Exception as e:
        raise RuntimeError(f"Failed to create application: {str(e)}") from e
def driver_status_application(driver_id,company_id,status,status_reason):
    try:
        app = DriverApplications.query.filter_by(user_id=driver_id,company_id=company_id).first()
        app.status = status
        app.status_reason = status_reason
        app.status_date = datetime.now()
        db.session.add(app)
        db.session.flush()
    except Exception as e:
        raise RuntimeError(f"Failed to change application: {str(e)}") from e      
# creates an activates a link between a driver and a company - Initatlies points
def driver_active_link(driver_id,company_id,points=0, reason = "New Relationship"):
    try:
        link = DriverCompanyLink.query.filter_by(
            driver_id=driver_id,
            company_id=company_id).first()
        if not link:
            link = DriverCompanyLink(
                driver_id=driver_id,
                company_id=company_id)
        link.is_active = True
        link.status_date = datetime.now()
        db.session.add(link)
        db.session.flush()

        init_points = DriverPointsHistory(
            link_id = link.id,
            points_change = points,
            current_points = points,
            reason = reason
        )
        db.session.add(init_points)
        db.session.flush()
    except Exception as e:
        raise RuntimeError(f"Failed to create application: {str(e)}") from e
def driver_update_address(driver_id,streetname,city,zipcode):
    try:
        driver_profile = DriverProfile.query.filter_by(user_id=driver_id).first()
        if not driver_profile:
            raise ValueError(f"No profile found for user ID {driver_id}")
        driver_profile.streetname = streetname
        driver_profile.city = city
        driver_profile.zipcode = zipcode
        db.session.add(driver_profile)
        db.session.flush()
    except Exception as e:
        raise RuntimeError(f"Failed to update address: {str(e)}") from e
# requires an active link
def driver_change_points(driver_id,company_id,points,sponsor_id,reason="New Link"):
    try:
        link = DriverCompanyLink.query.filter_by(
            driver_id=driver_id,
            company_id=company_id).first()
        if not link:
            raise ValueError("No relation to company found")

        history_update = DriverPointsHistory(
            link_id = link.id,
            points_change = points,
            current_points = (points+link.current_points),
            reason = reason
        )
        if sponsor_id:
            history_update.sponsor_user_id = sponsor_id
        db.session.add(history_update)
    except Exception as e:
        raise RuntimeError(f"Failed to change points for driver: {str(e)}") from e
# exisiting driver, auto accept into company
def ext_driver_auto_link(driver_id,company_id,points=0,points_reason="Auto-Accept"):
    try:
        # Create application
        driver_create_application(driver_id=driver_id,company_id=company_id)
        # Update application
        driver_status_application(driver_id=driver_id,company_id=company_id,status="accepted",status_reason="Auto-Accepted")
        # Add Company Link
        driver_active_link(driver_id=driver_id,company_id=company_id,points=points,reason=points_reason)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to create link: {str(e)}") from e

# Creates core user, driver profile, and application
def driver_create_signup(email,firstname,lastname,username,password,streetname,city,zipcode,company_id):
    try:
        # Create profile
        # Check Email uniqueness : email is unique identifier
        if Users.query.filter_by(email=email).first():
            raise ValueError(f"Email {email} is already registered to a user")
        # Check Username uniqueness : username is unique identifier
        if Users.query.filter_by(username=username).first():
            raise ValueError(f"Username {username} is already registered to a user")
        driver_user = driver_create_profile(email=email,firstname=firstname,
                                            lastname=lastname,username=username,
                                            password=password)
        # Add address
        driver_update_address(driver_id=driver_user.id,streetname=streetname,city=city,zipcode=zipcode)
        # Create application
        driver_create_application(driver_id=driver_user.id,company_id=company_id)
        db.session.commit()
        return driver_user
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to create driver: {str(e)}") from e


def driver_create_bulk(email,firstname,lastname,company_id,points,points_reason):
    try:
        # Create profile
        # Check Email uniqueness : email is unique identifier
        if Users.query.filter_by(email=email).first():
            raise ValueError(f"Email {email} is already registered to a user")
        username = generate_unique_username(email)
        password = "Password1"
        driver_user = driver_create_profile(email=email,firstname=firstname,
                                            lastname=lastname,username=username,
                                            password=password)
        # Create application
        driver_create_application(driver_id=driver_user.id,company_id=company_id)
        # Update application
        driver_status_application(driver_id=driver_user.id,company_id=company_id,status="accepted")
        # Add Company Link
        driver_active_link(driver_id=driver_user.id,company_id=company_id,points=points,reason=points_reason)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to change application: {str(e)}") from e









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

def add_driver_link(
    driver_profile: DriverProfile,
    company_id: int,
) -> DriverCompanyLink:
    # Check for previous relationship
    link = DriverCompanyLink.query.filter_by(
            driver_id=driver_profile.user_id
            ,company_id=company_id).first()
    if link:
        link.is_active = True
        db.session.add(link)
        return
    if not link:
        link = DriverCompanyLink(
            driver_profile = driver_profile,
            company_id = company_id,
            is_active = True)
        db.session.add(link)
        db.session.flush()
    

def driver_add_link(
    driver_profile: DriverProfile,
    company_id: int,
    reason: str = "New Link",
    sponsor_user_id: int | None = None,
    initial_points: int = 0
) -> DriverCompanyLink:
    link = DriverCompanyLink.query.filter_by(
            driver_id=driver_profile.user_id
            ,company_id=company_id).first()
    if not link:
            link = DriverCompanyLink(
                driver_profile = driver_profile,
                company_id = company_id
            )
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

def driver_a_update_address(
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


          
class DriverBuilder:
    def __init__(self, email, firstname, lastname):
        self.email = email.strip()
        self.firstname = firstname.strip()
        self.lastname = lastname.strip()
        
        # Optional Components & Defaults
        self.username = None
        self.password = "Password1" 
        self.address = {}
        self.sponsor_info = None # {id, auto_accept, points, reason}

    def with_auth(self, username, password):
        self.username = username.strip()
        self.password = password
        return self

    def with_address(self, street, city, zipcode):
        self.address = {
            "streetname": street.strip(),
            "city": city.strip(),
            "zipcode": zipcode.strip()
        }
        return self

    def with_company(self, company_id, auto_accept=False, points=0, reason="New Registration", sponsor_id=None):
        self.sponsor_info = {
            "company_id": company_id,
            "auto_accept": auto_accept,
            "points": points,
            "reason": reason,
            "sponsor_id" : sponsor_id
        }
        return self

    def build(self):
        try: 
            # 1. Validation
            if Users.query.filter_by(email=self.email).first():
                raise ValueError(f"Email {self.email} is already registered.")
            
            # 2. Logic for Username/Password
            final_username = self.username or generate_unique_username(self.email)         
            hashed_pw = generate_password_hash(self.password)

            # 3. Create core User & Profile
            new_user = Users(
                email=self.email, 
                username=final_username, 
                password=hashed_pw, 
                role="driver"
            )
            new_user.driver_profile = DriverProfile(
                firstname=self.firstname,
                lastname=self.lastname,
                **self.address,
                is_active=self.sponsor_info['auto_accept'] if self.sponsor_info else False
            )

            db.session.add(new_user)
            db.session.flush()

            # 4. Process Sponsor Application/Link
            if self.sponsor_info:
                status = "accepted" if self.sponsor_info['auto_accept'] else "pending"
                creation_time = datetime.now()

                app = DriverApplications(
                    driver_profile=new_user.driver_profile,
                    company_id=self.sponsor_info['company_id'],
                    status=status,
                    status_reason=self.sponsor_info['reason'],
                    status_date=creation_time if self.sponsor_info['auto_accept'] else None
                )
                db.session.add(app)

                if self.sponsor_info['auto_accept']:
                    # Create Link
                    link = DriverCompanyLink(
                        driver_profile = new_user.driver_profile,
                        company_id = self.sponsor_info['company_id'],
                        is_active = True,
                        status_date = creation_time
                    )
                    db.session.add(link)
                    db.session.flush()

                    # Create Points History
                    pts_change = DriverPointsHistory(
                        link_id = link.id,
                        points_change = self.sponsor_info['points'],
                        current_points = self.sponsor_info['points'],
                        update_date = creation_time,
                        reason = self.sponsor_info['reason'],
                        sponsor_user_id = self.sponsor_info['sponsor_id']
                    )
                    db.session.add(pts_change)

            db.session.commit()
            return new_user   
        except Exception as e:
            db.session.rollback()
            print(f"DEBUG BUILDER ERROR: {e}") 
            raise RuntimeError(f"Failed to create driver: {str(e)}") from e
        
class DriverService:
    # --- CREATION WORKFLOWS ---
    @staticmethod
    def register_online(data):
        """Path: Driver fills out the full web form."""
        return DriverBuilder(data['email'], data['firstname'], data['lastname']) \
            .with_auth(data['username'], data['password']) \
            .with_address(data['street'], data['city'], data['zip']) \
            .with_company(data['company_id'], auto_accept=False) \
            .build()

    @staticmethod
    def register_bulk(row, company_id):
        """Path: Auto-accepted, minimal info."""
        points = int(row.get('points', 0)) if row.get('points') else 0
        return DriverBuilder(row['email'], row['firstname'], row['lastname']) \
            .with_company(company_id, auto_accept=True, points=points, reason="Bulk Import") \
            .build()

    # --- MAINTENANCE WORKFLOWS ---
    @staticmethod
    def accept_application(driver_id,company_id,initial_points = 0,reason="Accept Application",sponsor_id=None):
        try:
            application = DriverApplications.query.filter_by(
                driver_id = driver_id,
                company_id=company_id).first()
            if not application:
                raise ValueError(f"No application found")
        
            application.status = "accepted"
            application.status_reason = reason
            application.status_date = datetime.now()
            db.session.add(application)

            DriverService.add_link(
                driver_id=driver_id,
                company_id=company_id,
                initial_points = initial_points,
                reason = reason,
                sponsor_id = sponsor_id
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()

    @staticmethod
    def add_link(driver_id,company_id,initial_points = 0,reason="New Link",sponsor_id=None):
        try:
            creation_time = datetime.now()
            link = DriverCompanyLink.query.filter_by(driver_id=driver_id,company_id=company_id).first()
            if link:
                if link.is_active:
                    return link
                else:
                    link.is_active = True
            else:
                link = DriverCompanyLink(
                    driver_id = driver_id,
                    company_id = company_id,
                    is_active = True,
                    status_date = creation_time
                )
            db.session.add(link)
            db.session.flush()

            # Create Points History
            pts_change = DriverPointsHistory(
                link_id = link.id,
                points_change = initial_points,
                current_points = initial_points,
                update_date = creation_time,
                reason = reason,
                sponsor_user_id = sponsor_id
            )
            db.session.add(pts_change)
            #db.session.commit()
            return link
        except Exception as e:
            db.session.rollback()
            raise RuntimeError(f"Failed to create driver-company link: {str(e)}") from e
        
    @staticmethod
    def remove_link(driver_id,company_id,reason="Link Ended",sponsor_id=None):
        try:
            link = DriverCompanyLink.query.filter_by(
                driver_id=driver_id,
                company_id=company_id).first()
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
                reason = reason,
                sponsor_user_id = sponsor_id
            )
            db.session.add(closeout_record)
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            raise RuntimeError(f"Failed to remove driver from company: {str(e)}") from e

    @staticmethod
    def add_points(driver_id, company_id, amount, reason="No Reason Given", sponsor_user_id=None):
        """Updates points for an existing driver."""
        try: 
            link = DriverCompanyLink.query.with_for_update().filter_by(
                driver_id=driver_id
                ,company_id=company_id).first()
            if not link:
                raise ValueError("Driver is not linked to this company.")

            new_record = DriverPointsHistory(
                link=link,
                points_change=amount,
                current_points = link.current_points + amount,
                reason=reason,
                sponsor_user_id=sponsor_user_id
            )
            db.session.add(new_record)
            db.session.commit()
            return link
        except DetachedInstanceError:
            db.session.rollback()
            raise RuntimeError("Database error: Driver profile is detached from session.")
        except Exception as e:
            db.session.rollback()
            raise RuntimeError(f"Database error while updating points: {str(e)}") from e

    @staticmethod
    def update_address(driver_id, street, city, zip_code):
        try:
            profile = DriverProfile.query.filter_by(user_id=driver_id).first()
            if not profile:
                raise ValueError(f"Driver does not exist with this id {driver_id}.")
            profile.streetname = street.strip()
            profile.city = city.strip()
            profile.zipcode = zip_code.strip()
            db.session.commit()
            return profile
        except DetachedInstanceError:
            db.session.rollback()
            raise RuntimeError("Database error: Driver profile is detached from session.")
        except Exception as e:
            db.session.rollback()
            raise RuntimeError(f"Database error while updating address: {str(e)}") from e
    
    @staticmethod
    def sync_driver_relationship(email, fname, lname, company_id, points=0,reason="Sync", sponsor_id=None):
        """
        The 'Smart' Logic for Bulk Uploads:
        1. Find or Create the User/Profile.
        2. Ensure they are a Driver.
        3. Find or Create the Link to the Company.
        4. Update the Points.
        """
        try:
            company_id = int(company_id)
            # --- STEP 1: Find or Create User ---
            user = Users.query.filter_by(email=email).first()
            
            if not user:
                # Scenario: Email doesn't exist at all -> Full Create
                user = Users(
                    email=email, 
                    username=generate_unique_username(email),
                    password=generate_password_hash("Password1"),
                    role="driver"
                )
                user.driver_profile = DriverProfile(firstname=fname, lastname=lname, is_active=True)
                db.session.add(user)
            else:
                # Scenario: User exists. Ensure they have a driver profile.
                if not user.driver_profile:
                    user.role = "driver" # Update role if they were something else
                    user.driver_profile = DriverProfile(firstname=fname, lastname=lname, is_active=True)
                
            db.session.flush()

            # --- STEP 2: Handle Application (Auto-Accept) ---
            # We check if an application already exists to avoid duplicates
            app = DriverApplications.query.filter_by(user_id=user.id, company_id=company_id).first()
            if not app:
                app = DriverApplications(
                    user_id=user.id, 
                    company_id=company_id, 
                    status="accepted", 
                    status_date=datetime.now(),
                    status_reason=reason
                )
            else:
                app.status="accepted"
                app.status_date=datetime.now()
                app.reason=reason
            db.session.add(app)

            # --- STEP 3: Find or Create the Link ---
            link = DriverCompanyLink.query.filter_by(driver_id=user.id, company_id=company_id).first()
            
            if not link:
                # Scenario: Driver exists but isn't linked to THIS company yet
                link = DriverCompanyLink(
                    driver_id=user.id,
                    company_id=company_id,
                    is_active=True,
                    current_points=0 # History will update this
                )
                db.session.add(link)
                db.session.flush()
            elif not link.is_active:
                link.is_active = True # Reactivate if they were previously removed

            # --- STEP 4: Update Points ---
            # Even if the driver existed with a link, we still add the new points
            if points != 0:
                history = DriverPointsHistory(
                    link_id=link.id,
                    points_change=points,
                    current_points=link.current_points + points,
                    reason=reason,
                    sponsor_user_id=sponsor_id
                )
                db.session.add(history)

            db.session.commit()
            return user

        except Exception as e:
            db.session.rollback()
            raise e

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
    firstname: str,
    lastname: str,
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
            role="admin"
        )
        new_user.admin_profile = AdminProfile(
            firstname = firstname,
            lastname = lastname
        )
        db.session.add(new_user)

        db.session.commit()
        db.session.refresh(new_user)
        return new_user
    
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to create admin: {str(e)}") from e