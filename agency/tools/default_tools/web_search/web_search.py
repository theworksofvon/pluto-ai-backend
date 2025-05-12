from typing import Optional
from agency.tools import BaseTool, ToolResult
from duckduckgo_search import DDGS
from logger import logger
import traceback
import aiohttp
from bs4 import BeautifulSoup
import asyncio


class WebSearchTool(BaseTool):
    name: str = "Web Search"
    description: str = "Search the web for information using DuckDuckGo and fetch full content"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ddgs = DDGS()
        self.parameters = {
            "query": {
                "type": "string",
                "description": "The search query to look up on the web",
                "required": True
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "required": False,
                "default": 5
            },
            "fetch_content": {
                "type": "boolean",
                "description": "Whether to fetch and parse the full content of each result (default: False)",
                "required": False,
                "default": False
            }
        }
    
    async def _fetch_content(self, url: str) -> Optional[str]:
        """Fetch and parse the content of a webpage."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        for script in soup(["script", "style"]):
                            script.decompose()
                            
                        text = soup.get_text(separator=' ', strip=True)
                        
                        lines = (line.strip() for line in text.splitlines())
                        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                        text = ' '.join(chunk for chunk in chunks if chunk)
                        
                        return text[:5000]
                    else:
                        logger.warning(f"Failed to fetch content from {url}: Status {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {str(e)}")
            return None

    async def execute(self, query: str, max_results: int = 5, fetch_content: bool = False) -> ToolResult:
        """
        Execute a web search using DuckDuckGo.

        Args:
            query: The search query to look up
            max_results: Maximum number of results to return (default: 5)
            fetch_content: Whether to fetch and parse the full content of each result (default: False)

        Returns:
            ToolResult containing the search results or error information
        """
        try:
            if not query:
                logger.error("Cannot perform search: query is empty")
                return ToolResult(
                    success=False, 
                    data=None, 
                    error="Search query cannot be empty"
                )

            logger.info(f"Performing web search for query: {query}")
            results = []
            
            for r in self.ddgs.text(query, max_results=max_results):
                result = {
                    "title": r["title"],
                    "link": r["link"],
                    "snippet": r["body"]
                }
                
                if fetch_content:
                    content = await self._fetch_content(r["link"])
                    if content:
                        result["full_content"] = content
                
                results.append(result)
            
            if not results:
                logger.warning(f"No results found for query: {query}")
                return ToolResult(
                    success=True,
                    data=[],
                    metadata={
                        "query": query,
                        "result_count": 0
                    }
                )

            logger.info(f"Found {len(results)} results for query: {query}")
            return ToolResult(
                success=True,
                data=results,
                metadata={
                    "query": query,
                    "result_count": len(results),
                    "content_fetched": fetch_content
                }
            )

        except Exception as e:
            error_msg = f"Error performing web search: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Full error details: {traceback.format_exc()}")
            return ToolResult(
                success=False,
                data=None,
                error=error_msg
            )
