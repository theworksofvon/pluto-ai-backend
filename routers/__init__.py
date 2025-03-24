from .prediction_router import router as prediction_router
from fastapi import APIRouter, Depends
from .odds_router import router as odds_router
from adapters import Adapters

def get_static_auth():
    return Adapters().static_auth


router = APIRouter(prefix="/api", dependencies=[Depends(get_static_auth().verify_static_token)])
router.include_router(prediction_router, tags=["prediction"])
router.include_router(odds_router, tags=["odds"])
