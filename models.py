from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import select,desc
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
    streetname = db.Column(db.String(250), nullable=False)
    city = db.Column(db.String(250), nullable=False)
    zipcode = db.Column(db.String(10), nullable=False)

    # Sponsor
    company = db.relationship("SponsorCompany",back_populates="drivers")
    company_id = db.Column(db.Integer,db.ForeignKey("sponsor_companies.id"),nullable=False)

    #points
    driver_points_history = db.relationship("DriverPointsHistory"
                            ,back_populates="driver_profile"
                            ,order_by="DriverPointsHistory.update_date.desc()")
    @hybrid_property
    def points(self):
        return self.driver_points_history[0].points_total if self.driver_points_history else 0
    
class DriverApplications(db.Model):
    __tablename__ = "driver_applications"

    # User ID
    driver_profile = db.relationship("DriverProfile")
    user_id = db.Column(db.Integer,db.ForeignKey('driver_profile.user_id'),primary_key=True,unique=True,nullable=False)

    # Sponsor
    company = db.relationship("SponsorCompany")
    company_id = db.Column(db.Integer,db.ForeignKey("sponsor_companies.id"),nullable=False)

    # Status 
    status = db.Column(db.String(10), nullable=False)

    # Reason
    reason = db.Column(db.String(250), nullable=False)

    
class DriverPointsHistory(db.Model):
    __tablename__ = "driver_points_history"
    id = db.Column(db.Integer, primary_key=True)

    # User ID
    driver_profile = db.relationship("DriverProfile",back_populates="driver_points_history")
    user_id = db.Column(db.Integer,db.ForeignKey('driver_profile.user_id'),nullable=False)

    # Points History
    points_change = db.Column(db.Integer,nullable=False,server_default="0")
    points_total = db.Column(db.Integer,nullable=False,server_default="0")
    update_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    reason = db.Column(db.String(250), nullable=False)

    # Sponsor Records
    sponsor_user = db.relationship("SponsorProfile")
    sponsor_user_id = db.Column(db.Integer,db.ForeignKey("sponsor_profile.user_id"),nullable=False)      


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

    # Employees
    sponsor_users = db.relationship("SponsorProfile",back_populates="company")
    drivers = db.relationship("DriverProfile",back_populates="company")

<<<<<<< Updated upstream
class SupportRequest(db.Model):
    __tablename__ = "support_requests"
    #info about the source
    req_id = db.Column(db.Integer, primary_key = True)
    source_id = db.Column(db.Integer, nullable = False)
    source_org = db.Column(db.Integer, nullable = False)

    #info about the request
    req_type = db.Column(db.String(100), nullable = False)
    req_details = db.Column(db.String(10000), nullable = False)
    creation_date = db.Column(db.DateTime, nullable = False)
    status = db.Column(db.String(20), nullable=False, default="Open")

=======
>>>>>>> Stashed changes
