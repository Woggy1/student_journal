-- Створення таблиці груп 
CREATE TABLE IF NOT EXISTS `group` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- Створення таблиці користувачів 
CREATE TABLE IF NOT EXISTS `user` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'teacher') NOT NULL,
    group_id INT,
    FOREIGN KEY (group_id) REFERENCES `group`(id)
);


-- Створення таблиці предметів
CREATE TABLE IF NOT EXISTS subject (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    teacher_id INT NOT NULL,
    group_id INT NOT NULL,
    FOREIGN KEY (teacher_id) REFERENCES user(id),
    FOREIGN KEY (group_id) REFERENCES `group`(id)
);

-- Створення таблиці оцінок
CREATE TABLE IF NOT EXISTS grade (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    subject_id INT NOT NULL,
    grade INT NOT NULL,
    comment TEXT,
    date DATE NOT NULL,
    FOREIGN KEY (student_id) REFERENCES user(id),
    FOREIGN KEY (subject_id) REFERENCES subject(id)
);

CREATE TABLE IF NOT EXISTS study_material (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    file_path VARCHAR(300),
    subject_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subject(id)
);