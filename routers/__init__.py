from .prediction_router import router as prediction_router
from fastapi import APIRouter
from .odds_router import router as odds_router


router = APIRouter(prefix="/api")
router.include_router(prediction_router, tags=["prediction"])
router.include_router(odds_router, tags=["odds"])
