from fastapi import APIRouter, Depends
from adapters import Adapters

router = APIRouter(prefix="/teams", tags=["teams"])


def get_adapters():
    return Adapters()


@router.get("/{team_name}")
async def get_team_info(team_name: str, adapters: Adapters = Depends(get_adapters)):
    return await adapters.nba_analytics.get_team_info(team_name)
