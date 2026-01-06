-- Tạo CSDL
CREATE DATABASE IF NOT EXISTS exam_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE exam_system;

-- Bảng đơn vị
CREATE TABLE units (
    unit_id INT AUTO_INCREMENT PRIMARY KEY,
    unit_name VARCHAR(255) NOT NULL UNIQUE,
    parent_id INT NULL,
    FOREIGN KEY (parent_id) REFERENCES units(unit_id) ON DELETE CASCADE
);

-- Bảng thành viên quản trị
CREATE TABLE IF NOT EXISTS admin_users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(100) NOT NULL UNIQUE,
  password_hash VARCHAR(512) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  role VARCHAR(50) NOT NULL DEFAULT 'user',
  unit_id INT NULL,
  status ENUM('active', 'locked') NOT NULL DEFAULT 'active',
  FOREIGN KEY (unit_id) REFERENCES units(unit_id) ON DELETE SET NULL
);

-- Tạo tài khoản mẫu: admin / Admin@395!
INSERT INTO admin_users (username, password_hash, role) VALUES
('admin_n', 'pbkdf2:sha256:1000000$geMDqhELbto9kjLK$49679762a88ea35c07fb20abebfae0b391596202f9269e37e39383c35b9bc2bf', 'superadmin');
-- Admin@395!

-- Bảng cuộc thi
CREATE TABLE competitions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    created_by INT NOT NULL,
    unit_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES admin_users(id),
    FOREIGN KEY (unit_id) REFERENCES units(unit_id)
);

-- Bảng đề thi
CREATE TABLE exams (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    duration_minutes INT DEFAULT 30,
    competition_id INT,
    FOREIGN KEY (competition_id) REFERENCES competitions(id)
);

-- Bảng môn thi
CREATE TABLE subjects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subject_name VARCHAR(255) NOT NULL,
    created_by INT,
    FOREIGN KEY (created_by) REFERENCES admin_users(id) ON DELETE SET NULL
);

-- Bảng câu hỏi
CREATE TABLE questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    content TEXT NOT NULL,
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    correct_option CHAR(1),
    created_by INT NULL,
    subject_id INT NULL,
    FOREIGN KEY (created_by) REFERENCES admin_users(id) ON DELETE SET NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
);

-- Bảng thí sinh
-- CREATE TABLE candidates (
--     id INT AUTO_INCREMENT PRIMARY KEY,
--     name VARCHAR(100),
--     rank VARCHAR(50),
--     position VARCHAR(50),
--     unit_id INT,
--     FOREIGN KEY (unit_id) REFERENCES units(unit_id) ON DELETE SET NULL
-- );
-- Bảng thí sinh
CREATE TABLE candidates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    `rank` VARCHAR(50),
    position VARCHAR(100),
    unit VARCHAR(255),
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    competition_id INT NOT NULL,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_version INT DEFAULT 1,
    FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES admin_users(id)
);

-- Bảng liên kết đề thi - câu hỏi
CREATE TABLE exam_questions (
    exam_id INT,
    question_id INT,
    score FLOAT NOT NULL DEFAULT 1,
    PRIMARY KEY (exam_id, question_id),
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

-- Bảng lưu kết quả bài làm
CREATE TABLE submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id INT,
    exam_id INT,
    submitted_at DATETIME,
    score FLOAT,
    competition_id INT,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    foreign key (competition_id) references competitions(id) on delete cascade
);
-- Thêm ràng buộc để một thí sinh chỉ làm đề thi một lần
ALTER TABLE submissions
ADD CONSTRAINT rangbuoc UNIQUE (candidate_id, exam_id);

-- Dữ liệu mẫu
INSERT INTO questions (content, option_a, option_b, option_c, option_d, correct_option) VALUES
('Thủ đô của Việt Nam là?', 'Hồ Chí Minh', 'Đà Nẵng', 'Hà Nội', 'Huế', 'C'),
('2 + 2 bằng mấy?', '3', '4', '5', '6', 'B'),
('Màu của lá cây là?', 'Đỏ', 'Xanh', 'Vàng', 'Đen', 'B');

-- Tạo đề thi mẫu và gán 3 câu hỏi vào đề thi ID = 1
INSERT INTO exams (title) VALUES ('Đề thi mẫu');

INSERT INTO exam_questions (exam_id, question_id) VALUES
(1, 1),
(1, 2),
(1, 3);

-- Thêm bảng submisstion_answers để lưu chi tiết bài làm của mỗi thí sinh
CREATE TABLE submission_answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    submission_id INT NOT NULL,
    question_id INT NOT NULL,
    selected_option VARCHAR(1),
    is_correct BOOLEAN,
    score_earned FLOAT,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

-- Bảng liên kết thí sinh - đê thi
CREATE TABLE exam_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    competition_id INT NOT NULL,
    exam_id INT NOT NULL,
    candidate_id INT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_ea_contest
        FOREIGN KEY (competition_id)
        REFERENCES competitions(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_ea_exam
        FOREIGN KEY (exam_id)
        REFERENCES exams(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_ea_candidate
        FOREIGN KEY (candidate_id)
        REFERENCES candidates(id)
        ON DELETE CASCADE
);
-- thêm ràng buộc 1 thí sinh - 1 đề
ALTER TABLE exam_assignments
ADD UNIQUE KEY uq_candidate_contest (exam_id, candidate_id);