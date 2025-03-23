from typing import Optional
import aiohttp
from pydantic import BaseModel, Field
from agency.tools import BaseTool, ToolResult
from requests_oauthlib import OAuth1
from requests import Request


class TwitterPostParams(BaseModel):
    message: str = Field(
        ..., description="The message to post on Twitter", max_length=280
    )
    media_url: Optional[str] = Field(
        None, description="Optional URL to media to attach to the tweet"
    )


class TwitterTool(BaseTool):
    def __init__(
        self,
        name: str,
        description: str,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str,
    ):
        super().__init__(name, description)
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.api_base = "https://api.twitter.com/2"

        self.parameters = {
            "message": {
                "type": "string",
                "description": "The message to post on Twitter",
                "required": True,
                "max_length": 280,
            },
            "media_url": {
                "type": "string",
                "description": "Optional URL to media to attach to the tweet",
                "required": False,
            },
        }

    def _generate_signed_headers(self, method: str, url: str, payload: dict) -> dict:
        """
        Generate OAuth1 signed headers for a request.

        :param method: HTTP method (e.g., 'POST')
        :param url: Full API endpoint URL
        :param payload: JSON payload for the request
        :return: Dictionary of signed headers
        """
        # OAuth1 object for signing
        oauth = OAuth1(
            self.api_key, self.api_secret, self.access_token, self.access_token_secret
        )

        # Prepare the request and sign it
        req = Request(method, url, json=payload, auth=oauth)
        prepared = req.prepare()

        # Extract signed headers
        return prepared.headers

    def validate_input(self, message: str, media_url: Optional[str] = None) -> bool:
        try:
            TwitterPostParams(message=message, media_url=media_url)
            return True
        except Exception:
            return False

    async def execute(
        self, message: str, media_url: Optional[str] = None
    ) -> ToolResult:
        """
        Post a tweet using the Twitter API.

        :param message: Text of the tweet
        :param media_url: Optional URL to attach media
        :return: ToolResult containing success status and response data
        """
        try:
            params = TwitterPostParams(message=message, media_url=media_url)
            url = f"{self.api_base}/tweets"
            payload = {"text": params.message}

            # Get signed headers
            headers = self._generate_signed_headers("POST", url, payload)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url=url, headers=headers, json=payload
                ) as response:
                    if response.status == 201:
                        data = await response.json()
                        return ToolResult(
                            success=True,
                            data={
                                "tweet_id": data["data"]["id"],
                                "text": data["data"]["text"],
                            },
                            metadata={"created_at": data["data"].get("created_at")},
                        )
                    else:
                        error_data = await response.json()
                        return ToolResult(
                            success=False, data=None, error=str(error_data)
                        )

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
