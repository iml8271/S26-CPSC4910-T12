-- SQLite

INSERT INTO users (id, username, password, email, role, creation_date)
VALUES (1,"driver1","Password1","driver@email.com","driver",'2025-01-01 10:00:00');

INSERT INTO users (id, username, password, email, role, creation_date)
VALUES (2,"admin1","Password1","admin@email.com","admin",'2025-01-01 10:00:00');

INSERT INTO users (id, username, password, email, role, creation_date)
VALUES (3,"sponsor1","Password1","sponsor@email.com","sponsor",'2025-01-01 10:00:00');


INSERT INTO driver_profile (id, user_id, firstname, lastname, streetname, city, zipcode, company_id, points, last_point_updated)
VALUES (1,1,"Drivery","DriverGuy","123 Seame Street","Rainbow","12345",2,0,'2025-01-01 10:00:00');

