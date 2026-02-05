from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Initialize database
db = SQLAlchemy()

class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    role = db.Column(db.String(250), nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.now, nullable=False)

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

    #points
    sponsor = db.Column(db.String(250), nullable=False)
    points = db.Column(db.Integer,nullable=False,server_default="0")
    last_point_updated = db.Column(db.DateTime, default=datetime.now, nullable=False)

    #link back to user
    user = db.relationship("Users")
