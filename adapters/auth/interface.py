from datetime import timedelta
from fastapi import Header

class AuthInterface:
    """Interface for authentication adapters."""
    def verify_static_token(self, bearer_token: str | None = None) -> None:
        """Verify a static API Key."""
        raise NotImplementedError()

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed one."""
        raise NotImplementedError()

    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        raise NotImplementedError()

    def create_access_token(self, data: dict, expires_delta: timedelta | None = None) -> str:
        """Create a JWT token."""
        raise NotImplementedError()

    def decode_access_token(self, token: str) -> dict | None:
        """Decode a JWT token. Returns the payload or None if invalid."""
        raise NotImplementedError()
    
    async def authenticate_user(self, token: str) -> bool:
        """Authenticate a user with a token."""
        raise NotImplementedError()
    
    async def authenticate_or_static_token(self, token: str) -> bool:
        """Authenticate a user with a token or use a static token."""
        raise NotImplementedError()

