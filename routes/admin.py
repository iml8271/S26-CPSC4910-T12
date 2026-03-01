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

admin_bp = Blueprint("admin",__name__,url_prefix="/admin")

@admin_bp.before_request
def restrict_to_driver():
    # User has to be logged in
    if not current_user.is_authenticated:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('auth.handle_login'))

    # User has to be a driver
    if current_user.role != "admin":
        flash("Access denied: Admins only.", "danger")
        return redirect(url_for('auth.handle_login'))
    
    # User has to have a profile
    if not g.profile:
        flash("Admin profile not found. Please contact an admin.", "danger")
        return redirect(url_for('auth.logout'))