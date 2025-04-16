from fastapi import APIRouter, Depends
from adapters import Adapters
from routers.helpers.helpers import get_adapters

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{team_name}")
async def get_team_info(team_name: str, adapters: Adapters = Depends(get_adapters)):
    return await adapters.nba_analytics.get_team_info(team_name)
