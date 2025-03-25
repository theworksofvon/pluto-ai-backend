import aiohttp
from collections import defaultdict
from typing import List, Dict, Set, Optional, Any
from logger import logger


class PrizePicksAdapter:
    def __init__(self, base_url: str = "https://api.prizepicks.com") -> None:
        self.base_url = base_url
        self.headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://prizepicks.com",
            "Referer": "https://prizepicks.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ),
            "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        }

    async def fetch_data(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
        """
        Fetch data from a given endpoint with the provided parameters.
        """
        url = f"{self.base_url}{endpoint}"
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    logger.info(f"API Response status: {response.status}")
                    logger.info(
                        f"API Response data keys: {data.keys() if data else 'No data'}"
                    )
                    if data and "data" in data:
                        logger.info(
                            f"Number of projections in response: {len(data['data'])}"
                        )
                    return data
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching data from {url}: {str(e)}")
            return None

    def parse_players(self, data: Dict) -> Dict[str, Dict]:
        """
        Parse the player information from the API response.
        """
        players = {}
        for item in data.get("included", []):
            if item.get("type") == "new_player":
                attr = item.get("attributes", {})
                players[item.get("id")] = {
                    "name": attr.get("name"),
                    "team": attr.get("team"),
                    "position": attr.get("position"),
                    "team_id": attr.get("team_id"),
                    "image_url": attr.get("image_url"),
                }
        logger.info(f"Parsed {len(players)} players from data")
        return players

    def parse_props(
        self,
        data: Dict,
        players: Dict[str, Dict],
        stat_types: Set[str],
        player_name: Optional[str] = None,
    ) -> List[Dict]:
        """
        Parse NBA props from the API response and filter by stat types and optional player name.
        """
        nba_props = []
        logger.info(f"Searching for player: {player_name}")
        logger.info(f"Available players: {[p.get('name') for p in players.values()]}")

        for prop in data.get("data", []):
            if prop.get("type") != "projection":
                continue

            attrs = prop.get("attributes", {})
            stat_type = attrs.get("stat_type")
            if stat_type not in stat_types:
                continue

            player_id = (
                prop.get("relationships", {})
                .get("new_player", {})
                .get("data", {})
                .get("id")
            )
            player_info = players.get(player_id, {})

            current_player_name = player_info.get("name", "")
            logger.info(
                f"Checking player: {current_player_name} against search term: {player_name}"
            )
            logger.info(
                f"Comparison: '{player_name.lower()}' in '{current_player_name.lower()}' = {player_name.lower() in current_player_name.lower()}"
            )

            if player_name and player_name.lower() not in current_player_name.lower():
                logger.info(f"Skipping {current_player_name} - name doesn't match")
                continue

            logger.info(f"Keeping prop for {current_player_name}")
            prop_data = {
                "player_name": current_player_name,
                "team": player_info.get("team"),
                "position": player_info.get("position"),
                "stat_type": stat_type,
                "line_score": attrs.get("line_score"),
                "description": attrs.get("description"),
                "game_time": attrs.get("game_time"),
                "opponent": attrs.get("opponent"),
                "is_flash_sale": bool(attrs.get("flash_sale_line_score")),
                "flash_sale_line_score": attrs.get("flash_sale_line_score"),
                "player_image_url": player_info.get("image_url"),
            }
            nba_props.append(prop_data)

        logger.info(
            f"Found {len(nba_props)} NBA props for stat types: {stat_types} and player: {player_name}"
            if player_name
            else ""
        )
        return nba_props

    async def get_nba_lines(
        self, stat_types: Set[str] = {"Points"}, player_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Gets NBA lines from PrizePicks API for specified stat types and player.
        """
        params = {"league_id": 7}  # NBA league_id is 7
        data = await self.fetch_data("/projections", params)
        if not data:
            return []

        players = self.parse_players(data=data)
        nba_props = self.parse_props(
            data=data, players=players, stat_types=stat_types, player_name=player_name
        )
        return nba_props

    def summarize_available_props(self, nba_props: List[Dict]) -> None:
        """
        Summarizes all available prop types and shows example lines for each type.
        """
        stat_types = set()
        player_props = defaultdict(list)

        for prop in nba_props:
            stat_types.add(prop["stat_type"])
            player_props[prop["player_name"]].append(
                {
                    "stat_type": prop["stat_type"],
                    "line_score": prop["line_score"],
                    "opponent": prop["opponent"],
                }
            )

        logger.info("\nAvailable stat types:")
        for stat_type in sorted(stat_types):
            logger.info(f"- {stat_type}")

        logger.info("\nExample props for some players:")
        for count, (player, props) in enumerate(player_props.items()):
            if count >= 3:
                break
            logger.info(f"\n{player} vs {props[0]['opponent']}:")
            for prop in props:
                logger.info(f"- {prop['stat_type']}: {prop['line_score']}")
