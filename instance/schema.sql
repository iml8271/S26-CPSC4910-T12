-- =============================================================
-- PointFleet MySQL Schema
-- Target: AWS RDS MySQL (Team12_DB)
-- =============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- =============================================================
-- TABLES
-- Tables with no foreign key dependencies go first,
-- then tables that reference them.
-- =============================================================

CREATE TABLE IF NOT EXISTS users (
    id              INT             NOT NULL AUTO_INCREMENT,
    username        VARCHAR(80)     NOT NULL,
    password        VARCHAR(255)    NOT NULL,
    email           VARCHAR(120)    NOT NULL,
    role            VARCHAR(50)     NOT NULL,
    creation_date   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE INDEX ix_users_username (username),
    UNIQUE INDEX ix_users_email (email),
    CONSTRAINT valid_role CHECK (role IN ('driver', 'sponsor', 'admin'))
);

CREATE TABLE IF NOT EXISTS sponsor_companies (
    id                  INT             NOT NULL AUTO_INCREMENT,
    name                VARCHAR(150)    NOT NULL,
    email               VARCHAR(120)    NOT NULL,
    phone               VARCHAR(50)     NOT NULL,
    logo_filename       VARCHAR(255),
    brand_color         VARCHAR(255),
    points_conversion   DECIMAL(10,2)   NOT NULL,
    priceMax            INT             NOT NULL DEFAULT 100,
    explicit            BOOLEAN         NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id),
    UNIQUE (name),
    UNIQUE INDEX ix_sponsor_companies_email (email)
);

CREATE TABLE IF NOT EXISTS support_requests (
    req_id          INT             NOT NULL AUTO_INCREMENT,
    source_id       INT             NOT NULL,
    source_org      INT             NOT NULL,
    req_type        VARCHAR(100)    NOT NULL,
    req_details     VARCHAR(10000)  NOT NULL,
    creation_date   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status          VARCHAR(20)     NOT NULL DEFAULT 'Open',
    PRIMARY KEY (req_id)
);

