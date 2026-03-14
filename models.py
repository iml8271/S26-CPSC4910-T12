from email.policy import default

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import select,desc, event
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime

# Initialize database
db = SQLAlchemy()

## USER ----
class Users(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False,index=True)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False,index=True)
    role = db.Column(db.String(50), nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # relationships are one-to-one and optional depending on role
    driver_profile = db.relationship("DriverProfile",back_populates="user",uselist=False,
        cascade="all,delete-orphan",lazy="joined")
    sponsor_profile = db.relationship("SponsorProfile",back_populates="user",uselist=False,
        cascade="all,delete-orphan",lazy="joined")
    admin_profile = db.relationship("AdminProfile",back_populates="user",uselist=False,
        cascade="all,delete-orphan",lazy="joined")
    
class PasswordChanges(db.Model):
    __tablename__ = "password_changes"
    # User ID
    user = db.relationship("Users")
    user_id = db.Column(db.Integer,db.ForeignKey('users.id'),primary_key=True,unique=True,nullable=False)

    # Attempt Date
    date = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Type of Change
    change = db.Column(db.String(250), nullable=False)

class LoginAttempts(db.Model):
    __tablename__ = "login_attempts"
    # User ID
    user = db.relationship("Users")
    user_id = db.Column(db.Integer,db.ForeignKey('users.id'),primary_key=True,unique=True,nullable=False)
    # Attempt Date
    date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    # Status 
    status = db.Column(db.String(10), nullable=False)


## DRIVER -------------
class DriverProfile(db.Model):
    __tablename__ = "driver_profile"

    # User ID
    user = db.relationship("Users",back_populates="driver_profile")
    user_id = db.Column(db.Integer,db.ForeignKey('users.id'),primary_key=True,unique=True,nullable=False)

    # Personal Details
    firstname = db.Column(db.String(250), nullable=False)
    lastname = db.Column(db.String(250), nullable=False)
    
    # Address fields
    streetname = db.Column(db.String(250))
    city = db.Column(db.String(250))
    zipcode = db.Column(db.String(10))

    # Status
    is_active = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # Sponsor Relationships
    company_links = db.relationship("DriverCompanyLink"
                                  ,back_populates="driver_profile")
    
class DriverApplications(db.Model):
    __tablename__ = "driver_applications"
    id = db.Column(db.Integer, primary_key=True)

    # User ID
    driver_profile = db.relationship("DriverProfile")
    user_id = db.Column(db.Integer,db.ForeignKey('driver_profile.user_id'),nullable=False)

    # Application Date
    app_date = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Sponsor
    company = db.relationship("SponsorCompany")
    company_id = db.Column(db.Integer,db.ForeignKey("sponsor_companies.id"),nullable=True)

    # Status 
    status = db.Column(db.String(10), nullable=False,default = "pending")  # 'pending', 'accepted', 'rejected'

    # Reason for status
    status_reason = db.Column(db.String(250), nullable=True)

    # Response Date
    status_date = db.Column(db.DateTime, nullable=True)


class DriverCompanyLink (db.Model):
    __tablename__ = "driver_company_link"
    id = db.Column(db.Integer, primary_key=True)

    # Driver
    driver_profile = db.relationship("DriverProfile",back_populates="company_links")
    driver_id = db.Column(db.Integer, db.ForeignKey('driver_profile.user_id'), nullable=False,index=True)

    # Sponsor Company
    company = db.relationship("SponsorCompany",back_populates="driver_links")
    company_id = db.Column(db.Integer, db.ForeignKey('sponsor_companies.id'), nullable=False,index=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=False, nullable=False, index=True)
    status_date = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Points
    point_history = db.relationship("DriverPointsHistory"
                            ,backref="link"
                            ,lazy="dynamic")
    current_points = db.Column(db.Integer,default=0, nullable=False)
    
class DriverPointsHistory(db.Model):
    __tablename__ = "driver_points_history"
    id = db.Column(db.Integer, primary_key=True)

    # Driver/SponsorCompany Relationship
    link_id = db.Column(db.Integer, db.ForeignKey('driver_company_link.id'), nullable=False)

    # Points History
    points_change = db.Column(db.Integer,nullable=False,server_default="0")
    current_points = db.Column(db.Integer,nullable=False,server_default="0")
    update_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    reason = db.Column(db.String(250), nullable=False)

    # Sponsor Records
    sponsor_user = db.relationship("SponsorProfile")
    sponsor_user_id = db.Column(db.Integer,db.ForeignKey("sponsor_profile.user_id"),nullable=True)      

@event.listens_for(DriverPointsHistory, 'after_insert')
def update_link_points(mapper, connection, target):
    # Everytime a record is added, update link's points

    # Target is new DriverPointsHistory object
    link_table = DriverCompanyLink.__table__
    
    # Direct SQL update
    connection.execute(
        link_table.update()
        .where(link_table.c.id == target.link_id)
        .values(current_points=link_table.c.current_points + target.points_change)
    )

## SPONSOR -----
class SponsorProfile(db.Model):
    __tablename__ = "sponsor_profile"

    # User ID
    user = db.relationship("Users",back_populates="sponsor_profile")
    user_id = db.Column(db.Integer,db.ForeignKey('users.id'),primary_key=True,unique=True,nullable=False)

    # Personal Details
    firstname = db.Column(db.String(250), nullable=False)
    lastname = db.Column(db.String(250), nullable=False)

    # Company
    company_id = db.Column(db.Integer,db.ForeignKey("sponsor_companies.id"),nullable=False)
    company = db.relationship("SponsorCompany",back_populates="sponsor_users")

class SponsorCompany(db.Model):
    __tablename__ = "sponsor_companies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150),unique=True,nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False,index=True)
    phone = db.Column(db.String(50), nullable=False)
    logo_filename = db.Column(db.String(255), nullable=True)
    brand_color = db.Column(db.String(255), nullable=True)
    points_conversion = db.Column(db.DECIMAL(10,2),nullable=False,default=1)

    # Employees
    sponsor_users = db.relationship("SponsorProfile",back_populates="company")
    driver_links = db.relationship("DriverCompanyLink", back_populates="company")

class SponsorCompanyRules(db.Model):
    __tablename__ = "Sponsor_Org_Rules"
    #company and tracking info
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey(SponsorCompany.id), nullable = False)
    #rule info
    #whether the rule describes a good or bad driving behavior
    nature = db.Column(db.String(10), nullable = False)
    #the rule itself
    rule = db.Column(db.String(255), nullable = False)


## SUPPORT -----
class SupportRequest(db.Model):
    __tablename__ = "support_requests"
    #info about the source
    req_id = db.Column(db.Integer, primary_key = True)
    source_id = db.Column(db.Integer, nullable = False)
    source_org = db.Column(db.Integer, nullable = False)

    #info about the request
    req_type = db.Column(db.String(100), nullable = False)
    req_details = db.Column(db.String(10000), nullable = False)
    creation_date = db.Column(db.DateTime, nullable = False, default=datetime.now)
    status = db.Column(db.String(20), nullable=False, default="Open")

## ADMIN -----------------------
class AdminProfile(db.Model):
    __tablename__ = "admin_profile"

    # User ID
    user = db.relationship("Users",back_populates="admin_profile")
    user_id = db.Column(db.Integer,db.ForeignKey('users.id'),primary_key=True,unique=True,nullable=False)

    # Personal Details
    firstname = db.Column(db.String(250), nullable=False)
    lastname = db.Column(db.String(250), nullable=False)