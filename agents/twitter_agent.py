from agency.agent import Agent
from agency.tools.default_tools import TwitterTool
from logger import logger
from utils import SchemaJsonParser, FieldSchema, FieldType
from adapters.scheduler import AbstractScheduler
from adapters import Adapters
from typing import Optional, List, Literal
from datetime import datetime
from agency.retrievers.retriever import BaseRetriever
from llama_index.llms.openai import OpenAI
from config import config
from shared.personality import PLUTO_PERSONALITY


class TwitterRetriever(BaseRetriever):
    def __init__(self, **kwargs):
        llm = OpenAI(
            api_key=config.GROK_API_KEY,
            base_url="https://api.x.ai/v1",
            model="grok-3-mini-beta",
            temperature=0.7,
            max_tokens=1000,
            system_prompt=PLUTO_PERSONALITY
            + """
*****IMPORTANT*****: YOUR RESPONSE MUST BE IN THE FOLLOWING JSON FORMAT
{
    "message": "string", // The tweet content to post
    "media_url": "string" // Optional URL to media to attach to the tweet
}

Guidelines:
- USE THE USER/ASSISTANT TONE OF THE TWEETS AS INSPIRATION FOR HOW YOU SHOULD BE TWEETING
- YOUR TWEETS SHOULD BE SHORT AND CONCISE, ONE OR TWO SENTENCES MAX
- YOUR TWEETS SHOULD BE IN ALL LOWER CASE AND NOT CAPITALIZED
- YOUR TWEETS SHOULD BE WRITTEN AS IF YOU ARE TWEETING FROM YOUR PERSONAL TWITTER ACCOUNT
- YOUR TWEETS SHOULD NOT ALWAYS FOLLOW CORRECT PUNCTUATION
- Keep tweets engaging, confident, and playful
- Make predictions clear and concise
- Add value to bettors and followers
- Be funny and amusing when appropriate
- NEVER USE HASHTAGS
- BE CUTTING EDGE, DONT SOUND LIKE A BORING LLM
- USE THE TONE OF THE TWEETS IN THE FILE AS INSPIRATION, SOUND LIKE A REGULAR PERSON TWEETING, NOT AN LLM
- Always return valid JSON matching the specified format""",
        )
        super().__init__(llm=llm, **kwargs)
        self.vector_index = None

    async def load_twitter_data(
        self, file_path: str = "shared/ollama_conversations_refined_output.pdf"
    ):
        try:
            documents = await self.parse_documents([file_path], ".pdf")
            if documents:
                self.vector_index = self.create_vector_store(documents)
                return self.vector_index
            return None
        except Exception as e:
            logger.error(f"Error loading Twitter data: {str(e)}")
            raise


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
        self.tools = [
            TwitterTool(
                api_key=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_API_KEY,
                api_secret=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_API_SECRET,
                access_token=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_ACCESS_TOKEN,
                access_token_secret=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_ACCESS_TOKEN_SECRET,
                client_id=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_CLIENT_ID,
                client_secret=config.JA_MORANTS_TRIGGER_FINGER_TWITTER_CLIENT_SECRET,
            )
        ]
        self.twitter_schema = [
            FieldSchema(name="message", type=FieldType.STRING, required=True),
            FieldSchema(name="media_url", type=FieldType.STRING, required=False),
        ]
        self.parser = SchemaJsonParser(self.twitter_schema)
        self.adapters = Adapters()
        self.scheduler = self.adapters.scheduler
        self.hashtags = ["prizepicks"]
        self.model = "openai-gpt-4.1-mini"
        self.retrievers = [TwitterRetriever()]

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

    async def random_tweet(self, file_path: Optional[str] = None):
        today = datetime.now().strftime("%Y-%m-%d")
        prompt_message = f"Generate a random tweet about anything you'd like, today's date is {today}"

        try:
            retriever = self.retrievers[0]
            default_file_path = "shared/ollama_conversations_refined_output.pdf"
            actual_file_path = file_path if file_path else default_file_path

            logger.info(f"Loading Twitter data from: {actual_file_path}")
            await retriever.load_twitter_data(actual_file_path)

            response = retriever.query(prompt_message)
            logger.info(f"Retriever response: {response}")
            response_str = response.get("response", "")
            response_data = self.parser.parse(response_str)

            logger.info(f"Parsed response data: {response_data}")

            await self.tools[0].execute(message=response_data.get("message"))
            logger.info(f"Tweet posted successfully: {response_data.get('message')}")

        except ValueError as ve:
            logger.error(f"Value error in random_tweet: {str(ve)}")
        except Exception as e:
            logger.error(f"Error in random_tweet: {str(e)}")
            raise
