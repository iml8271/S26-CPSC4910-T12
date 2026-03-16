from app import app, db
from models import (
    Users, SponsorCompany, SponsorProfile, DriverProfile, 
    DriverApplications, DriverCompanyLink, DriverPointsHistory
)
from werkzeug.security import generate_password_hash
from datetime import datetime

def seed_database():
    with app.app_context():
        print("--- Starting Database Seed ---")
        
        # 1. Clear existing data
        db.drop_all()
        db.create_all()
        print("Database cleared and tables recreated.")

        hashed_pwd = generate_password_hash('test', method='pbkdf2:sha256')

        # 2. Create 3 Companies
        companies_data = [
            {"name": "Apex Trucking", "email": "info@apextrucking.com", "phone": "555-0101"},
            {"name": "Horizon Logistics", "email": "contact@horizon.com", "phone": "555-0202"},
            {"name": "Swift Delivery", "email": "support@swiftdelivery.com", "phone": "555-0303"}
        ]
        
        companies = []
        for c in companies_data:
            company = SponsorCompany(
                name=c['name'],
                email=c['email'],
                phone=c['phone'],
                points_conversion=1.0
            )
            db.session.add(company)
            companies.append(company)
        
        db.session.flush() # Flush to get company IDs
        print(f"Created {len(companies)} companies.")

        # 3. Create 1 Sponsor and 2 Drivers for each company
        for i, company in enumerate(companies, 1):
            # --- Create Sponsor ---
            s_user = Users(
                username=f"sponsor{i}",
                email=f"sponsor{i}@test.com",
                password=hashed_pwd,
                role="sponsor"
            )
            db.session.add(s_user)
            db.session.flush()

            s_profile = SponsorProfile(
                user_id=s_user.id,
                firstname=f"Sponsor{i}",
                lastname="Manager",
                company_id=company.id
            )
            db.session.add(s_profile)

            # --- Create 2 Drivers for this company ---
            for j in range(1, 3):
                driver_num = ((i-1) * 2) + j
                d_user = Users(
                    username=f"driver{driver_num}",
                    email=f"driver{driver_num}@test.com",
                    password=hashed_pwd,
                    role="driver"
                )
                db.session.add(d_user)
                db.session.flush()

                d_profile = DriverProfile(
                    user_id=d_user.id,
                    firstname=f"Driver{driver_num}",
                    lastname="Test",
                    is_active=True
                )
                db.session.add(d_profile)
                db.session.flush()

                # --- Create Application (Accepted) ---
                app_record = DriverApplications(
                    user_id=d_profile.user_id,
                    company_id=company.id,
                    status="accepted",
                    status_reason="Seeded Account",
                    status_date=datetime.now()
                )
                db.session.add(app_record)

                # --- Create Company Link (Wallet) ---
                link = DriverCompanyLink(
                    driver_id=d_profile.user_id,
                    company_id=company.id,
                    is_active=True,
                    current_points=0 # Will be updated by history event
                )
                db.session.add(link)
                db.session.flush()

                # --- Add Initial Points History ---
                # This triggers your @event.listens_for logic to update link.current_points
                history = DriverPointsHistory(
                    link_id=link.id,
                    points_change=100, # Start everyone with 100 points
                    current_points=100,
                    reason="Welcome Bonus",
                    sponsor_user_id=s_profile.user_id
                )
                db.session.add(history)

        db.session.commit()
        print("--- Seed Complete: Successfully created 3 Sponsors and 6 Drivers ---")

if __name__ == "__main__":
    seed_database()