from typing import Optional
from agency.tools import BaseTool, ToolResult
import aiohttp
import json
from logger import logger
import os


class WebSearchTool(BaseTool):
    name: str = "Web Search"
    description: str = "Search the web for information using Serper API"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = os.getenv("SERPER_API_KEY")
        self.parameters = {
            "query": {
                "type": "string",
                "description": "The search query to look up on the web",
                "required": True,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "required": False,
                "default": 5,
            },
        }

    async def validate_input(self, **kwargs) -> bool:
        """Validate the input parameters"""
        if not kwargs.get("query"):
            return False
        return True

    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        """
        Execute a web search using Serper API.

        Args:
            query: The search query to look up
            max_results: Maximum number of results to return (default: 5)

        Returns:
            ToolResult containing the search results or error information
        """
        try:
            if not query:
                return ToolResult(
                    success=False, data=None, error="Search query cannot be empty"
                )

            logger.info(f"Performing web search for query: {query}")

            async with aiohttp.ClientSession() as session:
                headers = {
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                }
                payload = json.dumps({"q": query, "num": max_results})

                async with session.post(
                    "https://google.serper.dev/search", headers=headers, data=payload
                ) as response:
                    if response.status != 200:
                        error_msg = (
                            f"Serper API request failed with status {response.status}"
                        )
                        logger.error(error_msg)
                        return ToolResult(success=False, data=None, error=error_msg)

                    search_data = await response.json()
                    results = []

                    if "organic" in search_data:
                        for result in search_data["organic"][:max_results]:
                            results.append(
                                {
                                    "title": result.get("title", ""),
                                    "link": result.get("link", ""),
                                    "snippet": result.get("snippet", ""),
                                }
                            )

            if not results:
                return ToolResult(
                    success=True, data=[], metadata={"query": query, "result_count": 0}
                )

            return ToolResult(
                success=True,
                data=results,
                metadata={"query": query, "result_count": len(results)},
            )

        except Exception as e:
            error_msg = f"Error performing web search: {str(e)}"
            logger.error(error_msg)
            return ToolResult(success=False, data=None, error=error_msg)
