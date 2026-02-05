from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Initialize database
db = SQLAlchemy()

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


class DriverProfile(db.Model):
    __tablename__ = "driver_profile"
    id = db.Column(db.Integer,primary_key=True)
    user_id = db.Column(db.Integer,db.ForeignKey('users.id'),unique=True,nullable=False)

    # Personal Details
    firstname = db.Column(db.String(250), nullable=False)
    lastname = db.Column(db.String(250), nullable=False)
    
    # Address fields
    streetname = db.Column(db.String(250), nullable=False)
    city = db.Column(db.String(250), nullable=False)
    zipcode = db.Column(db.String(10), nullable=False)

    # Sponsor
    company_id = db.Column(db.Integer,db.ForeignKey("sponsor_companies.id"),nullable=False)

    #points
    points = db.Column(db.Integer,nullable=False,server_default="0")
    last_point_updated = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # relationships
    user = db.relationship("Users",back_populates="driver_profile")
    company = db.relationship("SponsorCompany",back_populates="drivers")

class SponsorProfile(db.Model):
    __tablename__ = "sponsor_profile"
    id = db.Column(db.Integer,primary_key=True)
    user_id = db.Column(db.Integer,db.ForeignKey('users.id'),unique=True,nullable=False)

    # Personal Details
    firstname = db.Column(db.String(250), nullable=False)
    lastname = db.Column(db.String(250), nullable=False)

    #sponsor
    company_id = db.Column(db.Integer,db.ForeignKey("sponsor_companies.id"),nullable=False)
    company = db.relationship("SponsorCompany",back_populates="sponsor_users")

    #link back to user
    user = db.relationship("Users",back_populates="sponsor_profile")

class SponsorCompany(db.Model):
    __tablename__ = "sponsor_companies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150),unique=True,nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False,index=True)
    phone = db.Column(db.String(50), nullable=False)
    sponsor_users = db.relationship("SponsorProfile",back_populates="company")
    drivers = db.relationship("DriverProfile",back_populates="company")