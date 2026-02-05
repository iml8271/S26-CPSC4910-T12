from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

# Initialize database
db = SQLAlchemy()

class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    role = db.Column(db.String(250), nullable=False)
