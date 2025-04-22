from fastapi import APIRouter, Depends
from services.user_service import UserService

router = APIRouter(prefix="/user", tags=["user"])


@router.post("/send-users-prediction-email")
async def send_users_prediction_email(user_service: UserService = Depends(UserService)):
    return await user_service.send_prediction_notifs()


@router.post("/send-users-game-prediction-email")
async def send_users_game_prediction_email(
    user_service: UserService = Depends(UserService),
):
    return await user_service.send_game_prediction_notifs()
