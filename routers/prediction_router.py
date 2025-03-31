from fastapi import APIRouter, HTTPException, Depends, Query, Body, status
from typing import Optional, Union
from datetime import datetime

from models import PredictionRequest, PredictionValue, PredictionResponse, GamePredictionRequest, GamePredictionValue, GamePredictionResponse
from agents import PlayerPredictionAgent, GamePredictionAgent
from services.player_prediction import PlayerPredictionService
from services.game_prediction import GamePredictionService
from services.data_pipeline import DataProcessor

from logger import logger

router = APIRouter(
    prefix="/predictions",
    tags=["predictions"],
    responses={404: {"description": "Not found"}},
)



def get_player_prediction_agent() -> PlayerPredictionAgent:
    return PlayerPredictionAgent()

def get_player_prediction_service() -> PlayerPredictionService:
    return PlayerPredictionService()

def get_game_prediction_agent() -> GamePredictionAgent:
    return GamePredictionAgent()

def get_data_pipeline() -> DataProcessor:
    return DataProcessor()


@router.post(
    "/player/{prediction_type}/{prediction_version}",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
)
async def predict_player_performance(
    prediction_type: str = "points",
    prediction_version: str = "v1",
    data: PredictionRequest = Body(...),
    agent: PlayerPredictionAgent = Depends(get_player_prediction_agent),
):
    """
    Predict a player's performance for an upcoming game.

    Accepts player name, opposing team, and prediction type (points/rebounds/assists).

    Returns a prediction with confidence interval and explanation.
    """
    logger.info(
        f"Prediction request received for {data.player_name} vs {data.opposing_team}"
    )

    try:
        prediction_data = await agent.predict_player_performance(
            player_name=data.player_name,
            opposing_team=data.opposing_team,
            prediction_type=prediction_type,
            team=data.team,
            game_id=data.game_id,
            prediction_version=prediction_version,
        )

        if prediction_data.get("status") == "error":
            return PredictionResponse(
                status="error",
                player=data.player_name,
                prediction_type=prediction_type,
                opposing_team=data.opposing_team,
                timestamp=datetime.now(),
                message=prediction_data.get("message", "Prediction failed"),
            )

        prediction_value = PredictionValue(
            value=prediction_data["prediction"]["value"],
            range_low=prediction_data["prediction"]["range_low"],
            range_high=prediction_data["prediction"]["range_high"],
            confidence=prediction_data["prediction"]["confidence"],
            explanation=prediction_data["prediction"]["explanation"],
        )

        return PredictionResponse(
            status="success",
            player=data.player_name,
            prediction_type=data.prediction_type,
            opposing_team=data.opposing_team,
            timestamp=datetime.now(),
            prediction=prediction_value,
        )

    except Exception as e:
        logger.error(f"Error making player prediction: {e}")
        raise HTTPException(status_code=500, detail=f"Player prediction error: {str(e)}")


@router.get("/context/{player_name}")
async def get_player_prediction_context(
    player_name: str,
    opposing_team: str = Query(..., description="The opposing team name"),
    prediction_type: str = Query(
        "points", description="Type of prediction (points, rebounds, assists)"
    ),
    service: PlayerPredictionService = Depends(get_player_prediction_service),
):
    """
    Get the raw prediction context for a player.

    This is useful for debugging or for clients that want to use the raw data
    to make their own predictions or visualizations.
    """
    logger.info(f"Context request received for {player_name} vs {opposing_team}")

    try:
        context = await service.prepare_prediction_context(
            player_name=player_name,
            opposing_team=opposing_team,
            prediction_type=prediction_type,
        )

        return context
    except Exception as e:
        logger.error(f"Error getting player prediction context: {e}")
        raise HTTPException(status_code=500, detail=f"Player context error: {str(e)}")


# --- Game Prediction Routes ---

@router.post(
    "/game/winner/{prediction_version}",
    response_model=GamePredictionResponse,
    status_code=status.HTTP_200_OK,
)
async def predict_game_winner(
    prediction_version: str = "v2",
    data: GamePredictionRequest = Body(...),
    agent: GamePredictionAgent = Depends(get_game_prediction_agent),
):
    """
    Predict the winner of an upcoming NBA game.

    Accepts home and away team abbreviations.

    Returns the predicted winner, confidence, win percentages, and explanation.
    """
    logger.info(
        f"Game winner prediction request received for {data.home_team_abbr} vs {data.away_team_abbr}"
    )

    try:
        agent_result = await agent.predict_game_winner(
            home_team_abbr=data.home_team_abbr,
            away_team_abbr=data.away_team_abbr,
            game_id=data.game_id,
            prediction_version=prediction_version,
        )

        if agent_result.get("status") != "success":
            logger.error(f"Agent returned error: {agent_result.get('message')}")
            return GamePredictionResponse(
                status="error",
                game=agent_result.get("game"),
                message=agent_result.get("message", "Prediction failed internally."),
            )

        raw_prediction = agent_result.get("prediction", {})
        
        prediction_value = GamePredictionValue(
            value=raw_prediction.get("value"),
            confidence=raw_prediction.get("confidence"),
            home_team_win_percentage=raw_prediction.get("home_team_win_percentage"),
            opposing_team_win_percentage=raw_prediction.get("opposing_team_win_percentage"),
            explanation=raw_prediction.get("explanation"),
        )

        return GamePredictionResponse(
            status="success",
            game=agent_result.get("game"),
            prediction=prediction_value,
            context_summary=agent_result.get("context_summary"),
        )

    except Exception as e:
        logger.exception(f"Error making game winner prediction: {e}")
        raise HTTPException(status_code=500, detail=f"Game prediction error: {str(e)}")


@router.get("/update-pluto-dataset")
async def update_pluto_dataset(
    service: DataProcessor = Depends(get_data_pipeline),
):
    """
    Update the Pluto dataset with new data.
    """
    try:
        await service.update_player_stats()
        return {"message": "Pluto dataset updated successfully"}
    except Exception as e:
        logger.error(f"Error updating Pluto dataset: {e}")
        raise HTTPException(status_code=500, detail=f"Dataset update error: {str(e)}")
