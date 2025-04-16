from fastapi import APIRouter, Depends, Body, Path, Query, HTTPException
from adapters import Adapters
from services.data_pipeline import DataProcessor
from services.player_service import PlayerService
from typing import Optional, List
from models.prediction_models import FormattedPrediction
from routers.helpers.helpers import (
    get_data_pipeline,
    get_player_service,
    get_adapters,
)


router = APIRouter(prefix="/players", tags=["players"])


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
) -> List[FormattedPrediction]:
    """
    Get player predictions either by player names or by game date.
    If both are provided, game_date takes precedence.
    """
    if game_date:
        return await service.get_formatted_predictions_by_date(
            game_date=game_date, prediction_type=prediction_type
        )
    elif player_names:
        return await service.get_formatted_predictions_by_players(
            player_names=player_names, prediction_type=prediction_type
        )
    else:
        raise HTTPException(
            status_code=400, detail="Either player_names or game_date must be provided"
        )
