from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Config(BaseSettings):
    # Odds API
    ODDS_API_KEY: str = Field(
        description="Odds API api key", default=""
    )
    
    PORT: int = Field(
        description="Port",
        default=10000,
    )
    
    ENVIRONMENT: str = Field(
        description="Environment",
        default="local",
    )
    
    LLAMA_CLOUD_API_KEY: str = Field(
        description="Llama Cloud API key",
        default="",
    )
    
    PLUTO_DATASET_FILE_NAME: str = Field(
        description="Path to the Pluto dataset",
        default="pluto_training_dataset_v1.csv",
    )
    
    ODDS_FILE_NAME: str = Field(
        description="Path to the odds dataset",
        default="vegas_odds.csv",
    )

    # DB
    DATABASE_URI: str = Field(
        description="Database URI",
        default="",
    )
    SQL_ECHO: bool = False
    
    OLLAMA_API_URL: str = os.environ.get("OLLAMA_API_URL", "")
    OLLAMA_MODEL_NAME: str = os.environ.get(
        "OLLAMA_MODEL_NAME", ""
    )
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")


    
    class Config:
        env_file = ".env" if os.environ.get("ENVIRONMENT", "local") == "local" else ".env.prod"
        env_file_encoding = 'utf-8'


config = Config()
