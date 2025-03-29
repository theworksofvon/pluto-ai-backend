from fastapi import APIRouter, Depends
from services.game_service import GameService


def get_game_service():
    return GameService()


router = APIRouter(
    prefix="/games", tags=["games"], responses={404: {"description": "Not found"}}
)


@router.get("/{game_id}")
async def get_game(game_id: str, service: GameService = Depends(get_game_service)):
    return await service.get_game(game_id)


@router.get("/today")
async def get_today_games(service: GameService = Depends(get_game_service)):
    return await service.get_todays_games()
