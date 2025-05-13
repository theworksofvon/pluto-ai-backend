from agency.agent import Agent
from logger import logger
from adapters import Adapters
from agency.tools.default_tools import TwitterTool, WebSearchTool
from pydantic import BaseModel
from typing import Optional
from utils import SchemaJsonParser, FieldSchema, FieldType
from datetime import datetime
from shared.personality import PLUTO_PERSONALITY
from config import config
from typing import List
from adapters.scheduler import AbstractScheduler


class TweetSchema(BaseModel):
    message: str
    media_url: Optional[str] = None


class RogueAgent(Agent):
    """
    Rogue Agent that posts tweets to twitter.
    """

    parser: SchemaJsonParser = None
    tweet_schema: List[FieldSchema] = []
    adapters: Adapters = None
    scheduler: AbstractScheduler = None

    def __init__(self, **kwargs):
        super().__init__(
            name="RogueAgent",
            model="grok",
            instructions=PLUTO_PERSONALITY
        )
        self.adapters = Adapters()
        self.scheduler = self.adapters.scheduler
        self.tools = [
            TwitterTool(
                api_key=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_API_KEY,
                api_secret=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_API_SECRET,
                access_token=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_ACCESS_TOKEN,
                access_token_secret=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_ACCESS_TOKEN_SECRET,
                client_id=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_CLIENT_ID,
                client_secret=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_CLIENT_SECRET,
            ),
            WebSearchTool()
        ]
        self.tweet_schema = [
            FieldSchema(name="message", type=FieldType.STRING, required=True),
            FieldSchema(name="media_url", type=FieldType.STRING, required=False),
        ]
        self.parser = SchemaJsonParser(self.tweet_schema)

    async def execute_task(self):
        self.scheduler.add_interval_job(
            func=self.tweet_latest_news,
            hours=0,
            minutes=1,
            job_id="twitter_agent_tweet_latest_news",
        )
        self.scheduler.start()
        logger.info("Twitter agent is running...")

    async def random_tweet(self):
        today = datetime.now().strftime("%Y-%m-%d")
        prompt_message = f"Tweet something crazy that has happened in the media today. {today}. Do not use hashtags and keep tweets short and concise. Don't say yo. no more than 15 words. tweets should be all lowercase and no punctuation unless necessary. Do not use emojis or special characters. Curse and be free. Be based. Feel free to write about anything not just crypto, those are just some meme style tweets to take inspiration from."
        response = await self.prompt(prompt_message, format=TweetSchema)
        response_data = self.parser.parse(response)
        try:
            await self.tools[0].execute(message=response_data.message)
        except Exception as e:
            logger.error(f"Error posting tweet: {e}")
            
    async def get_news(self, topic: Optional[str] = None):
        today = datetime.now().strftime("%Y-%m-%d")
        news_response = await self.search_web(f"latest news for {topic} {today}")
        logger.info(f"News: {news_response}")
        return news_response
    
    async def tweet_latest_news(self, topic: Optional[str] = None):
        today = datetime.now().strftime("%Y-%m-%d")
        news_response = await self.get_news(topic)
        prompt_message = f"here's some search results for news today {today}: {news_response}. Tweet something crazy that has happened in the media today. Do not use hashtags and keep tweets short and concise. Don't say yo. no more than 15 words. tweets should be all lowercase and no punctuation unless necessary. Do not use emojis or special characters. Curse and be free. Be based. Feel free to write about anything not just crypto, those are just some meme style tweets to take inspiration from."
        response = await self.prompt(prompt_message, format=TweetSchema)
        response_data = self.parser.parse(response)
        try:
            await self.tools[0].execute(message=response_data.message)
        except Exception as e:
            logger.error(f"Error posting tweet: {e}")
            
    async def search_web(self, query: str):
       response = await self.tools[1].execute(query=query, fetch_content=True)
       logger.info(f"Web search response: {response.data}")
       return response.data
   
        
