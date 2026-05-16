-- Game leaderboard database schema

CREATE TABLE users (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    email       VARCHAR(255) NOT NULL UNIQUE,
    name        VARCHAR(100) NOT NULL,
    password    VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE players (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id      BIGINT NOT NULL,
    display_name VARCHAR(50) NOT NULL,
    score        INT NOT NULL DEFAULT 0,
    rank         ENUM('bronze','silver','gold','platinum') DEFAULT 'bronze',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_players_score ON players (score DESC);

CREATE INDEX idx_users_email ON users (email);

CREATE VIEW leaderboard AS
    SELECT p.id, p.display_name, p.score, p.rank, u.email
    FROM players p
    JOIN users u ON u.id = p.user_id
    ORDER BY p.score DESC;

ALTER TABLE players ADD COLUMN wins   INT NOT NULL DEFAULT 0;

ALTER TABLE players ADD COLUMN losses INT NOT NULL DEFAULT 0;

CREATE TABLE match_history (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    winner_id   BIGINT NOT NULL,
    loser_id    BIGINT NOT NULL,
    score_delta INT NOT NULL,
    played_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (winner_id) REFERENCES players(id),
    FOREIGN KEY (loser_id)  REFERENCES players(id)
);

DROP TABLE IF EXISTS legacy_scores;

CREATE OR REPLACE VIEW player_stats AS
    SELECT p.id, p.display_name, p.score, p.wins, p.losses,
           ROUND(p.wins * 100.0 / NULLIF(p.wins + p.losses, 0), 2) AS win_rate
    FROM players p;
