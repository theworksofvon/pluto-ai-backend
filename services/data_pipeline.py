from adapters import Adapters
from scripts.create_dataset import create_pluto_dataset
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
from typing import Optional, List, Dict
from logger import logger


class DataProcessor:
    def __init__(self):
        self.adapters = Adapters()
        self.data_path = Path("shared/data")
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.player_stats_file = self.data_path / "pluto_training_dataset_v1.csv"
        self.odds_file = self.data_path / "vegas_odds.csv"

    async def get_and_process_features(self, team: Optional[str] = None) -> None:
        """Update all data sources concurrently."""
        await asyncio.gather(self.update_player_stats(), self.update_vegas_odds())

    async def update_player_stats(
        self, players: Optional[List[str]] = None, current: Optional[bool] = True
    ) -> Optional[pd.DataFrame]:
        """
        Update the player stats dataset with new data since the last update.

        Args:
            players (list, optional): List of player names to update. If None, updates all active players.

        Returns:
            DataFrame: The updated dataset or None if no updates were made.
        """
        last_update_date = self._get_last_update_date(self.player_stats_file)
        
        logger.info(f"Last update date: {last_update_date}")

        active_players = (
            players
            if players is not None
            else self.adapters.nba_analytics.get_all_active_players(minimized=True)
        )

        current_year = datetime.now().year
        month = datetime.now().month
        if month >= 7:
            current_season = f"{current_year}-{str(current_year + 1)[-2:]}"
        else:
            current_season = f"{current_year - 1}-{str(current_year)[-2:]}"

        logger.info(
            f"Updating player stats from {last_update_date} to present for {len(active_players)} players"
        )
        if current:
            new_data = await create_pluto_dataset(
                players=active_players, seasons=[current_season]
            )
        else:
            new_data = await create_pluto_dataset(
                players=active_players
            )

        if last_update_date is not None and current:
            new_data = new_data[new_data["game_date_parsed"] > last_update_date]
        else:
            new_data = new_data

        if self.player_stats_file.exists() and not new_data.empty:
            existing_data = pd.read_csv(
                self.player_stats_file, parse_dates=["game_date_parsed"]
            )
            updated_data = pd.concat([existing_data, new_data], ignore_index=True)
            
            duplicate_columns = ["player_name", "game_date_parsed"]
            if "GAME_ID" in updated_data.columns:
                duplicate_columns.append("GAME_ID")
                
            updated_data.drop_duplicates(
                subset=duplicate_columns,
                keep="last",
                inplace=True,
            )
            
            updated_data.to_csv(self.player_stats_file, index=False)
            logger.info(
                f"Added {len(new_data)} new player stat records to main dataset"
            )
            return updated_data
        elif not new_data.empty:
            new_data.to_csv(self.player_stats_file, index=False)
            logger.info(
                f"Created new player stats dataset with {len(new_data)} records"
            )
            return new_data
        else:
            logger.info("No new player stat data to update")
            return None

    async def update_vegas_odds(self) -> None:
        """Update the Vegas odds dataset with current odds."""
        current_odds = await self.adapters.vegas_odds.get_current_odds()

        if not current_odds or current_odds.status_code != 200:
            logger.error("Failed to fetch current odds")
            return

        odds_df = pd.DataFrame(current_odds.response)
        odds_df["fetch_date"] = datetime.now()

        if self.odds_file.exists():
            existing_odds = pd.read_csv(self.odds_file, parse_dates=["fetch_date"])
            # Remove odds older than 7 days to keep file size manageable
            cutoff_date = datetime.now() - timedelta(days=7)
            existing_odds = existing_odds[existing_odds["fetch_date"] > cutoff_date]
            updated_odds = pd.concat([existing_odds, odds_df], ignore_index=True)
            updated_odds.to_csv(self.odds_file, index=False)
            logger.info(f"Updated odds data with {len(odds_df)} new records")
        else:
            odds_df.to_csv(self.odds_file, index=False)
            logger.info(f"Created new odds dataset with {len(odds_df)} records")

    def _get_last_update_date(self, file_path: Path) -> Optional[datetime]:
        """
        Return the most recent date in the dataset from the 'game_date_parsed' column.

        Args:
            file_path (Path): Path to the CSV file.

        Returns:
            datetime or None: Latest date or None if file doesn't exist or an error occurs.
        """
        if file_path.exists():
            try:
                df = pd.read_csv(file_path, parse_dates=["game_date_parsed"])
                return df["game_date_parsed"].max()
            except Exception as e:
                logger.error(f"Error reading dataset {file_path}: {e}")
        return None

    async def get_latest_data(
        self, player_name: Optional[str] = None, team_name: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Retrieve the latest combined data for predictions.

        Args:
            player_name (str, optional): Filter data by a specific player.
            team_name (str, optional): (Unused in current implementation)

        Returns:
            dict: Dictionary containing 'player_stats' and 'odds_data'.
        """
        if not self.player_stats_file.exists():
            await self.update_player_stats()

        logger.info(f"Reading player stats from {self.player_stats_file}")
        player_stats = pd.read_csv(
            self.player_stats_file, parse_dates=["game_date_parsed"]
        )

        if player_name:
            if player_name not in player_stats["player_name"].values:
                logger.info(
                    f"Player {player_name} not found in dataset. Updating stats..."
                )
                try:
                    await self.update_player_stats(players=[player_name])
                    player_stats = pd.read_csv(
                        self.player_stats_file, parse_dates=["game_date_parsed"]
                    )
                except Exception as e:
                    logger.error(f"Error updating player stats: {e}")
                    raise e

            player_stats = player_stats[player_stats["player_name"] == player_name]

        if not self.odds_file.exists():
            await self.update_vegas_odds()

        odds_data = pd.read_csv(self.odds_file, parse_dates=["fetch_date"])

        return {"player_stats": player_stats, "odds_data": odds_data}
