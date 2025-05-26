from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field, ConfigDict


@dataclass
class ToolResult:
    """Container for tool execution results"""

    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Optional[Dict] = None


class BaseTool(ABC, BaseModel):
    """Abstract base class for all tools"""

    name: str = Field(description="Name of the tool")
    description: str = Field(description="Description of the tool")
    parameters: Dict[str, Dict] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool's primary function"""
        pass

    @abstractmethod
    def validate_input(self, **kwargs) -> bool:
        """Validate the input parameters"""
        pass

    def get_parameters(self) -> Dict[str, Dict]:
        """Return the tool's parameter specifications"""
        return self.parameters

    def describe(self) -> Dict[str, Any]:
        """Return a description of the tool"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
