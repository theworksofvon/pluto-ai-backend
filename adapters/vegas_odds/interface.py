from abc import ABC, abstractmethod
from typing import List, Optional, Union, Any
from pydantic import BaseModel


class SportsResponse(BaseModel):
    key: str
    group: str
    title: str
    active: bool
    has_outrights: bool


class VegasOddsResponse(BaseModel):
    response: Union[SportsResponse, Any]
    status_code: int


class VegasOddsInterface(ABC):

    @abstractmethod
    async def get_sports() -> VegasOddsResponse:
        """Returns a list of in-season sport objects. The sport key can be used as the sport parameter in get_current_odds"""
        raise NotImplementedError()

    @abstractmethod
    async def get_current_odds(
        sport: Optional[str] = "basketball_nba",
        regions: Optional[Union[List[str] | str]] = "us",
        markets: Optional[Union[List[str] | str]] = "h2h",
    ) -> VegasOddsResponse:
        """Returns a list of upcoming and live games with recent odds for a given sport, region and market"""
        raise NotImplementedError()

    @abstractmethod
    async def get_historical_odds(date: str) -> VegasOddsResponse:
        """Returns a snapshot of games with bookmaker odds for a given sport, region and market, at a given historical timestamp"""
        raise NotImplementedError()
