from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
from agency.tools import BaseTool


@dataclass
class LastState:
    last_task: str
    last_reason: str


@dataclass
class ReasonerContext:
    """Context object for reasoner state and decision making"""

    task: str
    last_state: LastState
    tools_available: List[str]
    history: List[Dict[str, Any]]


@dataclass
class ActionPlan:
    """Represents a planned action with tool selection"""

    tool_name: str
    reason: str
    priority: int


@dataclass
class ReasonerResponse:
    """Response object from engine reasoning"""

    plan: ActionPlan
    reason: str


class ReasoningEngine:
    def __init__(self, agent, tools: Dict[str, BaseTool]):
        """
        Initialize Reasoner with an AI agent and available tools

        Args:
            agent: The AI agent for decision making
            tools: Dictionary of available tools {"<tool_name>: <Tool>}
        """
        self.agent = agent
        self.tools = tools
        self.context = ReasonerContext(
            task="",
            tools_available=([tool.name for tool in tools] if tools else [""]),
            last_state={},
            history=[],
        )

    async def decide_action(self, task: str) -> Optional[ActionPlan]:
        """
        Ask the AI agent to decide what tool to use for a given task
        """
        # Update context with new task
        self.context.task = task

        # Create prompt for the agent
        prompt = self._create_decision_prompt()

        # Get pilot agent's decision
        response = await self.agent.prompt(prompt)

        # Parse agent's response into an ActionPlan
        try:
            action_plan = self._parse_agent_response(response)
            return action_plan
        except ValueError as e:
            print(f"Error parsing agent response: {e}")
            return None

    def _create_decision_prompt(self) -> str:
        """Create a prompt for the agent to make a decision"""
        tools_info = "\n".join(
            [f"- {tool.name}: {tool.description}\n" for tool in self.tools]
            if self.tools
            else "No tools available"
        )

        return f"""Given the following task and ONLY THE AVAILABLE TOOLS, decide which tool would be most appropriate to use.

Task: {self.context.task}

Available Tools:
{tools_info}

Current Context:
{self.context}
Please decide:
1. Which tool should be used?
2. Why did you choose this tool?
3. How important is this action (priority 1-5)?

***RESPOND IN JSON FORMAT, VALUES FOR TOOL AND REASON ARE STRINGS, PRIORITY IS A NUMBER AND ONLY THIS RESPONSE YOU ARE LIMITED TO THIS RESPONSE***IMPORTANT:
tool_name: <tool_name>
reason: <your_reason>
priority: <1-5>
"""

    def _parse_agent_response(self, response: str) -> ActionPlan:
        """Parse the agent's response into an ActionPlan"""
        # Implementation would parse the structured response
        # This is a simplified example
        try:
            print(f"Raw response: {response}")
            parsed_response = json.loads(response)
            print(f"Parsed response: {parsed_response}")

            return ActionPlan(
                tool_name=parsed_response["tool_name"],
                reason=parsed_response["reason"],
                priority=parsed_response["priority"],
            )
        except Exception as e:
            raise ValueError(f"Failed to parse agent response: {e}")

    async def execute_plan(self, plan: ActionPlan) -> Dict[str, Any]:
        """Execute a planned action using the agent that has access to tool"""
        tool = self.tools.get(plan.tool_name)
        if not tool:
            raise ValueError(f"Tool {plan.tool_name} not found")

        result = await tool.execute(**plan.parameters)

        # Update context with result
        self.context.history.append(
            {
                "task": self.context.task,
                "tool": plan.tool_name,
                "result": result,
                "reason": plan.reason,
            }
        )

        return result

    async def reason(
        self, task: str = "Do something that you would really like to do."
    ) -> ReasonerResponse:
        """Main method to trigger the reasoning process"""
        # Get agent's decision
        plan = await self.decide_action(task)
        if not plan:
            return {"error": "Could not determine action"}

        # Execute the plan
        # result = await self.execute_plan(plan)

        # Update last state since this will have already been reasoned
        self.context.last_state = LastState(last_reason=plan.reason, last_task=task)

        return ReasonerResponse(plan=plan, reason=plan.reason)
