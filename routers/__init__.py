from .prediction_router import router as prediction_router
from fastapi import APIRouter, Depends
from .odds_router import router as odds_router
from routers.dependecies import protected_route
from .games import router as games_router
from .players import router as players_router

router = APIRouter(prefix="/v1/api", dependencies=[Depends(protected_route)])
router.include_router(prediction_router, tags=["prediction"])
router.include_router(odds_router, tags=["odds"])
router.include_router(games_router, tags=["games"])
router.include_router(players_router, tags=["players"])
