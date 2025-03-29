from fastapi import APIRouter, Depends, Body
from services.data_pipeline import DataProcessor

router = APIRouter(prefix="/players", tags=["players"])


def get_data_pipeline():
    return DataProcessor()


@router.post("/update-player-stats")
async def update_player_stats(
    players: list[str] = Body(...),
    data_pipeline: DataProcessor = Depends(get_data_pipeline),
):
    await data_pipeline.update_player_stats(players=players)
    return {"message": "Player stats updated"}
