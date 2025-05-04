from typing import Optional
import aiohttp
from pydantic import BaseModel, Field, PrivateAttr
from agency.tools import BaseTool, ToolResult
from requests_oauthlib import OAuth1
from requests import Request
import os
from logger import logger


class TwitterPostParams(BaseModel):
    message: str = Field(
        ..., description="The message to post on Twitter", max_length=280
    )
    media_url: Optional[str] = Field(
        None, description="Optional URL to media to attach to the tweet"
    )


class TwitterTool(BaseTool):
    _api_key: str = PrivateAttr()
    _api_secret: str = PrivateAttr()
    _access_token: str = PrivateAttr()
    _access_token_secret: str = PrivateAttr()
    _api_base: str = PrivateAttr()
    _client_secret: str = PrivateAttr()
    _client_id: str = PrivateAttr()

    def __init__(
        self,
        name: str = "Twitter Tool",
        description: str = "A tool for posting and reading tweets to Twitter",
        api_key: str = os.getenv("TWITTER_API_KEY"),
        api_secret: str = os.getenv("TWITTER_API_SECRET"),
        access_token: str = os.getenv("TWITTER_ACCESS_TOKEN"),
        access_token_secret: str = os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
        client_secret: str = os.getenv("TWITTER_CLIENT_SECRET"),
        client_id: str = os.getenv("TWITTER_CLIENT_ID"),
    ):
        super().__init__(name=name, description=description)
        self._api_key = api_key
        self._api_secret = api_secret
        self._access_token = access_token
        self._access_token_secret = access_token_secret
        self._api_base = "https://api.twitter.com/2"
        self._client_secret = client_secret
        self._client_id = client_id

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

    def _generate_signed_headers(
        self, method: str, url: str, payload: dict = None, params: dict = None
    ) -> dict:
        """
        Generate OAuth1 signed headers for a request.

        :param method: HTTP method (e.g., 'POST' or 'GET')
        :param url: Full API endpoint URL
        :param payload: JSON payload for non-GET requests
        :param params: Query parameters for GET requests
        :return: Dictionary of signed headers
        """
        # OAuth1 object for signing
        oauth = OAuth1(
            self._api_key,
            self._api_secret,
            self._access_token,
            self._access_token_secret,
        )

        if method.upper() == "GET":
            req = Request(method, url, params=params, auth=oauth)
        else:
            req = Request(method, url, json=payload, auth=oauth)

        prepared = req.prepare()

        # Convert headers to a dict with string keys/values in case any are bytes
        headers = {
            (k.decode("utf-8") if isinstance(k, bytes) else k): (
                v.decode("utf-8") if isinstance(v, bytes) else v
            )
            for k, v in prepared.headers.items()
        }
        return headers

    def validate_input(self, message: str, media_url: Optional[str] = None) -> bool:
        try:
            TwitterPostParams(message=message, media_url=media_url)
            return True
        except Exception as e:
            logger.error(f"Error validating input: {e}")
            return False

    async def read_tweets(self, user_id: str, max_results: int = 5) -> ToolResult:
        """Read tweets from a user's timeline using the Twitter API."""
        try:
            url = f"{self._api_base}/users/{user_id}/tweets"
            params = {"max_results": max_results}
            headers = self._generate_signed_headers("GET", url, params=params)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return ToolResult(
                            success=True,
                            data=data,
                            metadata={"fetched_tweets": len(data.get("data", []))},
                        )
                    else:
                        error_data = await response.json()
                        return ToolResult(
                            success=False, data=None, error=str(error_data)
                        )
        except Exception as e:
            logger.error(f"Error reading tweets: {e}")
            return ToolResult(success=False, data=None, error=str(e))

    async def get_mentions(self, user_id: str, max_results: int = 5) -> ToolResult:
        """Retrieve tweets that mention the specified user using the Twitter API."""
        try:
            url = f"{self._api_base}/users/{user_id}/mentions"
            params = {"max_results": max_results}
            headers = self._generate_signed_headers("GET", url, params=params)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return ToolResult(
                            success=True,
                            data=data,
                            metadata={"mention_count": len(data.get("data", []))},
                        )
                    else:
                        error_data = await response.json()
                        return ToolResult(
                            success=False, data=None, error=str(error_data)
                        )
        except Exception as e:
            logger.error(f"Error getting mentions: {e}")
            return ToolResult(success=False, data=None, error=str(e))

    async def search_tweets_by_hashtag(
        self, hashtag: str, max_results: int = 10
    ) -> ToolResult:
        """Search for recent tweets containing the specified hashtag using the Twitter API."""
        try:
            url = f"{self._api_base}/tweets/search/recent"
            search_query = hashtag if hashtag.startswith("#") else f"#{hashtag}"
            params = {"query": search_query, "max_results": max_results}
            headers = self._generate_signed_headers("GET", url, params=params)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return ToolResult(
                            success=True,
                            data=data,
                            metadata={"tweet_count": len(data.get("data", []))},
                        )
                    else:
                        error_data = await response.json()
                        return ToolResult(
                            success=False, data=None, error=str(error_data)
                        )
        except Exception as e:
            logger.error(f"Error searching tweets by hashtag: {e}")
            return ToolResult(success=False, data=None, error=str(e))

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
            params_model = TwitterPostParams(message=message, media_url=media_url)
            url = f"{self._api_base}/tweets"
            payload = {"text": params_model.message}

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
            logger.error(f"Error posting tweet: {e}")
            return ToolResult(success=False, data=None, error=str(e))
