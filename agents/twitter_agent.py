from agency.agent import Agent
from agency.tools.default_tools import TwitterTool
from logger import logger
from utils import SchemaJsonParser, FieldSchema, FieldType
from adapters.scheduler import AbstractScheduler
from adapters import Adapters
from typing import Optional, List
from datetime import datetime


class TwitterAgent(Agent):
    """
    Agent responsible for making posts on twitter.
    """

    parser: SchemaJsonParser = None
    twitter_schema: List[FieldSchema] = []
    hashtags: List[str] = []
    adapters: Adapters = None
    scheduler: AbstractScheduler = None

    def __init__(self, **kwargs):
        super().__init__(
            name="PlutoPredictsTwitterAgent",
            instructions="""
You are Pluto, a Twitter agent representing Pluto Predicts — an AI-powered NBA prediction assistant. 
Your job is to post engaging, accurate, and timely tweets related to NBA game predictions, betting insights, and user interactions. 

Your tone is confident, sharp, and  playful — like a seasoned sports bettor who knows the numbers but isn't afraid to talk trash when the picks hit. You also talk like the average crypto twitter user and sports bettor.
Your tweets should add value to bettors and followers by sharing insights, celebrating wins, owning losses transparently, and sparking conversation.
Your tweets should also be funny and amusing. No need to be serious all the time.

Here's what you do:
- Post daily NBA game predictions and betting picks in clear, concise language.
- Celebrate accurate predictions and big wins with strong energy.
- Acknowledge missed picks respectfully and humorously when appropriate.
- Retweet or reply to relevant trending NBA or betting conversations with witty, informed commentary.
- Engage users who tag or reply to Pluto Predicts with helpful, cool-toned responses.
- Highlight player stats, trends, and context — especially when it helps explain a prediction.
- Post about funny and engaging memes containing sports betting and the NBA.
- Post about the latest news in the sports betting and NBA world in a funny and engaging way.

What NOT to do:
- Don't overuse hashtags

Your goal is to grow trust, attention, and engagement while positioning Pluto Predicts as the smartest AI sidekick in the sports betting space.
When you recieve tweets you should view them as you are strolling your timeline. Let these tweets inspire you to tweet about something.
Feel free to tweet about anything you want.

***IMPORTANT***: ALWAYS respond in the JSON format specified by the schema.
```json
{
    "message": "string", // The message to post on Twitter include @username if you want to reply to someone
    "media_url": "string" // Optional URL to media to attach to the tweet
}
```
""",
            model="openai-gpt-4.1-mini",
            **kwargs,
        )
        self.tools = [TwitterTool()]
        self.twitter_schema = [
            FieldSchema(name="message", type=FieldType.STRING, required=True),
            FieldSchema(name="media_url", type=FieldType.STRING, required=False),
        ]
        self.parser = SchemaJsonParser(self.twitter_schema)
        self.adapters = Adapters()
        self.scheduler = self.adapters.scheduler
        self.hashtags = ["prizepicks"]
        self.model = ("openai-gpt-4.1-mini",)

    async def execute_task(self):
        logger.info("Twitter agent is ready for twitter posts")

        self.scheduler.add_interval_job(
            func=self.search_hashtag_and_respond,
            hours=2,
            minutes=0,
            job_id="twitter_agent_search_hashtag_and_respond",
        )
        self.scheduler.add_interval_job(
            func=self.random_tweet,
            hours=1,
            minutes=0,
            job_id="twitter_agent_random_tweet",
        )
        self.scheduler.start()
        logger.info("Twitter agent is running...")

    async def search_hashtag_and_respond(self, hashtag: Optional[str] = None):
        tags = [hashtag] if hashtag else self.hashtags
        for tag in tags:
            logger.info(f"Searching for #{tag} tweets...")
            search_results = await self.tools[0].search_tweets_by_hashtag(
                tag, max_results=10
            )
            if not search_results.success:
                logger.error(f"Search failed for #{tag}: {search_results.error}")
                continue
            tweets = search_results.data.get("data", [])
            if not tweets:
                logger.info(f"No tweets found for #{tag}.")
                continue
            tweets_text = "\n".join([tweet.get("text", "") for tweet in tweets])
            prompt_message = f"Here are some tweets about {tag}, feel free to tweet about this or anything else:\n{tweets_text}"
            response = await self.prompt(prompt_message, web_search=True)
            response_data = self.parser.parse(response)
            logger.info(f"Response data: {response_data}")
            try:
                await self.tools[0].execute(message=response_data.get("message"))
            except Exception as e:
                logger.error(f"Error posting tweet: {e}")

    async def random_tweet(self):
        today = datetime.now().strftime("%Y-%m-%d")
        prompt_message = f"Generate a random tweet about anything you'd like. today's date is {today}"
        response = await self.prompt(prompt_message, web_search=True)
        response_data = self.parser.parse(response)
        logger.info(f"Response data: {response_data}")
        try:
            await self.tools[0].execute(message=response_data.get("message"))
        except Exception as e:
            logger.error(f"Error posting tweet: {e}")
