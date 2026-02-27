from models import db,Users,DriverProfile,DriverApplications,DriverPointsHistory,SponsorProfile
from werkzeug.security import generate_password_hash

# Universal ---------
def generate_unique_username(email):
    base = email.split('@')[0]
    username = base
    counter = 1
    while Users.query.filter_by(username=username).first():
        username = f"{base}{counter}"
        counter += 1
    return username

# DRIVER ------------------
def driver_create(
    email: str,
    firstname: str,
    lastname: str,
    company_id: int,
    streetname: str = "",
    city: str = "",
    zipcode: str = "",
    username: str | None = None,
    password: str | None = None,
    points_to_add: int = 0,
    points_reason: str = "New Driver",
    status: str = "pending",
    application_reason: str = "New Driver",
    sponsor_user_id: int | None = None
) -> Users:
    """
    Creates a driver user, profile, and application record.
    """
    # Check uniqueness
    if Users.query.filter_by(email=email).first():
        raise ValueError(f"Email {email} is already registered to a user")
    
    # Username handling
    username = username or generate_unique_username(email)
    if username and Users.query.filter_by(username=username).first():
        raise ValueError(f"Username {username} is already taken")

    # Password handling
    # temp password until user creates new password
    password= password or "Password1"
    hashed_password = generate_password_hash(password,method="pbkdf2:sha256") if password else None

    # Check activeness
    is_active = (status == "approved")

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
            company_id=company_id,
            is_active = is_active
        )

        db.session.add(new_user)

        # Create application record
        application = DriverApplications(
            driver_profile = new_user.driver_profile,
            company_id=company_id,
            status=status,
            reason=application_reason
        )
        db.session.add(application)

        # Create points record
        if is_active:
            points_history = DriverPointsHistory(
                driver_profile = new_user.driver_profile,
                points_change = points_to_add,
                current_points = points_to_add,
                reason = points_reason,
                sponsor_user_id = sponsor_user_id
            )
            db.session.add(points_history)

        db.session.commit()
        return new_user
    
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to create driver: {str(e)}") from e
    
def driver_update_points(
    user_id: int,
    points_to_add = 0,
    points_reason = "None given",
    sponsor_user_id: int | None = None,
) -> DriverProfile:
    if points_to_add == 0:
        raise ValueError("No points to add (change is zero)")
    
    driver = DriverProfile.query.filter_by(user_id = user_id).first()
    if not driver: 
        raise ValueError(f"No driver found with user_id {user_id}")
    try:
        current_points = driver.points or 0
        new_total = current_points + points_to_add

        points_history = DriverPointsHistory(
            user_id=driver.user_id,
            points_change = points_to_add,
            current_points = new_total,
            reason = points_reason,
            sponsor_user_id = sponsor_user_id
        )
        db.session.add(points_history)
        db.session.commit()
        db.session.refresh(driver)
        return driver
    
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Database error while updating points: {str(e)}") from e

def driver_update_address(
    user_id: int,
    streetname: str ,
    city: str,
    zipcode: str,
) -> DriverProfile:    
    driver = DriverProfile.query.filter_by(user_id = user_id).first()
    if not driver: 
        raise ValueError(f"No driver found with user_id {user_id}")

    if not streetname.strip():
        raise ValueError("Street name cannot be empty")
    if not city.strip():
        raise ValueError("City cannot be empty")
    if not zipcode.strip():
        raise ValueError("Zip code cannot be empty")
    
    try:
        driver.streetname = streetname.strip()
        driver.city = city.strip()
        driver.zipcode = zipcode.strip()

        db.session.commit()
        db.session.refresh(driver)

        return driver

    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Failed to update driver address: {str(e)}")
    
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