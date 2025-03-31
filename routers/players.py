from fastapi import APIRouter, Depends, Body, Path, Query
from adapters import Adapters
from services.data_pipeline import DataProcessor
from services.player_service import PlayerService
from typing import Optional
from datetime import datetime


router = APIRouter(prefix="/players", tags=["players"])


def get_data_pipeline():
    return DataProcessor()


def get_player_service():
    return PlayerService()


def get_adapters():
    return Adapters()


@router.post("/update-player-stats")
async def update_player_stats(
    players: list[str] = Body(...),
    data_pipeline: DataProcessor = Depends(get_data_pipeline),
):
    await data_pipeline.update_player_stats(players=players, current=False)
    return {"message": "Player stats updated"}


@router.get("/get-player-image")
async def get_player_image(
    player_name: str = Body(...),
    adapters: Adapters = Depends(get_adapters),
):
    return await adapters.nba_analytics.get_player_image(player_name=player_name)


@router.get("/player-predictions")
async def get_player_predictions(
    player_names: Optional[list[str]] = Query(
        None, description="List of player names to get predictions for"
    ),
    game_date: Optional[str] = Query(
        None,
        description="The game date to get predictions for (YYYY-MM-DD), defaults to today",
    ),
    prediction_type: Optional[str] = Query(
        "points", description="The type of prediction to get"
    ),
    service: PlayerService = Depends(get_player_service),
):
    """
    Get player predictions either by player names or by game date.
    If both are provided, game_date takes precedence.
    """
    if game_date:
        return await service.get_formatted_predictions_by_date(
            game_date, prediction_type
        )
    elif player_names:
        return await service.get_formatted_predictions_by_players(
            player_names, prediction_type
        )
    else:
        return {"error": "Either player_names or game_date must be provided"}
