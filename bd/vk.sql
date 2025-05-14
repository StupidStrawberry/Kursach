-- vk.sql
-- Хранение данных VK API

START TRANSACTION;

CREATE TABLE IF NOT EXISTS vk_data (
    vk_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    access_token VARCHAR(255) NOT NULL COMMENT 'Шифруется приложением',
    target_id VARCHAR(50) NOT NULL,
    token_expires_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_vk_active_tokens ON vk_data(user_id, is_active, token_expires_at);

COMMIT;
