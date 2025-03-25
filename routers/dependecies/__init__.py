from adapters import Adapters
from fastapi import Header
from logger import logger

async def protected_route(authorization: str | None = Header(None)):
    """
    Protected route that verifies the static token
    """
    adapters = Adapters()
    return adapters.static_auth.verify_static_token(bearer_token=authorization)
