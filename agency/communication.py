import os
from typing import Dict, List, Optional, Union
import aiohttp
import traceback
from openai import OpenAI
from pydantic import BaseModel
from config import config
from .exceptions import CommunicationsProtocolError
from logger import logger


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
        self.default_open_ai_model = "gpt-4o-mini"
        self.default_deepseek_model = "deepseek-chat"
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
        self,
        prompt: str,
        sender: str,
        format: Optional[Dict] = None,
        web_search: bool = False,
    ) -> str:
        """
        Send a prompt to the model, including personality and history, and return the response.
        Mainly for agent -> agent communication.

        Args:
            prompt (str): The input prompt for the model.

        Returns:
            str: The model's response.
        """

        if web_search and not self.model.startswith("openai"):
            raise ValueError("Web search is not supported for this model.")

        full_prompt = prompt

        if self.model.startswith("openai"):
            response = await self._send_to_openai(full_prompt, format, web_search)
        elif self.model.startswith("deepseek"):
            response = await self._send_to_deepseek(full_prompt, format)
        elif self.model.startswith("ollama"):
            response = await self._send_to_ollama(full_prompt, format)
        elif self.model.startswith("grok"):
            response = await self._send_to_grok(prompt=prompt, format=format)
        try:
            self._update_history("user", prompt)
            self._update_history("assistant", response)
        except Exception as error:
            error_message = f"Failed to update agent's context history, error: {error}"
            raise CommunicationsProtocolError(error_message, status_code=400)
        return response

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
        )
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

    async def _send_to_openai(
        self, prompt: str, format: Optional[Dict] = None, web_search: bool = False
    ) -> str:
        """
        Handle communication with a remote OpenAI model.

        Args:
            prompt (str): The input prompt for the model.
            format (Dict] type: The response format for the model. Defaults to json_object.
            web_search (bool): Whether to invoke the built‑in web search tool.

        Returns:
            str: The model's response.
        """
        api_key = self.config.OPENAI_API_KEY_OAI or os.getenv("OPENAI_API_KEY_OAI")
        if not api_key:
            raise ValueError("OpenAI API key is missing.")

        client = OpenAI(base_url="https://api.openai.com/v1", api_key=api_key)
        tools = [{"type": "web_search_preview"}] if web_search else None

        try:
            response = client.responses.create(
                model=self.default_open_ai_model,
                input=prompt,
                tools=tools,
            )
            logger.info(f"OpenAI response: {response}")
            outputs = response.output
            text = ""
            for msg in outputs:
                if hasattr(msg, "content") and msg.content and len(msg.content) > 0:
                    text = msg.content[0].text
                    break
            if not text:
                for msg in outputs:
                    if hasattr(msg, "function_call") and msg.function_call:
                        text = msg.function_call.arguments
                        break
            return text
        except Exception as error:
            error_message = f"Error communicating with OpenAI model: {self.default_open_ai_model}, error: {error}"
            print(error_message)
            raise CommunicationsProtocolError(error_message, status_code=400)

    async def _send_to_grok(
        self, prompt: str, format: Optional[BaseModel] = None
    ) -> str:
        """
        Handle communication with a remote Grok model.

        Args:
            prompt (str): The input prompt for the model.
            format (Optional[BaseModel]): The response format for the model. Can be a Pydantic BaseModel.

        Returns:
            str: The model's response.
        """
        api_key = self.config.GROK_API_KEY or os.getenv("GROK_API_KEY")
        if not api_key:
            raise ValueError("Grok API key is missing.")

        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        try:
            response = client.beta.chat.completions.parse(
                model="grok-3-mini-beta",
                messages=[
                    {
                        "role": "system",
                        "content": self.personality,
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=format,
            )
            return response.choices[0].message.parsed
        except Exception as error:
            full_trace = traceback.format_exc()
            error_message = (
                f"Error communicating with Grok model: {self.model}\n"
                f"{str(error)}\n"
                f"{full_trace}"
            )
            logger.error(error_message)
            raise CommunicationsProtocolError(error_message, status_code=400)

    async def _send_to_deepseek(
        self, prompt: str, format: Optional[Dict] = None
    ) -> str:
        """
        Handle communication with a remote DeepSeek model.

        Args:
            prompt (str): The input prompt for the model.
            format (Dict) type: The response format for the model. Defaults to json_object.
        Returns:
            str: The model's response.
        """
        api_key = self.config.OPENAI_API_KEY or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DeepSeek API key is missing.")

        client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=api_key)

        try:
            completion = client.chat.completions.create(
                model=self.default_deepseek_model,
                messages=[{"role": "user", "content": f"{prompt}"}],
                stream=False,
            )
            return completion.choices[0].message.content
        except Exception as error:
            error_message = (
                f"Error communicating with DeepSeek model: {self.model}, error: {error}"
            )
            print(error_message)

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
