-- Drop old tables if they exist
DROP TABLE IF EXISTS player_predictions;
DROP TABLE IF EXISTS game_predictions;
DROP TABLE IF EXISTS players;
DROP TABLE IF EXISTS games;
DROP TABLE IF EXISTS teams;

-- Create new table for game predictions
CREATE TABLE game_predictions (
    prediction_id SERIAL PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team VARCHAR NOT NULL,
    away_team VARCHAR NOT NULL,
    predicted_winner VARCHAR NOT NULL,
    home_team_win_percentage FLOAT NOT NULL,
    opposing_team_win_percentage FLOAT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create new table for player predictions
CREATE TABLE player_predictions (
    prediction_id SERIAL PRIMARY KEY,
    game_date DATE NOT NULL,
    player_name VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    opposing_team VARCHAR NOT NULL,
    prediction_type VARCHAR NOT NULL,
    predicted_value FLOAT NOT NULL,
    range_low FLOAT,
    range_high FLOAT,
    confidence FLOAT,
    explanation VARCHAR,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);