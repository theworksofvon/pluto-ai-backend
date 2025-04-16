from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Config(BaseSettings):
    # Odds API
    ODDS_API_KEY: str = Field(description="Odds API api key", default="")

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

    OPENAI_API_KEY_OAI: str = Field(
        description="OpenAI API key",
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

    # Supabase
    SUPABASE_URL: str = Field(
        description="Supabase project URL",
        default="",
    )
    SUPABASE_KEY: str = Field(
        description="Supabase project API key",
        default="",
    )

    OLLAMA_API_URL: str = Field(
        description="Ollama API URL",
        default="",
    )
    OLLAMA_MODEL_NAME: str = Field(
        description="Ollama model name",
        default="",
    )
    OPENAI_API_KEY: str = Field(
        description="OpenAI API key",
        default="",
    )

    ACCESS_TOKEN: str = Field(
        description="Access token",
        default="",
    )

    JWT_SUPABASE_SECRET: str = Field(
        description="JWT Supabase secret",
        default="",
    )

    class Config:
        env_file = (
            ".env" if os.environ.get("ENVIRONMENT", "local") == "local" else ".env.prod"
        )
        env_file_encoding = "utf-8"


config = Config()
