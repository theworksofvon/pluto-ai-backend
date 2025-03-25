from adapters.auth.interface import AuthInterface
from fastapi import HTTPException, status, Header
from config import config
from jose import jwt, JWTError
from logger import logger

class StaticAuthAdapter(AuthInterface):
    """
    A simple authentication adapter that uses a static API Key.
    This adapter does not store or manage user data; it simply
    validates that the incoming token matches the preconfigured static token.
    """
    def __init__(self, algorithm: str = "HS256"):
        self.static_token = config.ACCESS_TOKEN
        self.jwt_secret = config.JWT_SUPABASE_SECRET
        self.jwt_algorithm = algorithm
        
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
            token = self._extract_token(bearer_token)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format"
            )
        if token != self.static_token:
            logger.info(f"Static token not verified...")
            return False
        logger.info(f"Static token verified...")
        return True
            
    async def authenticate_user(self, token: str) -> bool:
        """
        Authenticate a user with a token.
        """
        try:
            logger.info(f"Authenticating user with token...")
            token = self._extract_token(token)
            logger.info(f"Decoding token....")
            jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            logger.info(f"Token decoded...")
            return True
        except JWTError:
            logger.info(f"Token not decoded...")
            return False
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
            
            
            
    async def decode_access_token(self, token: str) -> dict | None:
        """
        Decode an access token.
        """
        try:
            token = self._extract_token(token)
            return jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
        except JWTError:
            return None
        
    async def authenticate_or_static_token(self, token: str) -> bool:
        """
        Authenticate a user with a token or use a static token.
        """
        logger.info(f"Authenticating or using static token...")
        return await self.authenticate_user(token) or self.verify_static_token(bearer_token=token)

    def _extract_token(self, token: str | None = None) -> str:
        """
        Extract the token from the Authorization header.
        """
        if token is None:
            raise ValueError("Authorization header is None")
        parts = token.split(" ")
        # If the header is in the "Bearer <token>" format, return the token part.
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return token