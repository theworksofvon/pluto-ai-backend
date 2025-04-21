from fastapi import APIRouter, Depends
from adapters import Adapters
from routers.helpers.helpers import get_adapters

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{team_name}")
async def get_team_info(team_name: str, adapters: Adapters = Depends(get_adapters)):
    return await adapters.nba_analytics.get_team_info(team_name)


@router.get("/")
async def get_teams(adapters: Adapters = Depends(get_adapters)):
    return adapters.nba_analytics.get_teams()


@router.get("/game-winner/{home_team}/{away_team}/{game_date}")
async def get_game_winner(
    home_team: str,
    away_team: str,
    game_date: str,
    adapters: Adapters = Depends(get_adapters),
):
    return await adapters.nba_analytics.get_game_winner(
        game_date=game_date, home_team=home_team, away_team=away_team
    )
