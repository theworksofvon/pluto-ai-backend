from .data_pipeline import DataProcessor
from adapters import Adapters
from logger import logger
from datetime import datetime, timedelta
from datetime import date as date_type
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
import os
import time  # For rate limiting

# Import specific nba_api endpoint for rosters
from nba_api.stats.endpoints import commonteamroster

# Define the path to the dataset relative to the project root
DATASET_DIR = "shared/data"
DATASET_FILENAME = "team_predictions_enhanced.csv"
DATASET_PATH = os.path.join(DATASET_DIR, DATASET_FILENAME)

# --- Constants ---
NBA_API_RATE_LIMIT_DELAY = 0.6  # Seconds to wait between API calls


class GamePredictionService:
    """
    Service responsible for preparing data for NBA game winner predictions.
    Uses a pre-calculated dataset for historical context and fetches live data using nba_api.
    """

    def __init__(self):
        # Adapters might still be used for things *not* covered by nba_api (like odds)
        self.adapters = Adapters()
        # Attempt to load the dataset during initialization
        self.team_data_df = self._load_dataset()
        # You might still need a DataProcessor for live API calls not covered by the dataset/adapters
        # self.data_processor = DataProcessor()

    def _load_dataset(self) -> pd.DataFrame:
        """Loads the pre-calculated team dataset."""
        try:
            logger.info(f"Loading team dataset from: {DATASET_PATH}")
            df = pd.read_csv(DATASET_PATH)
            # Convert GAME_DATE to datetime objects for proper comparison
            df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
            logger.info(f"Successfully loaded dataset with {len(df)} rows.")
            return df
        except FileNotFoundError:
            logger.error(
                f"Dataset file not found at {DATASET_PATH}. Service will lack historical context."
            )
            return pd.DataFrame()  # Return empty DataFrame if file not found
        except Exception as e:
            logger.error(f"Error loading dataset from {DATASET_PATH}: {e}")
            return pd.DataFrame()

    def _get_team_id_from_name(self, team_name: str) -> Optional[int]:
        """Helper to get team ID from name using the loaded dataset or nba_api."""
        if self.team_data_df.empty:
            logger.warning("Dataset empty, cannot map team name to ID reliably.")
            # Add fallback to nba_api static teams here if desired
            try:
                from nba_api.stats.static import teams

                nba_teams = teams.get_teams()
                team = next(
                    (t for t in nba_teams if t["abbreviation"] == team_name), None
                )
                if team:
                    logger.info(
                        f"Mapped {team_name} to ID {team['id']} via nba_api.stats.static.teams"
                    )
                    return team["id"]
                else:
                    logger.error(
                        f"Could not find team ID for {team_name} via fallback."
                    )
                    return None
            except Exception as e:
                logger.error(f"Error during nba_api static team lookup: {e}")
                return None

        # Find the first match for the team name abbreviation in the dataset
        match = self.team_data_df[self.team_data_df["TEAM_ABBREVIATION"] == team_name]
        if not match.empty:
            # Ensure the ID is a standard Python int
            team_id = match["TEAM_ID"].iloc[0]
            return int(team_id) if pd.notna(team_id) else None
        else:
            logger.warning(
                f"Could not find TEAM_ID for {team_name} in the dataset. Trying fallback."
            )
            # Fallback to static teams if not found in dataset
            return self._get_team_id_from_name_fallback(team_name)

    def _get_team_id_from_name_fallback(self, team_name: str) -> Optional[int]:
        """Fallback to get team ID using nba_api.stats.static.teams."""
        try:
            from nba_api.stats.static import teams

            nba_teams = teams.get_teams()
            team = next((t for t in nba_teams if t["abbreviation"] == team_name), None)
            if team:
                logger.info(
                    f"Mapped {team_name} to ID {team['id']} via nba_api.stats.static.teams (fallback)"
                )
                return team["id"]
            else:
                logger.error(f"Could not find team ID for {team_name} via fallback.")
                return None
        except Exception as e:
            logger.error(f"Error during nba_api static team lookup fallback: {e}")
            return None

    # --- Methods using nba_api (Synchronous) ---

    def _get_team_roster(self, team_id: int) -> List[Dict]:
        """Fetches the current team roster using nba_api."""
        if not team_id:
            return []
        logger.info(f"Fetching roster for team ID: {team_id}")
        try:
            roster_endpoint = commonteamroster.CommonTeamRoster(team_id=team_id)
            time.sleep(NBA_API_RATE_LIMIT_DELAY)
            roster_df = roster_endpoint.get_data_frames()[0]
            # Convert DataFrame to list of dictionaries
            roster_list = roster_df.to_dict("records")
            logger.info(
                f"Successfully fetched roster with {len(roster_list)} players for team ID: {team_id}"
            )
            return roster_list
        except Exception as e:
            logger.error(
                f"Error fetching roster for team ID {team_id} from nba_api: {e}"
            )
            return []

    def _get_team_injuries(self, team_id: int) -> List[Dict]:
        """
        Placeholder for fetching team injuries. Returns an empty list.
        Implement web scraping or use a third-party API here for actual injury data.
        """
        # TODO: Implement actual injury data fetching (e.g., web scraping, external API)
        # logger.warning(f"Injury data fetching not implemented for team ID: {team_id}. Returning empty list.")
        return []  # Return empty list to avoid breaking the flow

    def _get_game_odds(
        self, home_team_abbr: str, away_team_abbr: str, game_id: Optional[str]
    ) -> Dict:
        """
        Placeholder for fetching game odds.
        NOTE: nba_api does NOT provide betting odds.
        This method returns a status indicating data is not available.
        """
        logger.warning(
            f"Betting odds data not available via standard nba_api for {home_team_abbr} vs {away_team_abbr}. Returning 'not_available'. Use a dedicated odds API/adapter."
        )
        # In a real implementation, you would call an odds provider API via an adapter.
        # vegas_factors = await self.adapters.odds_provider.get_game_odds(...)
        return {"status": "not_available"}

    async def prepare_game_prediction_context(
        self,
        home_team_abbr: str,  # Expecting abbreviation now, consistent with dataset
        away_team_abbr: str,
        game_id: Optional[str] = None,
        prediction_date: Optional[
            datetime
        ] = None,  # Date for which prediction is needed
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Prepare all relevant context and data for a game winner prediction,
        primarily using the pre-calculated dataset and fetching live data via nba_api.

        Args:
            home_team_abbr: Abbreviation of the home team (e.g., 'LAL')
            away_team_abbr: Abbreviation of the away team (e.g., 'DEN')
            game_id: Specific game ID if available
            prediction_date: The date for which the prediction is being made (defaults to today)

        Returns:
            Dict containing all relevant data for making a game winner prediction
        """
        logger.info(
            f"Preparing game prediction context for {home_team_abbr} vs {away_team_abbr}"
        )

        if self.team_data_df.empty:
            logger.error("Team dataset not loaded. Cannot provide historical context.")
            # Optionally, allow proceeding without historical data if desired
            # return {"status": "error", "message": "Team dataset not loaded.", "data": None}

        pred_date = prediction_date or datetime.now()
        effective_date = pred_date.date()

        # Get team IDs
        home_team_id = self._get_team_id_from_name(home_team_abbr)
        away_team_id = self._get_team_id_from_name(away_team_abbr)

        if not home_team_id or not away_team_id:
            message = (
                f"Could not resolve Team IDs for {home_team_abbr} or {away_team_abbr}."
            )
            logger.error(message)
            # If dataset loaded, maybe IDs exist but name lookup failed? Handle appropriately.
            return {"status": "error", "message": message, "data": None}

        # Initialize context dictionaries
        home_context_dict = {}
        away_context_dict = {}
        home_performance = {}
        away_performance = {}
        h2h_context = {}
        adv_metrics = {}
        rest_and_b2b = {}
        streaks = {}

        # --- Try to Extract Historical Context from Dataset ---
        if not self.team_data_df.empty:
            home_latest_context = (
                self.team_data_df[
                    (self.team_data_df["TEAM_ID"] == home_team_id)
                    & (self.team_data_df["GAME_DATE"].dt.date < effective_date)
                ]
                .sort_values(by="GAME_DATE", ascending=False)
                .iloc[0:1]
            )

            away_latest_context = (
                self.team_data_df[
                    (self.team_data_df["TEAM_ID"] == away_team_id)
                    & (self.team_data_df["GAME_DATE"].dt.date < effective_date)
                ]
                .sort_values(by="GAME_DATE", ascending=False)
                .iloc[0:1]
            )

            if home_latest_context.empty or away_latest_context.empty:
                logger.warning(
                    f"Insufficient historical data found in dataset for {home_team_abbr} or {away_team_abbr} before {effective_date}. Context will be limited."
                )
            else:
                home_context_dict = home_latest_context.iloc[0].to_dict()
                away_context_dict = away_latest_context.iloc[0].to_dict()

                # Extract features if context was found
                home_performance = self._extract_team_performance(
                    home_context_dict, is_opponent=False
                )
                away_performance = self._extract_team_performance(
                    away_context_dict, is_opponent=False
                )
                h2h_context = self._extract_h2h_performance(
                    home_context_dict, int(away_team_id)
                )
                adv_metrics = self._extract_advanced_metrics(
                    home_context_dict, away_context_dict
                )
                rest_and_b2b = self._extract_rest_and_b2b(
                    home_context_dict, away_context_dict
                )
                streaks = self._extract_streaks(home_context_dict, away_context_dict)
        else:
            logger.warning(
                "Proceeding without historical data as dataset was not loaded."
            )

        # --- Fetch Live / External Data ---

        # Use internal methods calling nba_api (synchronous)
        home_roster = self._get_team_roster(int(home_team_id))
        away_roster = self._get_team_roster(int(away_team_id))
        home_injuries = self._get_team_injuries(int(home_team_id))  # Placeholder
        away_injuries = self._get_team_injuries(int(away_team_id))  # Placeholder
        vegas_factors = self._get_game_odds(
            home_team_abbr, away_team_abbr, game_id
        )  # Placeholder

        # Calculate Injury Impact using live data (even if placeholder injuries)
        injury_impact = self._calculate_injury_impact(
            home_injuries, away_injuries, home_roster, away_roster
        )

        # --- Combine and Format Context ---
        final_context = {
            "status": "success",
            "home_team": home_team_abbr,
            "away_team": away_team_abbr,
            "game_id": game_id,
            "game_date": pred_date.date(),  # Date for which prediction is made
            "timestamp": datetime.now().isoformat(),
            "team_stats": {  # Based on dataset averages leading into the game (or empty if no history)
                "home": home_performance,
                "away": away_performance,
            },
            "additional_context": additional_context,
            "head_to_head": h2h_context,  # Based on dataset H2H win pct (or empty)
            "vegas_factors": vegas_factors,  # Live data (placeholder)
            "advanced_metrics": {  # Combining multiple sources
                **adv_metrics,  # From dataset (Ratings)
                **rest_and_b2b,  # From dataset
                **streaks,  # From dataset
                **injury_impact,  # Calculated from live data
            },
            "live_data": {  # Include fetched live data
                "home_roster": home_roster,
                "away_roster": away_roster,
                "home_injuries": home_injuries,  # Placeholder
                "away_injuries": away_injuries,  # Placeholder
            },
        }

        # Clean up NaN values for JSON serialization if needed
        final_context = self._clean_nan(final_context)

        return final_context

    def _extract_team_performance(self, context_dict: Dict, is_opponent: bool) -> Dict:
        """Extracts team performance metrics from the dataset context row."""
        prefix = "OPP_" if is_opponent else ""
        # Ensure keys exist before formatting record string
        wins = context_dict.get(f"{prefix}SEASON_WINS_BEFORE", "N/A")
        losses = context_dict.get(f"{prefix}SEASON_LOSSES_BEFORE", "N/A")
        record = f"{wins}-{losses}" if wins != "N/A" and losses != "N/A" else "N/A"

        return {
            "record": record,
            "win_pct": context_dict.get(f"{prefix}SEASON_WIN_PCT", np.nan),
            "home_record": "N/A",
            "away_record": "N/A",
            "last_5_avg_pts": context_dict.get(f"{prefix}AVG_PTS_L5", np.nan),
            "last_10_avg_pts": context_dict.get(f"{prefix}AVG_PTS_L10", np.nan),
            "last_5_avg_plus_minus": context_dict.get(
                f"{prefix}AVG_PLUS_MINUS_L5", np.nan
            ),
            "last_10_avg_plus_minus": context_dict.get(
                f"{prefix}AVG_PLUS_MINUS_L10", np.nan
            ),
            "offensive_rating": context_dict.get(
                f"{prefix}SEASON_AVG_OFF_RTG_APPROX", np.nan
            ),
            "defensive_rating": context_dict.get(
                f"{prefix}SEASON_AVG_DEF_RTG_APPROX", np.nan
            ),
            "net_rating": context_dict.get(f"{prefix}SEASON_AVG_PLUS_MINUS", np.nan),
        }

    def _extract_h2h_performance(
        self, home_context_dict: Dict, away_team_id: int
    ) -> Dict:
        """Extracts H2H performance if the opponent in the context matches."""
        h2h_win_pct = np.nan  # Default to NaN if not applicable
        opponent_in_context = home_context_dict.get("OPP_TEAM_ID")

        # Ensure away_team_id is comparable (e.g., both int or float)
        if (
            opponent_in_context is not None
            and pd.notna(opponent_in_context)
            and opponent_in_context == float(away_team_id)
        ):
            h2h_win_pct = home_context_dict.get("SEASON_H2H_WIN_PCT", np.nan)
        elif (
            opponent_in_context is not None
        ):  # Log only if opponent ID was present but didn't match
            logger.warning(
                f"Latest context opponent ({int(opponent_in_context) if pd.notna(opponent_in_context) else 'N/A'}) doesn't match current opponent ({away_team_id}). H2H may not reflect direct matchup history."
            )

        return {
            "home_team_h2h_win_pct_vs_away": h2h_win_pct,
            "away_team_h2h_win_pct_vs_home": (
                1.0 - h2h_win_pct if pd.notna(h2h_win_pct) else np.nan
            ),
        }

    def _extract_advanced_metrics(self, home_context: Dict, away_context: Dict) -> Dict:
        """Extracts pre-calculated advanced metrics. SOS, Ratings etc."""
        # Note: The dataset doesn't explicitly calculate SOS or consistency/momentum scores.
        # We are extracting the available average ratings here.
        return {
            "home_season_avg_off_rtg": home_context.get(
                "SEASON_AVG_OFF_RTG_APPROX", np.nan
            ),
            "home_season_avg_def_rtg": home_context.get(
                "SEASON_AVG_DEF_RTG_APPROX", np.nan
            ),
            "away_season_avg_off_rtg": away_context.get(
                "SEASON_AVG_OFF_RTG_APPROX", np.nan
            ),
            "away_season_avg_def_rtg": away_context.get(
                "SEASON_AVG_DEF_RTG_APPROX", np.nan
            ),
            "home_l10_avg_off_rtg": home_context.get("AVG_OFF_RTG_APPROX_L10", np.nan),
            "home_l10_avg_def_rtg": home_context.get("AVG_DEF_RTG_APPROX_L10", np.nan),
            "away_l10_avg_off_rtg": away_context.get("AVG_OFF_RTG_APPROX_L10", np.nan),
            "away_l10_avg_def_rtg": away_context.get("AVG_DEF_RTG_APPROX_L10", np.nan),
        }

    def _extract_rest_and_b2b(self, home_context: Dict, away_context: Dict) -> Dict:
        """Extracts rest days and B2B status."""
        return {
            "home_rest_days": home_context.get("REST_DAYS", np.nan),
            "away_rest_days": away_context.get("REST_DAYS", np.nan),
            "home_is_b2b": home_context.get("B2B", np.nan),
            "away_is_b2b": away_context.get("B2B", np.nan),
        }

    def _extract_streaks(self, home_context: Dict, away_context: Dict) -> Dict:
        """Extracts win/loss streaks."""
        return {
            "home_win_streak": home_context.get("WIN_STREAK", 0),
            "home_loss_streak": home_context.get("LOSS_STREAK", 0),
            "away_win_streak": away_context.get("WIN_STREAK", 0),
            "away_loss_streak": away_context.get("LOSS_STREAK", 0),
        }

    # --- Methods requiring LIVE data or Calculations ---

    def _calculate_injury_impact(
        self,
        home_injuries: List[Dict],
        away_injuries: List[Dict],
        home_roster: List[Dict],
        away_roster: List[Dict],
    ) -> Dict[str, Any]:
        """
        Calculate the impact of current injuries on both teams.
        Requires live injury reports and potentially roster data with usage stats (e.g., MPG).
        Placeholder implementation - needs actual roster data with minutes/usage.
        """
        home_impact_score = self._evaluate_single_team_injury_impact(
            home_injuries, home_roster
        )
        away_impact_score = self._evaluate_single_team_injury_impact(
            away_injuries, away_roster
        )

        return {
            "home_injury_impact": home_impact_score,
            "away_injury_impact": away_impact_score,
        }

    def _evaluate_single_team_injury_impact(
        self, injuries: List[Dict], roster: List[Dict]
    ) -> float:
        """Evaluates injury impact for one team. Placeholder logic."""
        if not injuries:
            return 0.0  # No impact if no injuries

        # --- Placeholder Logic ---
        # A more robust approach would:
        # 1. Get player usage/minutes (e.g., VORP, WAR, MPG) from roster or another source.
        # 2. Sum the usage metric for injured players.
        # 3. Normalize this sum (e.g., as a % of total team usage).

        # Simple placeholder: count number of injured players as % of roster size
        roster_size = len(roster) if roster else 15  # Default estimate
        num_injured = len(injuries)

        if roster_size == 0:
            return 0.0

        # Return fraction of roster injured (capped at 1.0)
        impact = min(num_injured / roster_size, 1.0)
        logger.debug(
            f"Calculated injury impact (placeholder): {impact:.2f} ({num_injured}/{roster_size})"
        )
        return impact

    # Optional: Keep a simple model prediction based on ratings extracted
    def _get_game_model_prediction(
        self, home_perf: Dict, away_perf: Dict
    ) -> Optional[str]:
        """Basic prediction based on extracted season net ratings."""
        try:
            # Ensure values exist and are float convertible
            home_nr = home_perf.get("net_rating")
            away_nr = away_perf.get("net_rating")
            if (
                home_nr is None
                or away_nr is None
                or pd.isna(home_nr)
                or pd.isna(away_nr)
            ):
                logger.warning("Net rating missing for basic model prediction.")
                return None

            home_net_rating = float(home_nr)
            away_net_rating = float(away_nr)

            home_advantage = 2.5
            adjusted_home_rating = home_net_rating + home_advantage

            if adjusted_home_rating > away_net_rating:
                return "home_team"
            elif adjusted_home_rating < away_net_rating:
                return "away_team"
            else:
                return "toss_up"
        except (ValueError, TypeError):
            logger.warning("Could not parse net ratings for basic model prediction.")
            return None

    def _clean_nan(self, data: Any) -> Any:
        """Recursively replace NaN values with None for JSON compatibility."""
        if isinstance(data, dict):
            return {k: self._clean_nan(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._clean_nan(item) for item in data]
        elif isinstance(data, float) and np.isnan(data):
            return None
        # Handle pandas Timestamps and datetime.date objects
        elif isinstance(data, (pd.Timestamp, date_type)):
            return data.isoformat()
        # Handle potential numpy types that aren't JSON serializable
        elif isinstance(
            data,
            (
                np.int_,
                np.intc,
                np.intp,
                np.int8,
                np.int16,
                np.int32,
                np.int64,
                np.uint8,
                np.uint16,
                np.uint32,
                np.uint64,
            ),
        ):
            return int(data)
        elif isinstance(data, (np.float_, np.float16, np.float32, np.float64)):
            return float(data) if not np.isnan(data) else None
        elif isinstance(data, (np.ndarray,)):
            return self._clean_nan(data.tolist())  # Convert arrays to lists
        elif isinstance(data, (np.bool_)):
            return bool(data)
        return data
