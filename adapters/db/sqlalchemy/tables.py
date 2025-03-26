from sqlalchemy import Column, Integer, String, ForeignKey, Date, DateTime, Float
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class Team(Base):
    __tablename__ = "teams"
    team_id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    players = relationship(
        "Player", back_populates="team", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Team(name={self.name})>"


class Player(Base):
    __tablename__ = "players"
    player_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    team = relationship("Team", back_populates="players")

    def __repr__(self):
        return f"<Player(name={self.name})>"


class Game(Base):
    __tablename__ = "games"
    game_id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    winner_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    winner_team = relationship("Team", foreign_keys=[winner_team_id])

    def __repr__(self):
        return f"<Game(id={self.game_id}, date={self.date})>"


class PlayerPrediction(Base):
    """
    Model for an individual player's prediction in a game.
    Each record represents a prediction for a specific player's stat(s)
    in a specific game.
    """

    __tablename__ = "player_predictions"
    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.player_id"), nullable=False)
    predicted_points = Column(Float, nullable=False)
    predicted_assists = Column(Float, nullable=True)
    predicted_rebounds = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    value = Column(Float, nullable=True)
    range_low = Column(Float, nullable=True)
    range_high = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    explanation = Column(String, nullable=True)

    game = relationship("Game")
    player = relationship("Player")

    def __repr__(self):
        return (
            f"<PlayerPrediction(prediction_id={self.prediction_id}, game_id={self.game_id}, "
            f"player_id={self.player_id}, predicted_points={self.predicted_points})>"
        )


class GamePrediction(Base):
    """
    Model for predicting the outcome of a game.
    This prediction focuses on the overall game outcome (i.e. the winning team)
    and includes win percentage estimates for both the home team and the opposing team.
    """

    __tablename__ = "game_predictions"
    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    home_team_win_percentage = Column(Float, nullable=False)
    opposing_team_win_percentage = Column(Float, nullable=False)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    predicted_winner_team_id = Column(
        Integer, ForeignKey("teams.team_id"), nullable=False
    )
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    game = relationship("Game")
    predicted_winner_team = relationship(
        "Team", foreign_keys=[predicted_winner_team_id]
    )

    def __repr__(self):
        return (
            f"<GamePrediction(prediction_id={self.prediction_id}, game_id={self.game_id}, "
            f"predicted_winner_team_id={self.predicted_winner_team_id}, "
            f"home_team_win_percentage={self.home_team_win_percentage}, "
            f"opposing_team_win_percentage={self.opposing_team_win_percentage})>"
        )
