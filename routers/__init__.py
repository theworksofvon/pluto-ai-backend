from .prediction_router import router as prediction_router
from fastapi import APIRouter, Depends
from .odds_router import router as odds_router
from routers.dependecies import protected_route


router = APIRouter(prefix="/api", dependencies=[Depends(protected_route)])
router.include_router(prediction_router, tags=["prediction"])
router.include_router(odds_router, tags=["odds"])
