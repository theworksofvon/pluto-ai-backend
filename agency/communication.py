import os
from typing import Dict, List, Optional
import aiohttp
from openai import OpenAI
from config import config
from .exceptions import CommunicationsProtocolError


class CommunicationProtocol:
    """
    This protocol determines the communication layer between agents.
    The protocol is model-agnostic and handles both local (e.g., Ollama)
    and remote models (e.g., OpenAI API), incorporating agent-specific personality
    and context.
    """

    def __init__(self, model: str, personality: str = "") -> None:
        """
        Initialize the communication protocol with the specified model.

        Args:
            model (str): The model type (e.g., "ollama", "openai-{model_name}").
            config (Dict): Configuration parameters for the model (e.g., API key, endpoint).
            personality (str): The personality or context of the agent.
        """
        self.model = model.lower()
        self.config = config
        self.default_open_ai_model = "deepseek-chat"
        self.personality = personality  # Personality of the agent
        self.history: List[Dict[str, str]] = (
            []
        )  # To track the context of the conversation

    ## TODO: validate every response that goes out
    def _validate_llm_response(self, response: str):
        if response:
            return True
        return False

    ## TODO: ollama to respond in json
    async def send_prompt(
        self, prompt: str, sender: str, format: Optional[Dict] = None
    ) -> str:
        """
        Send a prompt to the model, including personality and history, and return the response.
        Mainly for agent -> agent communication.

        Args:
            prompt (str): The input prompt for the model.

        Returns:
            str: The model's response.
        """
        full_prompt = self._build_prompt(prompt, sender)

        if self.model.startswith("openai"):
            response = await self._send_to_openai(full_prompt)
        else:
            response = await self._send_to_ollama(full_prompt, format)
        try:
            self._update_history("user", prompt)
            self._update_history("assistant", response)
        except Exception as error:
            error_message = f"Failed to update agent's context history, error: {error}"
            raise CommunicationsProtocolError(error_message, status_code=400)
        return response

    # TODO: Maximine use of 128k token context window, better prompt building
    def _build_prompt(self, prompt: str, sender: str) -> str:
        """
        Combine personality, context, and the new prompt into a full query.

        Args:
            prompt (str): The input prompt for the model.

        Returns:
            str: The full prompt including personality and history.
        """
        context = "\n".join(
            [f"{item['role']}: {item['content']}" for item in self.history[-5:]]
        )  # Last 5 interactions
        return f"{self.personality}\n\n{context}\n\nUser - {sender}: {prompt}"

    async def _send_to_ollama(self, prompt: str, format: Optional[Dict] = None) -> str:
        """
        Handle communication with a local Ollama model.

        Args:
            prompt (str): The input prompt for the model.

        Returns:
            str: The model's response.
        """
        url = f"{self.config.OLLAMA_API_URL}/generate"
        async with aiohttp.ClientSession() as session:

            try:
                async with session.post(
                    url,
                    json={
                        "prompt": prompt,
                        "stream": False,
                        "model": self.model,
                        "format": format,
                    },
                ) as res:
                    res.raise_for_status()
                    json_response = await res.json()
                    return json_response["response"]
            except Exception as error:
                error_message = f"Error communicating with Ollama model: {self.model}, error: {error}"
                print(error_message)
                raise CommunicationsProtocolError(error_message, status_code=400)

    async def _send_to_openai(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Handle communication with the OpenAI API.

        Args:
            prompt (str): The input prompt for the model.

        Returns:
            str: The model's response.
        """
        api_key = self.config.get("openai_api_key", os.getenv("OPENAI_API_KEY"))
        if not api_key:
            raise ValueError("OpenAI API key is missing.")
        client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=api_key)
        model_name = self.model.split("-")[1]

        try:
            completion = client.chat.completions.create(
                model=model_name if model_name else self.default_open_ai_model,
                messages=[{"role": "user", "content": f"{prompt}"}],
                stream=False,
            )
            return completion.choices[0].message.content
        except Exception as error:
            error_message = (
                f"Error communicating with OpenAI model: {self.model}, error: {error}"
            )
            print(error_message)
            raise CommunicationsProtocolError(error_message, status_code=400)

    def _update_history(self, role: str, content: str) -> None:
        """
        Update the conversation history.

        Args:
            role (str): The role of the speaker (e.g., "user", "assistant").
            content (str): The content of the message.
        """
        self.history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        """
        Clear the conversation history.
        """
        self.history = []
