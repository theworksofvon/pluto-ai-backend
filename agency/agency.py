import asyncio
from typing import List, Dict, Union, Optional, Any
from openai_sdk.agent import OpenAIAgent
from .engines.reasoning_engine import ReasoningEngine


class Agency:
    def __init__(self, agents: List[OpenAIAgent]) -> None:
        """
        Initialize the Agency with agents and set up the pilot.
        """
        self.agents: Dict[str, OpenAIAgent] = {agent.name: agent for agent in agents}
        self.pilot = next((agent for agent in agents if agent.role == "pilot"), None)
        self.memory = None
        self.context: Dict[str, Any] = {}
        self.reasoner = None
        self.tools = next((agent.tools for agent in agents if agent.tools), None)

        if not self.pilot:
            raise ValueError("Agency must have at least one pilot agent.")

    def _establish_reasoning_engine(self) -> None:
        if self.pilot is None:
            raise ValueError("Pilot agent must be initialized")
        self.reasoner = ReasoningEngine(agent=self.pilot, tools=self.tools)

    def _find_agent_by_tool(self, tool_name: str) -> Optional[OpenAIAgent]:
        for agent_name, agent in self.agents.items():
            if agent.tools and any(tool.name == tool_name for tool in agent.tools):
                print(f"agent found, {agent_name}")
                return agent
        print("No agent found")
        return None

    def update_context(self, key: str, value: Any) -> None:
        """
        Updates the shared context with new information.
        """
        self.context[key] = value

    async def send_message(
        self, sender: str, message: str, receiver: Optional[str] = None
    ) -> Union[str, None]:
        """
        Facilitates communication between agents.

        Args:
            sender (str): Name of the sending agent.
            receiver (str): Name of the receiving agent. Defaults to the pilot agent.
            message (str): Message to be sent.

        Returns:
            Union[str, None]: Response from the receiving agent, or None if the receiver is not found.
        """
        if receiver is not None and receiver not in self.agents:
            return f"Agent {receiver} not found in agency."
        if receiver is not None:
            agent = self.agents[receiver]
            res = await agent.prompt(message=message)
        else:
            res = await self.pilot.prompt(message=message)
        return res

    async def run(self, starting_prompt: Optional[str] = None):
        """
        Executes tasks for all worker agents, facilitates communication with the pilot,
        and incorporates reasoning and decision-making.
        """

        async def process_agent(agent: OpenAIAgent):
            print(f"Running task for worker agent: {agent.name}")

            max_iterations = 1
            feedback_iterations = 0

            gen = agent.run()

            try:
                result = await gen.__anext__()

                if not isinstance(result, str):
                    result = str(result)

                while feedback_iterations < max_iterations:
                    print(f"Task result from {agent.name}: {result}")

                    self.update_context(agent.name, result)

                    feedback = await self.send_message(
                        sender=agent.name, message=result
                    )

                    result = await gen.asend(feedback)
                    feedback_iterations += 1

            except StopAsyncIteration as error:
                print(error)
                return None

            return result

        self._establish_reasoning_engine()
        action_plan = await self.reasoner.reason(task=starting_prompt)
        if hasattr(action_plan, "plan"):
            agent = self._find_agent_by_tool(action_plan.plan.tool_name)
            tasks = [process_agent(agent=agent)]
        else:
            tasks = []
            print("No action plan returned from reasoning engine")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return results
