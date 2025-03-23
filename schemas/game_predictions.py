from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


# Team Models
class TeamCreate(BaseModel):
    name: str


class TeamRead(BaseModel):
    team_id: int
    name: str

    class Config:
        orm_mode = True


# Player Models
class PlayerCreate(BaseModel):
    name: str
    team_id: int


class PlayerRead(BaseModel):
    player_id: int
    name: str
    team_id: int

    class Config:
        orm_mode = True


class GameCreate(BaseModel):
    date: date
    home_team_id: int
    away_team_id: int


class GameRead(BaseModel):
    game_id: int
    date: date
    home_team_id: int
    away_team_id: int
    winner_team_id: Optional[int]

    class Config:
        orm_mode = True


class GamePredictionCreate(BaseModel):
    game_id: int
    predicted_winner_team_id: int
    home_team_win_percentage: float
    opposing_team_win_percentage: float


class GamePredictionRead(BaseModel):
    prediction_id: int
    game_id: int
    predicted_winner_team_id: int
    home_team_win_percentage: float
    opposing_team_win_percentage: float
    timestamp: datetime

    class Config:
        orm_mode = True

class PlayerPredictionCreate(BaseModel):
    prediction_id: int
    player_id: int
    predicted_points: float 
    predicted_assists: float | None = None
    predicted_rebounds: float | None = None


class PlayerPredictionRead(BaseModel):
    prediction_id: int
    player_id: int
    predicted_points: float
    predicted_assists: float | None = None
    predicted_rebounds: float | None = None

    class Config:
        orm_mode = True


class TeamReadWithPlayers(TeamRead):
    players: List[PlayerRead]


class GameReadWithTeams(BaseModel):
    game_id: int
    date: date
    home_team: TeamRead
    away_team: TeamRead
    winner_team: Optional[TeamRead]

    class Config:
        orm_mode = True