CREATE TABLE IF NOT EXISTS password_changes (
    user_id     INT             NOT NULL,
    date        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `change`      VARCHAR(250)    NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE (user_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS login_attempts (
    user_id     INT             NOT NULL,
    date        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status      VARCHAR(10)     NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE (user_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INT             NOT NULL AUTO_INCREMENT,
    event_type  VARCHAR(50)     NOT NULL,
    user_id     INT,
    username    VARCHAR(150),
    ip_address  VARCHAR(45),
    details     TEXT,
    timestamp   DATETIME        DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_audit_log_event_type (event_type),
    INDEX ix_audit_log_timestamp (timestamp),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS admin_profile (
    user_id     INT             NOT NULL,
    firstname   VARCHAR(250)    NOT NULL,
    lastname    VARCHAR(250)    NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE (user_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS driver_profile (
    user_id     INT             NOT NULL,
    firstname   VARCHAR(250)    NOT NULL,
    lastname    VARCHAR(250)    NOT NULL,
    streetname  VARCHAR(250),
    city        VARCHAR(250),
    zipcode     VARCHAR(10),
    is_active   BOOLEAN         NOT NULL DEFAULT FALSE,
    PRIMARY KEY (user_id),
    UNIQUE (user_id),
    INDEX ix_driver_profile_is_active (is_active),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sponsor_profile (
    user_id     INT             NOT NULL,
    firstname   VARCHAR(250)    NOT NULL,
    lastname    VARCHAR(250)    NOT NULL,
    company_id  INT             NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE (user_id),
    FOREIGN KEY (user_id)   REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES sponsor_companies (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Sponsor_Org_Rules (
    id          INT             NOT NULL AUTO_INCREMENT,
    company_id  INT             NOT NULL,
    nature      VARCHAR(10)     NOT NULL,
    rule        VARCHAR(255)    NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (company_id) REFERENCES sponsor_companies (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS driver_applications (
    id              INT             NOT NULL AUTO_INCREMENT,
    user_id         INT             NOT NULL,
    app_date        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    company_id      INT,
    status          VARCHAR(10)     NOT NULL DEFAULT 'pending',
    status_reason   VARCHAR(250),
    status_date     DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'accepted', 'rejected', 'expired')),
    FOREIGN KEY (user_id)    REFERENCES driver_profile (user_id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES sponsor_companies (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS driver_company_link (
    id              INT             NOT NULL AUTO_INCREMENT,
    driver_id       INT             NOT NULL,
    company_id      INT             NOT NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT FALSE,
    status_date     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    current_points  INT             NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    INDEX ix_driver_company_link_is_active (is_active),
    INDEX ix_driver_company_link_driver_id (driver_id),
    INDEX ix_driver_company_link_company_id (company_id),
    CONSTRAINT chk_points_non_negative CHECK (current_points >= 0),
    FOREIGN KEY (driver_id)  REFERENCES driver_profile (user_id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES sponsor_companies (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS driver_points_history (
    id              INT             NOT NULL AUTO_INCREMENT,
    link_id         INT             NOT NULL,
    points_change   INT             NOT NULL DEFAULT 0,
    current_points  INT             NOT NULL DEFAULT 0,
    update_date     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason          VARCHAR(250)    NOT NULL,
    sponsor_user_id INT,
    PRIMARY KEY (id),
    FOREIGN KEY (link_id)         REFERENCES driver_company_link (id) ON DELETE CASCADE,
    FOREIGN KEY (sponsor_user_id) REFERENCES sponsor_profile (user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS driver_alerts (
    id              INT         NOT NULL AUTO_INCREMENT,
    driver_id       INT,
    points_alerts   BOOLEAN     DEFAULT TRUE,
    order_alerts    BOOLEAN     DEFAULT TRUE,
    PRIMARY KEY (id),
    UNIQUE (driver_id),
    FOREIGN KEY (driver_id) REFERENCES driver_profile (user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS driver_preferences (
    id              INT         NOT NULL AUTO_INCREMENT,
    driver_id       INT,
    points_alerts   BOOLEAN,
    order_alerts    BOOLEAN,
    PRIMARY KEY (id),
    UNIQUE (driver_id),
    FOREIGN KEY (driver_id) REFERENCES driver_profile (user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS driver_Org_RelationShip (
    user_id     INT             NOT NULL,
    company     VARCHAR(150)    NOT NULL,
    company_id  INT             NOT NULL,
    isActive    BOOLEAN         NOT NULL DEFAULT FALSE,
    PRIMARY KEY (user_id),
    FOREIGN KEY (user_id)    REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES sponsor_companies (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sponsor_catalog (
    id          INT         NOT NULL AUTO_INCREMENT,
    company_id  INT         NOT NULL,
    item_info   JSON,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id),
    FOREIGN KEY (company_id) REFERENCES sponsor_companies (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS invoices (
    id              INT             NOT NULL AUTO_INCREMENT,
    company_id      INT             NOT NULL,
    start_date      DATE            NOT NULL,
    end_date        DATE            NOT NULL,
    total_points    INT             NOT NULL DEFAULT 0,
    total_amount    DECIMAL(10,2)   NOT NULL DEFAULT 0.00,
    created_by      INT             NOT NULL,
    created_date    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes           VARCHAR(500),
    PRIMARY KEY (id),
    FOREIGN KEY (company_id) REFERENCES sponsor_companies (id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by) REFERENCES admin_profile (user_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id                  INT             NOT NULL AUTO_INCREMENT,
    invoice_id          INT             NOT NULL,
    driver_id           INT             NOT NULL,
    points_history_id   INT,
    description         VARCHAR(255)    NOT NULL,
    points              INT             NOT NULL,
    amount              DECIMAL(10,2)   NOT NULL,
    transaction_date    DATETIME        NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (invoice_id)        REFERENCES invoices (id) ON DELETE CASCADE,
    FOREIGN KEY (driver_id)         REFERENCES driver_profile (user_id),
    FOREIGN KEY (points_history_id) REFERENCES driver_points_history (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    PRIMARY KEY (version_num)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id        INT             NOT NULL AUTO_INCREMENT,
    date            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id         INT             NOT NULL,
    org_id          INT             NOT NULL,
    dollar_price    DECIMAL(10,2)   NOT NULL,
    point_price     INT             NOT NULL,
    PRIMARY KEY (order_id),
    UNIQUE (order_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT,
    FOREIGN KEY (org_id)  REFERENCES sponsor_companies (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS order_items (
    id                  INT             NOT NULL AUTO_INCREMENT,
    order_id            INT             NOT NULL,
    product_name        VARCHAR(200)    NOT NULL,
    quantity            INT             NOT NULL DEFAULT 1,
    unit_price_dollars  DECIMAL(10,2)   NOT NULL,
    unit_price_points   INT             NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS order_history (
    id                      INT             NOT NULL AUTO_INCREMENT,
    link_id                 INT             NOT NULL,
    date                    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    item_id                 INT             NOT NULL,
    purchase_point_price    INT             NOT NULL,
    purchase_dollar_price   DECIMAL(10,2)   NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (link_id)  REFERENCES driver_company_link (id) ON DELETE CASCADE,
    FOREIGN KEY (item_id)  REFERENCES sponsor_catalog (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS order_status (
    id            INT           NOT NULL AUTO_INCREMENT,
    link_id       INT           NOT NULL,
    order_id      INT           NOT NULL,
    status        VARCHAR(20)   NOT NULL DEFAULT 'ordered',
    update_date   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    advance_after DATETIME      NULL,
    PRIMARY KEY (id),
    CONSTRAINT valid_order_status CHECK (status IN ('ordered', 'shipping', 'arrived')),
    FOREIGN KEY (link_id)  REFERENCES driver_company_link (id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE
);

SET FOREIGN_KEY_CHECKS = 1;


-- =============================================================
-- TRIGGERS
-- =============================================================

-- Trigger 1: Set creation_date on users if not provided
DELIMITER $$
CREATE TRIGGER trg_user_creation_date
BEFORE INSERT ON users
FOR EACH ROW
BEGIN
    IF NEW.creation_date IS NULL THEN
        SET NEW.creation_date = NOW();
    END IF;
END$$
DELIMITER ;

-- Trigger 2: Log password changes
DELIMITER $$
CREATE TRIGGER trg_password_update
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    IF OLD.password <> NEW.password THEN
        INSERT INTO password_changes (user_id, date, `change`)
        VALUES (NEW.id, NOW(), 'Password updated');
    END IF;
END$$
DELIMITER ;

-- Trigger 3: Sync current_points on driver_company_link
--            after every insert into driver_points_history
DELIMITER $$
CREATE TRIGGER after_points_insert
AFTER INSERT ON driver_points_history
FOR EACH ROW
BEGIN
    UPDATE driver_company_link
    SET current_points = current_points + NEW.points_change
    WHERE id = NEW.link_id;
END$$
DELIMITER ;

-- Trigger 4: Auto-create driver_alerts row when a driver profile is created
DELIMITER $$
CREATE TRIGGER after_driver_profile_insert
AFTER INSERT ON driver_profile
FOR EACH ROW
BEGIN
    INSERT INTO driver_alerts (driver_id, points_alerts, order_alerts)
    VALUES (NEW.user_id, TRUE, TRUE);
END$$
DELIMITER ;

-- Trigger 5: Auto-create order_status row when a new order is placed.
--             advance_after is randomized between 1-3 days from now.
DELIMITER $$
CREATE TRIGGER after_order_insert
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
    DECLARE v_link_id INT DEFAULT NULL;

    SELECT id INTO v_link_id
    FROM driver_company_link
    WHERE driver_id  = NEW.user_id
      AND company_id = NEW.org_id
    LIMIT 1;

    IF v_link_id IS NOT NULL THEN
        INSERT INTO order_status (link_id, order_id, status, update_date, advance_after)
        VALUES (
            v_link_id,
            NEW.order_id,
            'ordered',
            NOW(),
            NOW() + INTERVAL (1 + FLOOR(RAND() * 3)) DAY
        );
    END IF;
END$$
DELIMITER ;

-- Trigger 6: Activate or create driver_company_link when an application is accepted (update)
DELIMITER $$
CREATE TRIGGER after_application_accepted
AFTER UPDATE ON driver_applications
FOR EACH ROW
BEGIN
    IF NEW.status = 'accepted' AND OLD.status != 'accepted' THEN

        UPDATE driver_company_link
        SET is_active   = 1,
            status_date = NOW()
        WHERE driver_id  = NEW.user_id
          AND company_id = NEW.company_id;

        IF ROW_COUNT() = 0 THEN
            INSERT INTO driver_company_link (driver_id, company_id, is_active, status_date, current_points)
            VALUES (NEW.user_id, NEW.company_id, 1, NOW(), 0);
        END IF;

    END IF;
END$$
DELIMITER ;

-- Trigger 7: Activate or create driver_company_link when an application is inserted as accepted
DELIMITER $$
CREATE TRIGGER after_application_insert
AFTER INSERT ON driver_applications
FOR EACH ROW
BEGIN
    IF NEW.status = 'accepted' THEN

        UPDATE driver_company_link
        SET is_active   = 1,
            status_date = NOW()
        WHERE driver_id  = NEW.user_id
          AND company_id = NEW.company_id;

        IF ROW_COUNT() = 0 THEN
            INSERT INTO driver_company_link (driver_id, company_id, is_active, status_date, current_points)
            VALUES (NEW.user_id, NEW.company_id, 1, NOW(), 0);
        END IF;

    END IF;
END$$
DELIMITER ;

-- =============================================================
-- STORED PROCEDURES
-- =============================================================

-- Procedure 1: Approve a driver application by ID.
--              Updates the application status to 'accepted'.
--              The after_application_accepted trigger then
--              automatically activates or creates the
--              driver_company_link.
DELIMITER $$
CREATE PROCEDURE approve_driver_application(
    IN p_application_id INT
)
BEGIN
    DECLARE v_user_id    INT;
    DECLARE v_company_id INT;

    -- Get application info
    SELECT user_id, company_id
    INTO v_user_id, v_company_id
    FROM driver_applications
    WHERE id = p_application_id;

    -- Bail if application not found
    IF v_user_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Application not found';
    END IF;

    -- Mark as accepted (trigger handles the link activation)
    UPDATE driver_applications
    SET status      = 'accepted',
        status_date = NOW()
    WHERE id = p_application_id;

END$$
DELIMITER ;


-- Procedure 2: Reject a driver application by ID.
--              Updates the application status to 'rejected' and
--              deactivates the driver_company_link if one exists.
DELIMITER $$
CREATE PROCEDURE reject_driver_application(
    IN p_application_id INT,
    IN p_reason         VARCHAR(250)
)
BEGIN
    DECLARE v_user_id    INT;
    DECLARE v_company_id INT;

    -- Get application info
    SELECT user_id, company_id
    INTO v_user_id, v_company_id
    FROM driver_applications
    WHERE id = p_application_id;

    -- Bail if application not found
    IF v_user_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Application not found';
    END IF;

    -- Mark as rejected
    UPDATE driver_applications
    SET status        = 'rejected',
        status_date   = NOW(),
        status_reason = p_reason
    WHERE id = p_application_id;

    -- Deactivate the link if one exists
    UPDATE driver_company_link
    SET is_active   = 0,
        status_date = NOW()
    WHERE driver_id  = v_user_id
      AND company_id = v_company_id;

END$$
DELIMITER ;


-- =============================================================
-- DATABASE JOBS
-- NOTE: Run `SET GLOBAL event_scheduler = ON;` on your RDS
-- instance via the parameter group before these will fire.
-- =============================================================

-- Job 1: Auto-expire pending applications older than 30 days.
--        Runs every day at 2:00 AM.
DELIMITER $$
CREATE EVENT expire_old_applications
ON SCHEDULE EVERY 1 DAY
STARTS (CURRENT_DATE + INTERVAL 1 DAY + INTERVAL 2 HOUR)
DO
BEGIN
    UPDATE driver_applications
    SET status        = 'expired',
        status_date   = NOW(),
        status_reason = 'Auto-expired: no response within 30 days'
    WHERE status  = 'pending'
      AND app_date < (NOW() - INTERVAL 30 DAY);
END$$
DELIMITER ;


-- Job 2: Advance order status automatically.
--        ordered  -> shipping : after randomized 1-3 days
--        shipping -> arrived  : after another randomized 1-3 days
--        Runs every hour.
DELIMITER $$
CREATE EVENT advance_order_status
ON SCHEDULE EVERY 1 HOUR
DO
BEGIN
    -- Step 1: Advance 'ordered' -> 'shipping' where advance_after has passed
    UPDATE order_status
    SET status        = 'shipping',
        update_date   = NOW(),
        advance_after = NOW() + INTERVAL (1 + FLOOR(RAND() * 3)) DAY
    WHERE status        = 'ordered'
      AND advance_after <= NOW();

    -- Step 2: Advance 'shipping' -> 'arrived' where advance_after has passed
    UPDATE order_status
    SET status        = 'arrived',
        update_date   = NOW(),
        advance_after = NULL
    WHERE status        = 'shipping'
      AND advance_after <= NOW();
END$$
DELIMITER ;