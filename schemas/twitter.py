
from typing import Optional
from pydantic import BaseModel


class TweetSchema(BaseModel):
    message: str
    media_url: Optional[str] = None