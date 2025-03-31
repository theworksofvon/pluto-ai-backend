from typing import Optional
from logger import logger

_TEAM_ID_TO_NAME = {
    "1610612737": "Atlanta Hawks",
    "1610612738": "Boston Celtics",
    "1610612751": "Brooklyn Nets",
    "1610612766": "Charlotte Hornets",
    "1610612741": "Chicago Bulls",
    "1610612739": "Cleveland Cavaliers",
    "1610612742": "Dallas Mavericks",
    "1610612743": "Denver Nuggets",
    "1610612765": "Detroit Pistons",
    "1610612744": "Golden State Warriors",
    "1610612745": "Houston Rockets",
    "1610612754": "Indiana Pacers",
    "1610612746": "LA Clippers",
    "1610612747": "Los Angeles Lakers",
    "1610612763": "Memphis Grizzlies",
    "1610612748": "Miami Heat",
    "1610612749": "Milwaukee Bucks",
    "1610612750": "Minnesota Timberwolves",
    "1610612740": "New Orleans Pelicans",
    "1610612752": "New York Knicks",
    "1610612760": "Oklahoma City Thunder",
    "1610612753": "Orlando Magic",
    "1610612755": "Philadelphia 76ers",
    "1610612756": "Phoenix Suns",
    "1610612757": "Portland Trail Blazers",
    "1610612758": "Sacramento Kings",
    "1610612759": "San Antonio Spurs",
    "1610612761": "Toronto Raptors",
    "1610612762": "Utah Jazz",
    "1610612764": "Washington Wizards",
}

_TEAM_ID_TO_ABBR = {
    "1610612737": "ATL",
    "1610612738": "BOS",
    "1610612751": "BKN",
    "1610612766": "CHA",
    "1610612741": "CHI",
    "1610612739": "CLE",
    "1610612742": "DAL",
    "1610612743": "DEN",
    "1610612765": "DET",
    "1610612744": "GSW",
    "1610612745": "HOU",
    "1610612754": "IND",
    "1610612746": "LAC",
    "1610612747": "LAL",
    "1610612763": "MEM",
    "1610612748": "MIA",
    "1610612749": "MIL",
    "1610612750": "MIN",
    "1610612740": "NOP",
    "1610612752": "NYK",
    "1610612760": "OKC",
    "1610612753": "ORL",
    "1610612755": "PHI",
    "1610612756": "PHX",
    "1610612757": "POR",
    "1610612758": "SAC",
    "1610612759": "SAS",
    "1610612761": "TOR",
    "1610612762": "UTA",
    "1610612764": "WAS",
}

_TEAM_ABBR_TO_NAME = {v: _TEAM_ID_TO_NAME[k] for k, v in _TEAM_ID_TO_ABBR.items() if k in _TEAM_ID_TO_NAME}


def get_team_name_from_id(team_id: str) -> Optional[str]:
    """
    Convert a team ID to its team name.
    """
    try:
        team_name = _TEAM_ID_TO_NAME.get(str(team_id))
        return team_name
    except Exception as e:
        logger.error(f"Error converting team ID {team_id} to name: {e}")
        return None

def get_team_abbr_from_id(team_id: str) -> Optional[str]:
    """
    Convert a team ID to its team abbreviation.
    """
    try:
        team_abbr = _TEAM_ID_TO_ABBR.get(str(team_id))
        return team_abbr
    except Exception as e:
        logger.error(f"Error converting team ID {team_id} to abbreviation: {e}")
        return None

def get_team_name_from_abbr(team_abbr: str) -> Optional[str]:
    """
    Convert a team abbreviation to its full team name.
    """
    try:
        team_name = _TEAM_ABBR_TO_NAME.get(team_abbr.upper())
        return team_name
    except Exception as e:
        logger.error(f"Error converting team abbreviation {team_abbr} to name: {e}")
        return None
