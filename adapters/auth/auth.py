from adapters.auth.interface import AuthInterface
from fastapi import HTTPException, status, Header
from config import config

class StaticAuthAdapter(AuthInterface):
    """
    A simple authentication adapter that uses a static API Key.
    This adapter does not store or manage user data; it simply
    validates that the incoming token matches the preconfigured static token.
    """
    def __init__(self):
        self.static_token = config.ACCESS_TOKEN
        
    def verify_static_token(self, bearer_token: str | None = None) -> None:
        """
        Checks that the request includes a valid token in the Authorization header.
        Expects header in format: "Bearer <token>"
        """
        if not bearer_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header"
            )
        try:
            scheme, token = bearer_token.split()   
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format"
            )
        if scheme.lower() != "bearer" or token != self.static_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )