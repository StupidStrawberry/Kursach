-- telegram.sql
-- Хранение данных Telegram API

START TRANSACTION;

CREATE TABLE IF NOT EXISTS telegram_data (
    telegram_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    api_id VARCHAR(50) NOT NULL COMMENT 'Шифруется приложением',
    api_hash VARCHAR(100) NOT NULL COMMENT 'Шифруется приложением',
    phone_number VARCHAR(20) NOT NULL COMMENT 'Шифруется приложением',
    session_data TEXT,
    target_username VARCHAR(50),
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_telegram_user ON telegram_data(user_id);

DELIMITER //
CREATE TRIGGER validate_telegram_phone
BEFORE INSERT ON telegram_data
FOR EACH ROW
BEGIN
    IF NEW.phone_number NOT REGEXP '^\\+[0-9]{10,15}$' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid phone number format';
    END IF;
END//
DELIMITER ;

COMMIT;
