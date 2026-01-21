create database health;
use health;


CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    phone VARCHAR(100),
    address VARCHAR(255),
    gender VARCHAR(10),
    profile_picture VARCHAR(255),
    password VARCHAR(255),
    status VARCHAR(255)
);



CREATE TABLE friend_requests (
    friend_requests_id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT,
    receiver_id INT,
    status VARCHAR(20),
    FOREIGN KEY (sender_id) REFERENCES users(user_id),
    FOREIGN KEY (receiver_id) REFERENCES users(user_id)
);


CREATE TABLE post (
    post_id INT AUTO_INCREMENT PRIMARY KEY,
    image VARCHAR(255),
    audio VARCHAR(255),
    video VARCHAR(255),
    description TEXT,
    privacy_type ENUM('public', 'private') NOT NULL,
    user_id INT,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);


CREATE TABLE comment (
    comment_id INT AUTO_INCREMENT PRIMARY KEY,
    comment TEXT,
    user_id INT,
    post_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (post_id) REFERENCES post(post_id)
);


CREATE TABLE likes (
    like_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    post_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (post_id) REFERENCES post(post_id)
);


CREATE TABLE share (
    share_id INT AUTO_INCREMENT PRIMARY KEY,
    shared_by_user_id INT,
    shared_to_user_id INT,
    post_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shared_by_user_id) REFERENCES users(user_id),
    FOREIGN KEY (shared_to_user_id) REFERENCES users(user_id),
    FOREIGN KEY (post_id) REFERENCES post(post_id)
);


CREATE TABLE chat (
    chat_id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT,
    receiver_id INT,
    message TEXT,
    isSenderRead ENUM('read', 'unread') DEFAULT 'unread',
    isReceiverRead ENUM('read', 'unread') DEFAULT 'unread',
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users(user_id),
    FOREIGN KEY (receiver_id) REFERENCES users(user_id)
);


