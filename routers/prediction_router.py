from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Optional, Union
from datetime import datetime
from models import PredictionRequest, PredictionValue, PredictionResponse

from agents import PredictionAgent
from services.prediction import PredictionService
from services.data_pipeline import DataProcessor
from logger import logger

router = APIRouter(
    prefix="/predictions",
    tags=["predictions"],
    responses={404: {"description": "Not found"}},
)


def get_prediction_agent() -> PredictionAgent:
    return PredictionAgent()


def get_prediction_service() -> PredictionService:
    return PredictionService()

def get_data_pipeline() -> DataProcessor:
    return DataProcessor()


@router.post(
    "/player/{prediction_type}",
    response_model=PredictionResponse,
)
async def predict_player_performance(
    prediction_type: str = "points",
    data: PredictionRequest = Body(...),
    agent: PredictionAgent = Depends(get_prediction_agent),
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
            game_id=data.game_id,
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
        logger.error(f"Error making prediction: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@router.get("/context/{player_name}")
async def get_prediction_context(
    player_name: str,
    opposing_team: str = Query(..., description="The opposing team name"),
    prediction_type: str = Query(
        "points", description="Type of prediction (points, rebounds, assists)"
    ),
    service: PredictionService = Depends(get_prediction_service),
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
        logger.error(f"Error getting prediction context: {e}")
        raise HTTPException(status_code=500, detail=f"Context error: {str(e)}")

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
