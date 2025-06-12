from __future__ import annotations
import asyncio
import os
from dataclasses import dataclass
from typing import Dict, Optional, Any

from openai import AsyncOpenAI
from config import config


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str


class OpenAIAgent:
    """Simplified agent using OpenAI's Assistant API for memory management."""

    def __init__(
        self,
        name: str,
        instructions: str,
        llm_configs: Optional[Dict[str, LLMConfig]] = None,
        default_client: str = "openai",
    ) -> None:
        self.name = name
        self.instructions = instructions
        self.llm_configs = llm_configs or {
            "openai": LLMConfig(
                base_url="https://api.openai.com/v1",
                api_key=config.OPENAI_API_KEY_OAI or os.getenv("OPENAI_API_KEY"),
                model="o3",
            )
        }
        self.clients = {
            key: AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
            for key, cfg in self.llm_configs.items()
        }
        self.default_client = default_client
        self.sessions: Dict[str, Dict[str, str]] = {}

    async def start_session(self, client_name: Optional[str] = None) -> None:
        """Create a new assistant and thread for the given client."""
        client_key = client_name or self.default_client
        client = self.clients[client_key]
        cfg = self.llm_configs[client_key]
        assistant = await client.beta.assistants.create(
            name=self.name,
            instructions=self.instructions,
            model=cfg.model,
        )
        thread = await client.beta.threads.create()
        self.sessions[client_key] = {
            "assistant_id": assistant.id,
            "thread_id": thread.id,
        }

    async def load_session(
        self, thread_id: str, assistant_id: str, client_name: Optional[str] = None
    ) -> None:
        """Load an existing session for a client."""
        client_key = client_name or self.default_client
        self.sessions[client_key] = {
            "assistant_id": assistant_id,
            "thread_id": thread_id,
        }

    async def prompt(self, message: str, client_name: Optional[str] = None) -> str:
        """Send a prompt to the specified client using its session."""
        client_key = client_name or self.default_client
        client = self.clients.get(client_key)
        if client is None:
            raise ValueError(f"Unknown client: {client_name}")

        session = self.sessions.get(client_key)
        if session is None:
            await self.start_session(client_key)
            session = self.sessions[client_key]

        await client.beta.threads.messages.create(
            thread_id=session["thread_id"],
            role="user",
            content=message,
        )
        run = await client.beta.threads.runs.create(
            thread_id=session["thread_id"],
            assistant_id=session["assistant_id"],
        )
        while True:
            run = await client.beta.threads.runs.retrieve(
                thread_id=session["thread_id"], run_id=run.id
            )
            if run.status in {"completed", "failed"}:
                break
            await asyncio.sleep(0.5)
        if run.status == "failed":
            raise RuntimeError(str(run.last_error))
        messages = await client.beta.threads.messages.list(
            thread_id=session["thread_id"],
            limit=1,
        )
        return messages.data[0].content[0].text.value

    async def execute_task(self, **kwargs) -> Any:
        raise NotImplementedError()

    async def run(self, **kwargs):
        result = await self.execute_task(**kwargs)
        feedback = yield result
        if feedback:
            result = await self.prompt(message=feedback)
            yield result
