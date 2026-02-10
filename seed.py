from app import app, db   # adjust to how you import your app and db
from models import Users, DriverProfile, SponsorCompany, SponsorProfile
from datetime import datetime
from werkzeug.security import generate_password_hash,check_password_hash

def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        password = generate_password_hash("test",method="pbkdf2:sha256")

        d1 = Users(username="driver1", password=password, email="d1@test.com", role="driver")
        db.session.add(d1)
        db.session.commit()

        a1 = Users(username="admin1", password=password, email="admin@test.com", role="admin")
        db.session.add(a1)
        db.session.commit()

        s1 = Users(username="sponsor1", password=password, email="sponsor@test.com", role="sponsor")
        db.session.add(s1)
        db.session.commit()

        
        c1 = SponsorCompany(name="Amazon", email="amazon@test.com", phone="123")
        db.session.add(c1)
        db.session.commit()

        c2 = SponsorCompany(name="Sephora", email="sephora@test.com", phone="123")
        db.session.add(c2)
        db.session.commit()

        c3 = SponsorCompany(name="Nike", email="nike@test.com", phone="123")
        db.session.add(c3)
        db.session.commit()

        

        dp1 = DriverProfile(
            user_id=d1.id,
            company_id=c1.id,
            firstname="TestDriver",
            lastname="DriverGal",
            streetname="123 St",
            city="Greenville",
            zipcode="29607",
            points=0
        )
        db.session.add(dp1)
        db.session.commit()

        sp1 = SponsorProfile(
            user_id=s1.id,
            firstname="TestSponsor",
            lastname="SponsorGuy",
            company_id=c1.id,
        )
        db.session.add(sp1)
        db.session.commit()

        print("Seeded!")

if __name__ == "__main__":
    seed()