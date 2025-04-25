from fastapi import APIRouter, HTTPException, Depends, Query, Body, status
from typing import List, Dict, Any, Literal
from datetime import datetime

from models import (
    PredictionRequest,
    PredictionValue,
    PredictionResponse,
    GamePredictionRequest,
    GamePredictionValue,
    GamePredictionResponse,
    PromptPlutoRequest,
)
from agents import PlayerPredictionAgent, GamePredictionAgent
from services.game_service import GameService
from services.data_pipeline import DataProcessor
from services.eval_service import EvaluationService
from routers.helpers.helpers import (
    get_player_prediction_agent,
    get_game_prediction_agent,
    get_game_service,
    get_data_pipeline,
    get_evaluation_service,
    get_adapters,
)

from logger import logger

router = APIRouter(
    prefix="/predictions",
    tags=["predictions"],
    responses={404: {"description": "Not found"}},
)


@router.post("/all-predictions")
async def get_all_predictions(
    agent: PlayerPredictionAgent = Depends(get_player_prediction_agent),
):
    return await agent._run_daily_predictions()


@router.post("/all-game-predictions")
async def get_all_game_predictions(
    agent: GamePredictionAgent = Depends(get_game_prediction_agent),
):
    return await agent._run_daily_predictions()


@router.post(
    "/player/{prediction_type}",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
)
async def predict_player_performance(
    prediction_type: str = "points",
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
            prizepicks_line=data.prizepicks_line,
            season_mode=data.season_mode,
        )

        if prediction_data.status == "error":
            return PredictionResponse(
                status="error",
                player=data.player_name,
                prediction_type=prediction_type,
                opposing_team=data.opposing_team,
                timestamp=datetime.now(),
                message="Prediction failed",
            )

        prediction_value = PredictionValue(
            value=prediction_data.prediction.value,
            range_low=prediction_data.prediction.range_low,
            range_high=prediction_data.prediction.range_high,
            confidence=prediction_data.prediction.confidence,
            explanation=prediction_data.prediction.explanation,
            prizepicks_line=prediction_data.prediction.prizepicks_line,
            prizepicks_reason=prediction_data.prediction.prizepicks_reason,
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
        raise HTTPException(
            status_code=500, detail=f"Player prediction error: {str(e)}"
        )


@router.post(
    "/game/winner",
    response_model=GamePredictionResponse,
    status_code=status.HTTP_200_OK,
)
async def predict_game_winner(
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
            additional_context=data.additional_context,
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
            opposing_team_win_percentage=raw_prediction.get(
                "opposing_team_win_percentage"
            ),
            explanation=raw_prediction.get("explanation"),
            additional_context=raw_prediction.get("additional_context"),
        )

        return GamePredictionResponse(
            status="success",
            game=agent_result.get("game"),
            prediction=prediction_value,
        )

    except Exception as e:
        logger.exception(f"Error making game winner prediction: {e}")
        raise HTTPException(status_code=500, detail=f"Game prediction error: {str(e)}")


@router.get(
    "/game/winner", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK
)
async def get_formatted_game_predictions(
    game_date: str = Query(..., description="Date in YYYY-MM-DD format"),
    service: GameService = Depends(get_game_service),
):
    """
    Get all game predictions for a specific date, formatted for the frontend.
    """
    try:
        datetime.strptime(game_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD."
        )

    try:
        predictions = await service.get_formatted_game_predictions_by_date(game_date)
        return predictions
    except Exception as e:
        logger.exception(
            f"Error getting formatted game predictions for date {game_date}: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Error retrieving formatted game predictions."
        )


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


@router.get("/evaluate-predictions/{prediction_type}")
async def evaluate_predictions(
    prediction_type: str = "points",
    service: EvaluationService = Depends(get_evaluation_service),
):
    """
    Evaluate all predictions in the database.
    """
    try:
        if prediction_type == "points":
            return await service.evaluate_points_predictions()
        elif prediction_type == "rebounds":
            return await service.evaluate_rebounds_predictions()
        elif prediction_type == "assists":
            return await service.evaluate_assists_predictions()
        else:
            raise HTTPException(status_code=400, detail="Invalid prediction type")
    except Exception as e:
        logger.error(f"Error evaluating predictions: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation error: {str(e)}")


@router.get("/evaluate-game-predictions")
async def evaluate_game_predictions(
    service: EvaluationService = Depends(get_evaluation_service),
):
    """
    Evaluate all game predictions in the database.
    """
    return await service.evaluate_game_predictions()


@router.get("/fill-actual-values")
async def fill_actual_values(
    service: EvaluationService = Depends(get_evaluation_service),
):
    try:
        return await service.get_and_fill_actual_values()
    except Exception as e:
        logger.error(f"Error filling actual values: {e}")
        raise HTTPException(
            status_code=500, detail=f"Fill actual values error: {str(e)}"
        )


@router.get("/get-evaluation-metrics")
async def get_evaluation_metrics(
    timeframe: Literal["7_days", "14_days", "30_days", "all_time"] = "7_days",
    prediction_type: str = "points",
    service: EvaluationService = Depends(get_evaluation_service),
):
    return await service.get_prediction_metrics_by_timeframe(
        timeframe=timeframe, prediction_type=prediction_type
    )


@router.get("/get-key-metrics")
async def get_key_metrics(
    timeframe: Literal["7_days", "14_days", "30_days", "all_time"] = "7_days",
    service: EvaluationService = Depends(get_evaluation_service),
):
    """
    Get key dashboard metrics with change values from previous period.

    Returns formatted metrics matching the frontend dashboard requirements.
    """
    return await service.get_key_metrics(timeframe=timeframe)


@router.post("/prompt-pluto")
async def prompt_pluto(
    data: PromptPlutoRequest = Body(...),
    agent: PlayerPredictionAgent = Depends(get_player_prediction_agent),
):
    """
    Prompt Pluto any question.
    """
    logger.info(f"Prompt Pluto request received: {data.prompt}")
    return await agent.prompt(data.prompt)
