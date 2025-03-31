from adapters import Adapters
from fastapi import Header, HTTPException, status
from logger import logger


async def protected_route(authorization: str | None = Header(None)):
    """
    Protected route that verifies the static token
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    logger.info(f"Authorizing request...")
    adapters = Adapters()
    is_authenticated = await adapters.auth.authenticate_or_static_token(token=authorization)
    logger.info(f"Authorization result: {is_authenticated}")
    
    if not is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    return {"authenticated": True}
    