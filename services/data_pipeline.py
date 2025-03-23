from adapters import Adapters
from scripts.create_dataset import create_pluto_dataset
import pandas as pd
import os
from datetime import datetime, timedelta
import asyncio
import hashlib
from logger import logger


class DataProcessor:
    def __init__(self):
        self.adapters = Adapters()
        self.data_path = "shared/data/"
        self.player_stats_file = os.path.join(
            self.data_path, "pluto_training_dataset_v1.csv"
        )
        self.odds_file = os.path.join(self.data_path, "vegas_odds.csv")

    async def get_and_process_features(self, team=None):
        """Main method to update all data sources"""
        await asyncio.gather(self.update_player_stats(), self.update_vegas_odds())

    async def update_player_stats(self, players=None):
        """Update the player stats dataset with new data since last update

        Args:
            players (list, optional): List of player names to update. If provided,
                                     creates/updates a separate file for these specific players.

        Returns:
            DataFrame: The updated dataset or None if no updates were made
        """
        if players is not None:
            player_names_str = "_".join(sorted([p.replace(" ", "") for p in players]))
            player_hash = hashlib.md5(player_names_str.encode()).hexdigest()[:8]
            stats_file = os.path.join(self.data_path, f"player_stats_{player_hash}.csv")
            logger.info(
                f"Using player-specific file: {stats_file} for {len(players)} players"
            )
        else:
            stats_file = self.player_stats_file

        last_update_date = self._get_last_update_date(file_path=stats_file)

        if players is None:
            active_players = self.adapters.nba_analytics.get_all_active_players(
                minimized=True
            )
        else:
            active_players = players

        current_year = datetime.now().year
        month = datetime.now().month
        current_season = (
            f"{current_year}-{current_year+1 if month >= 7 else current_year-1 % 100}"
        )

        logger.info(
            f"Updating player stats from {last_update_date} to present for {len(active_players)} players"
        )

        new_data = await create_pluto_dataset(
            players=active_players, seasons=[current_season]
        )

        if last_update_date is not None:
            new_data = new_data[new_data["game_date_parsed"] > last_update_date]

        if os.path.exists(stats_file) and not new_data.empty:
            existing_data = pd.read_csv(stats_file, parse_dates=["game_date_parsed"])
            updated_data = pd.concat([existing_data, new_data], ignore_index=True)
            updated_data = updated_data.drop_duplicates(
                subset=["player_name", "game_date_parsed", "GAME_ID"], keep="last"
            )
            updated_data.to_csv(stats_file, index=False)
            logger.info(
                f"Added {len(new_data)} new player stat records to {os.path.basename(stats_file)}"
            )
            return updated_data
        elif not new_data.empty:
            new_data.to_csv(stats_file, index=False)
            logger.info(
                f"Created new player stats dataset {os.path.basename(stats_file)} with {len(new_data)} records"
            )
            return new_data
        else:
            logger.info(f"No new data to update in {os.path.basename(stats_file)}")
            return None

    async def update_vegas_odds(self):
        """Update the Vegas odds dataset with current odds"""
        current_odds = await self.adapters.vegas_odds.get_current_odds()

        if not current_odds or current_odds.status_code != 200:
            logger.error("Failed to fetch current odds")
            return

        odds_df = pd.DataFrame(current_odds.response)
        odds_df["fetch_date"] = datetime.now()

        if os.path.exists(self.odds_file):
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

    def _get_last_update_date(self, file_path=None):
        """Get the date of the most recent data point in the existing dataset

        Args:
            file_path (str, optional): Path to specific file to check. If None, uses default player_stats_file.

        Returns:
            datetime or None: The latest date in the dataset or None if file doesn't exist
        """
        if file_path is None:
            file_path = self.player_stats_file

        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, parse_dates=["game_date_parsed"])
                return df["game_date_parsed"].max()
            except Exception as e:
                logger.error(f"Error reading existing dataset {file_path}: {e}")
        return None

    async def get_latest_data(self, player_name=None, team_name=None):
        """Get the latest combined data for a player or team for predictions"""
        if not os.path.exists(self.player_stats_file):
            await self.update_player_stats()

        logger.info(f"Player stats file: {self.player_stats_file}")
        player_stats = pd.read_csv(self.player_stats_file)
        logger.info(f"Player stats: {player_stats}")

        if not os.path.exists(self.odds_file):
            await self.update_vegas_odds()

        odds_data = pd.read_csv(self.odds_file, parse_dates=["fetch_date"])

        if player_name:
            player_stats = player_stats[player_stats["player_name"] == player_name]
            logger.info(f"Player stats: {player_stats}")

        return {"player_stats": player_stats, "odds_data": odds_data}
