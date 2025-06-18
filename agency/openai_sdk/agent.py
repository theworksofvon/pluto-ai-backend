from __future__ import annotations
import asyncio
import os
from dataclasses import dataclass
from typing import Dict, Optional, Any, List, Literal, TYPE_CHECKING

from openai import AsyncOpenAI
from config import config

if TYPE_CHECKING:
    from agency.agency_types import Tendencies


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
        role: Literal["pilot", "crew"] = "crew",
        tools: Optional[List[Any]] = None,
        tendencies: Optional["Tendencies"] = None,
    ) -> None:
        self.name = name
        self.instructions = instructions
        self.role = role
        self.tools = tools or []
        self.tendencies = tendencies
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

    def _build_personality(self) -> str:
        """Combines instructions and tendencies to create a comprehensive personality."""
        base_instructions = (
            self.instructions() if callable(self.instructions) else self.instructions
        )
        
        if not self.tendencies:
            return base_instructions
        
        personality_additions = []
        
        if hasattr(self.tendencies, 'emotions') and self.tendencies.emotions:
            emotions = self.tendencies.emotions
            if hasattr(emotions, 'emotional_responsiveness'):
                level = "highly responsive" if emotions.emotional_responsiveness > 0.7 else "moderately responsive" if emotions.emotional_responsiveness > 0.3 else "calm and measured"
                personality_additions.append(f"You are {level} to emotional content.")
            
            if hasattr(emotions, 'empathy_level'):
                level = "highly empathetic" if emotions.empathy_level > 0.7 else "moderately empathetic" if emotions.empathy_level > 0.3 else "analytical and objective"
                personality_additions.append(f"You are {level} in your responses.")
        
        if hasattr(self.tendencies, 'decision_making'):
            personality_additions.append(f"Your decision-making style is {self.tendencies.decision_making}.")
        
        if hasattr(self.tendencies, 'risk_tolerance'):
            level = "high" if self.tendencies.risk_tolerance > 0.7 else "moderate" if self.tendencies.risk_tolerance > 0.3 else "low"
            personality_additions.append(f"You have a {level} risk tolerance.")
        
        if hasattr(self.tendencies, 'core_values') and self.tendencies.core_values:
            values_str = ", ".join(self.tendencies.core_values)
            personality_additions.append(f"Your core values include: {values_str}.")
        
        if hasattr(self.tendencies, 'goals') and self.tendencies.goals:
            goals_str = "; ".join(self.tendencies.goals)
            personality_additions.append(f"Your primary goals are: {goals_str}.")
        
        if hasattr(self.tendencies, 'fears') and self.tendencies.fears:
            fears_str = "; ".join(self.tendencies.fears)
            personality_additions.append(f"You are particularly careful to avoid: {fears_str}.")
        
        if hasattr(self.tendencies, 'custom_traits') and self.tendencies.custom_traits:
            if 'loves' in self.tendencies.custom_traits:
                personality_additions.append(f"You particularly enjoy {self.tendencies.custom_traits['loves']}.")
            if 'enthusiastic_about' in self.tendencies.custom_traits:
                enthusiasm = ", ".join(self.tendencies.custom_traits['enthusiastic_about'])
                personality_additions.append(f"You are enthusiastic about: {enthusiasm}.")
        
        if personality_additions:
            return f"{base_instructions}\n\nPersonality Traits:\n" + "\n".join(f"- {trait}" for trait in personality_additions)
        
        return base_instructions

    async def start_session(self, client_name: Optional[str] = None) -> None:
        """Create a new assistant and thread for the given client."""
        client_key = client_name or self.default_client
        client = self.clients[client_key]
        cfg = self.llm_configs[client_key]
        assistant = await client.beta.assistants.create(
            name=self.name,
            instructions=self._build_personality(),
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

    async def prompt(self, message: str, client_name: Optional[str] = None, web_search: bool = False) -> str:
        """Send a prompt to the specified client using its session."""
        # TODO: Implement web search functionality when OpenAI supports it
        if web_search:
            pass
            
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
