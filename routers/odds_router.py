from fastapi import APIRouter, Depends, HTTPException
from typing import List
from services.odds_service import OddsService, GameOdds
from logger import logger

router = APIRouter(
    prefix="/odds", tags=["odds"], responses={404: {"description": "Not found"}}
)


def get_odds_service():
    return OddsService()


@router.get("/today/{team}", response_model=List[GameOdds])
async def get_todays_odds(
    team: str,
    sport: str = "basketball_nba",
    service: OddsService = Depends(get_odds_service),
):
    """
    Get today's odds for the specified sport
    """
    try:
        logger.info(f"Getting today's odds for {team} in {sport}")
        return await service.get_todays_odds(sport=sport, team=team)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error fetching odds: {str(e)}")


@router.get("/sports", response_model=List[dict])
async def get_available_sports(service: OddsService = Depends(get_odds_service)):
    """
    Get available sports from the Odds API
    """
    try:
        return await service.get_sports()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error fetching sports: {str(e)}")


@router.get("/prizepicks/{player_name}", response_model=List[dict])
async def get_prizepicks_lines(
    player_name: str, service: OddsService = Depends(get_odds_service)
):
    """
    Get PrizePicks lines for the specified sport
    """
    try:
        return await service.get_prizepicks_lines(player_name)
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Error fetching PrizePicks lines: {str(e)}"
        )
