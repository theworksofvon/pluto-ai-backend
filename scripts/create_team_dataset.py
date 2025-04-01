import pandas as pd
from nba_api.stats.endpoints import leaguegamelog
from nba_api.stats.static import teams
import time
import logging
import os
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Constants ---
RATE_LIMIT_DELAY = 0.6  # Seconds to wait between API calls
ROLLING_WINDOW_SIZES = [5, 10]  # Calculate rolling averages for last 5 and 10 games
MIN_GAMES_FOR_ROLLING = 1  # Minimum games needed for rolling calculation


def _get_team_id(abbreviation):
    """Helper to get team ID from abbreviation."""
    try:
        nba_teams = teams.get_teams()
        team = next((t for t in nba_teams if t["abbreviation"] == abbreviation), None)
        return team["id"] if team else None
    except Exception as e:
        logging.error(f"Error fetching team ID for {abbreviation}: {e}")
        return None


def _fetch_season_gamelogs(season):
    """Fetches all regular season game logs for a given season."""
    logging.info(f"Fetching game logs for season: {season}")
    try:
        gamelog = leaguegamelog.LeagueGameLog(
            season=season, season_type_all_star="Regular Season"
        )
        time.sleep(RATE_LIMIT_DELAY)
        df = gamelog.get_data_frames()[0]
        if df.empty:
            logging.warning(f"No game logs found for season {season}.")
            return pd.DataFrame()
        logging.info(f"Successfully fetched {len(df)} game log entries for {season}")
        df["SEASON"] = season  # Add season identifier
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], format="%Y-%m-%d")
        # Sort by date needed for correct calculations later
        df = df.sort_values(by="GAME_DATE")
        return df
    except Exception as e:
        logging.error(f"Error fetching game logs for season {season}: {e}")
        return pd.DataFrame()


def _calculate_initial_metrics(df):
    """Calculates initial game-level metrics like approximate possessions and offensive rating."""
    logging.info("Calculating initial game metrics (Possessions, Offensive Rating)...")
    # Approximate possessions: FGA + 0.44*FTA + TOV - OREB (if available, else just use TOV)
    # LeagueGameLog doesn't typically have OREB directly per team entry, TOV is team turnovers committed.
    df["POSS_APPROX"] = df["FGA"] + 0.44 * df["FTA"] + df["TOV"]
    df["OFF_RTG_APPROX"] = np.where(
        df["POSS_APPROX"] > 0, (df["PTS"] / df["POSS_APPROX"]) * 100, 0
    )
    # Defensive Rating needs opponent points/team possessions, calculated after merging opponent data.
    df["DEF_RTG_APPROX"] = np.nan  # Initialize column
    logging.info("Finished calculating initial game metrics.")
    return df


def _calculate_streaks(series):
    """Helper function to calculate win/loss streaks."""
    streak = 0
    streaks = []
    for x in series:
        if x == 1:  # Win
            streak = max(1, streak + 1)
        else:  # Loss
            streak = min(-1, streak - 1)
        streaks.append(streak)
    # Separate into win (positive) and loss (negative) streaks
    win_streak = [max(0, s) for s in streaks]
    loss_streak = [max(0, -s) for s in streaks]
    return win_streak, loss_streak


def _calculate_team_features(full_log_df):
    """
    Calculates rolling, cumulative season stats, rest days, B2B flags, and streaks for all teams.
    Crucially shifts data to prevent leakage (uses data *before* the current game).
    """
    logging.info("Calculating team features (rolling, cumulative, rest, streaks)...")
    all_team_features = []

    # Ensure sorting for correct shift and rolling calculations
    full_log_df = full_log_df.sort_values(by=["SEASON", "TEAM_ID", "GAME_DATE"])

    # Stats for rolling/cumulative calculations
    stats_cols = [
        "PTS",
        "AST",
        "REB",
        "FG_PCT",
        "FT_PCT",
        "FG3_PCT",
        "PLUS_MINUS",
        "POSS_APPROX",
        "OFF_RTG_APPROX",
    ]
    # Note: DEF_RTG_APPROX averages are calculated later after opponent merge

    # Group by season and team
    grouped = full_log_df.groupby(["SEASON", "TEAM_ID"])

    for (season, team_id), group in grouped:
        team_df = group.copy().sort_values(by="GAME_DATE")  # Ensure chronological order

        # --- Shifted Data (Exclude current game from calculations) ---
        shifted_df = team_df.shift(1)

        # --- Rolling Stats ---
        for window in ROLLING_WINDOW_SIZES:
            rolling_group = shifted_df.rolling(
                window=window, min_periods=MIN_GAMES_FOR_ROLLING
            )
            for col in stats_cols:
                if col in team_df.columns:
                    team_df[f"AVG_{col}_L{window}"] = rolling_group[col].mean()
                else:
                    team_df[f"AVG_{col}_L{window}"] = np.nan

        # --- Cumulative Season Stats (Shifted) ---
        team_df["SEASON_WINS_BEFORE"] = (shifted_df["WL"] == "W").cumsum()
        team_df["SEASON_LOSSES_BEFORE"] = (shifted_df["WL"] == "L").cumsum()
        team_df["SEASON_GAMES_PLAYED"] = (
            team_df["SEASON_WINS_BEFORE"] + team_df["SEASON_LOSSES_BEFORE"]
        )
        team_df["SEASON_WIN_PCT"] = np.where(
            team_df["SEASON_GAMES_PLAYED"] > 0,
            team_df["SEASON_WINS_BEFORE"] / team_df["SEASON_GAMES_PLAYED"],
            0,
        )

        # Cumulative averages for stats
        for col in stats_cols:
            if col in team_df.columns:
                cumulative_sum = shifted_df[col].cumsum()
                team_df[f"SEASON_AVG_{col}"] = np.where(
                    team_df["SEASON_GAMES_PLAYED"] > 0,
                    cumulative_sum / team_df["SEASON_GAMES_PLAYED"],
                    np.nan,  # Use NaN before first game played
                )
            else:
                team_df[f"SEASON_AVG_{col}"] = np.nan

        # --- Rest Days & B2B ---
        team_df["REST_DAYS"] = (
            team_df["GAME_DATE"] - shifted_df["GAME_DATE"]
        ).dt.days - 1
        # Fill NaN for the first game of the season for that team
        team_df["REST_DAYS"] = team_df["REST_DAYS"].fillna(
            10
        )  # Assume ample rest before first game
        team_df["REST_DAYS"] = team_df["REST_DAYS"].astype(int)
        team_df.loc[team_df["REST_DAYS"] < 0, "REST_DAYS"] = 0  # Handle data errors
        team_df["B2B"] = (team_df["REST_DAYS"] == 0).astype(int)

        # --- Streaks ---
        # Calculate streaks based on past games WL (shifted)
        shifted_wl_numeric = (
            shifted_df["WL"].map({"W": 1, "L": 0}).fillna(0)
        )  # Use 0 for first game
        win_s, loss_s = _calculate_streaks(shifted_wl_numeric)
        team_df["WIN_STREAK"] = win_s
        team_df["LOSS_STREAK"] = loss_s

        all_team_features.append(team_df)

    if not all_team_features:
        logging.error("No team features were calculated.")
        return pd.DataFrame()

    combined_df = pd.concat(all_team_features).reset_index(drop=True)
    logging.info("Finished calculating base team features.")
    return combined_df


def _add_opponent_h2h_and_final_metrics(df_with_features):
    """
    Merges opponent data, calculates season H2H stats, finalizes Def Rtg,
    and calculates rolling/season averages for Def Rtg.
    """
    logging.info("Adding opponent data, H2H stats, and finalizing metrics...")
    processed_games = []

    # ===> Remove setting the index here <===
    # # Use SEASON, GAME_ID, TEAM_ID as a unique key for lookups
    # try:
    #     # Ensure necessary columns exist before setting index
    #     required_cols = ['SEASON', 'GAME_ID', 'TEAM_ID']
    #     if not all(col in df_with_features.columns for col in required_cols):
    #         missing = [col for col in required_cols if col not in df_with_features.columns]
    #         logging.error(f"Input DataFrame is missing required columns for indexing: {missing}. Aborting merge.")
    #         return pd.DataFrame()

    #     df_with_features_indexed = df_with_features.set_index(['SEASON', 'GAME_ID', 'TEAM_ID'])
    # except KeyError as e:
    #     logging.error(f"Failed to set index on df_with_features. Error: {e}")
    #     logging.error(f"Columns present: {df_with_features.columns.tolist()}")
    #     return pd.DataFrame()

    # Get unique games directly from the DataFrame columns
    if not all(col in df_with_features.columns for col in ["SEASON", "GAME_ID"]):
        logging.error(
            "DataFrame missing SEASON or GAME_ID columns. Cannot process games."
        )
        return pd.DataFrame()

    unique_games = (
        df_with_features[["SEASON", "GAME_ID"]].drop_duplicates().values.tolist()
    )

    feature_cols_to_copy = [
        col
        for col in df_with_features.columns
        if col.startswith("AVG_")
        or col.startswith("SEASON_")
        or col
        in [
            "REST_DAYS",
            "B2B",
            "WIN_STREAK",
            "LOSS_STREAK",
            "POSS_APPROX",
            "OFF_RTG_APPROX",
        ]
    ]
    # Exclude DEF_RTG_APPROX for now

    # Use the input DataFrame directly for H2H lookups as well
    temp_df_for_h2h = df_with_features

    for season, game_id in unique_games:
        try:
            # ===> Filter DataFrame directly instead of using .loc on index <===
            game_rows = df_with_features[
                (df_with_features["SEASON"] == season)
                & (df_with_features["GAME_ID"] == game_id)
            ]

            if len(game_rows) != 2:
                logging.warning(
                    f"Season {season}, Game ID {game_id} does not have exactly two teams in DataFrame. Found {len(game_rows)}. Skipping."
                )
                continue

            # ===> Convert rows to dictionaries <===
            # .iloc[0] and .iloc[1] are safe here because we checked len == 2
            team1_row_dict = game_rows.iloc[0].to_dict()
            team2_row_dict = game_rows.iloc[1].to_dict()

            # Get IDs from the dictionaries
            team1_id = team1_row_dict.get("TEAM_ID")
            team2_id = team2_row_dict.get("TEAM_ID")

            if pd.isna(team1_id) or pd.isna(team2_id):
                logging.warning(
                    f"Missing TEAM_ID in one or both rows for game {season}, {game_id}. Skipping."
                )
                continue

            # ===> Remove the index structure check - no longer needed <===
            # if not (isinstance(team1_idx, tuple) and len(team1_idx) == 3 and
            #         isinstance(team2_idx, tuple) and len(team2_idx) == 3):
            #     logging.warning(f"Invalid index structure found for game {season}, {game_id}. Indices: {team1_idx}, {team2_idx}. Skipping.")
            #     continue

            # team1_id = team1_idx[2]
            # team2_id = team2_idx[2]

            # team1_row_dict = game_rows.loc[team1_idx].to_dict() # Now done above
            # team2_row_dict = game_rows.loc[team2_idx].to_dict() # Now done above

            # --- Merge Opponent Features ---
            for col in feature_cols_to_copy:
                team1_row_dict[f"OPP_{col}"] = team2_row_dict.get(col, np.nan)
                team2_row_dict[f"OPP_{col}"] = team1_row_dict.get(col, np.nan)

            # Copy opponent identifiers
            team1_row_dict["OPP_TEAM_ID"] = team2_id
            team1_row_dict["OPP_TEAM_ABBREVIATION"] = team2_row_dict.get(
                "TEAM_ABBREVIATION", "N/A"
            )  # Use .get for safety
            team2_row_dict["OPP_TEAM_ID"] = team1_id
            team2_row_dict["OPP_TEAM_ABBREVIATION"] = team1_row_dict.get(
                "TEAM_ABBREVIATION", "N/A"
            )  # Use .get for safety

            # --- Finalize Defensive Rating (Game Level) ---
            opp1_pts = team2_row_dict.get("PTS", np.nan)  # Use .get for safety
            opp2_pts = team1_row_dict.get("PTS", np.nan)  # Use .get for safety
            team1_poss = team1_row_dict.get("POSS_APPROX", 0)
            team2_poss = team2_row_dict.get("POSS_APPROX", 0)

            # Check for NaN points before calculating
            if pd.isna(opp1_pts) or pd.isna(opp2_pts):
                team1_row_dict["DEF_RTG_APPROX"] = np.nan
                team2_row_dict["DEF_RTG_APPROX"] = np.nan
                logging.warning(
                    f"Missing PTS data for game {season}, {game_id}. Cannot calculate Def Rtg."
                )
            else:
                team1_row_dict["DEF_RTG_APPROX"] = np.where(
                    team1_poss > 0, (opp1_pts / team1_poss) * 100, np.nan
                )
                team2_row_dict["DEF_RTG_APPROX"] = np.where(
                    team2_poss > 0, (opp2_pts / team2_poss) * 100, np.nan
                )

            # Copy opponent Def Rtg as well
            team1_row_dict["OPP_DEF_RTG_APPROX"] = team2_row_dict.get(
                "DEF_RTG_APPROX", np.nan
            )
            team2_row_dict["OPP_DEF_RTG_APPROX"] = team1_row_dict.get(
                "DEF_RTG_APPROX", np.nan
            )

            # --- Calculate Season H2H Win Percentage (Shifted) ---
            try:
                # Get game date safely
                current_game_date = team1_row_dict.get("GAME_DATE")
                if pd.isna(current_game_date):
                    raise ValueError("Current game date is missing")

                # Filter temp_df for past games in the same season between these two teams
                past_games_team1 = temp_df_for_h2h[
                    (temp_df_for_h2h["SEASON"] == season)
                    & (temp_df_for_h2h["GAME_DATE"] < current_game_date)
                    & (temp_df_for_h2h["TEAM_ID"] == team1_id)
                ]
                # Need opponent ABBR from team1's perspective
                opp_abbr_for_team1 = team1_row_dict["OPP_TEAM_ABBREVIATION"]

                # Handle case where OPP_TEAM_ABBREVIATION might be missing or NaN
                if pd.isna(opp_abbr_for_team1):
                    raise ValueError(
                        f"Opponent abbreviation missing for team {team1_id} in game {game_id}"
                    )

                team1_vs_team2_past = past_games_team1[
                    past_games_team1["MATCHUP"].str.contains(
                        f"{opp_abbr_for_team1}$|vs\. {opp_abbr_for_team1}",
                        na=False,
                        regex=True,
                    )  # Check end or vs., handle NaN MATCHUP, ensure regex=True
                ]

                total_h2h_games = len(team1_vs_team2_past)
                team1_h2h_wins = (
                    (team1_vs_team2_past["WL"] == "W").sum()
                    if total_h2h_games > 0
                    else 0
                )

                team1_row_dict["SEASON_H2H_WIN_PCT"] = np.where(
                    total_h2h_games > 0, team1_h2h_wins / total_h2h_games, 0
                )
                team2_row_dict["SEASON_H2H_WIN_PCT"] = np.where(
                    total_h2h_games > 0,
                    (total_h2h_games - team1_h2h_wins) / total_h2h_games,
                    0,
                )

            except Exception as h2h_err:
                logging.warning(
                    f"Could not calculate H2H for game {season}, {game_id}. Error: {h2h_err}. Setting H2H to 0."
                )
                team1_row_dict["SEASON_H2H_WIN_PCT"] = 0
                team2_row_dict["SEASON_H2H_WIN_PCT"] = 0

            # Add opponent H2H
            team1_row_dict["OPP_SEASON_H2H_WIN_PCT"] = team2_row_dict[
                "SEASON_H2H_WIN_PCT"
            ]
            team2_row_dict["OPP_SEASON_H2H_WIN_PCT"] = team1_row_dict[
                "SEASON_H2H_WIN_PCT"
            ]

            # --- Add Home/Away Flag ---
            matchup_str = team1_row_dict.get("MATCHUP", "")  # Use .get for safety
            if "@" in matchup_str:
                team1_row_dict["HOME_GAME"] = 0
                team2_row_dict["HOME_GAME"] = 1
            elif "vs." in matchup_str:
                team1_row_dict["HOME_GAME"] = 1
                team2_row_dict["HOME_GAME"] = 0
            else:  # Handle unexpected format
                team1_row_dict["HOME_GAME"] = np.nan
                team2_row_dict["HOME_GAME"] = np.nan
                logging.warning(
                    f"Could not determine home/away for game {season}, {game_id} from MATCHUP: {matchup_str}"
                )

            # --- Add Target Variable ---
            team1_wl = team1_row_dict.get("WL")  # Use .get for safety
            team2_wl = team2_row_dict.get("WL")
            team1_row_dict["WIN"] = (
                1 if team1_wl == "W" else (0 if team1_wl == "L" else np.nan)
            )
            team2_row_dict["WIN"] = (
                1 if team2_wl == "W" else (0 if team2_wl == "L" else np.nan)
            )

            # Restore index info -> No longer needed as we didn't use index
            # team1_row_dict['SEASON'], team1_row_dict['GAME_ID'], team1_row_dict['TEAM_ID'] = season, game_id, team1_id
            # team2_row_dict['SEASON'], team2_row_dict['GAME_ID'], team2_row_dict['TEAM_ID'] = season, game_id, team2_id

            processed_games.extend([team1_row_dict, team2_row_dict])

        # except KeyError as e:
        #      logging.warning(f"KeyError processing game {season}, {game_id}. Maybe missing data? Error: {e}. Skipping.")
        except Exception as e:
            # Log the specific error and traceback for better debugging
            import traceback

            logging.error(
                f"Unexpected error processing game {season}, {game_id}: {e}. Skipping."
            )
            logging.error(traceback.format_exc())  # Log full traceback

    final_df = pd.DataFrame(processed_games)

    # ===> Check if DataFrame is empty before proceeding <===
    if final_df.empty:
        logging.error(
            "No games were successfully processed in the opponent merge step. Returning empty DataFrame."
        )
        return pd.DataFrame()

    # Check if required columns for sorting exist
    sort_cols = ["SEASON", "TEAM_ID", "GAME_DATE"]
    if not all(col in final_df.columns for col in sort_cols):
        missing_sort_cols = [col for col in sort_cols if col not in final_df.columns]
        logging.error(
            f"DataFrame is missing columns required for sorting: {missing_sort_cols}. Cannot recalculate Def Rtg averages."
        )
        # Attempt to return the df as is, hoping downstream can handle it or user can inspect
        return final_df

    # --- Recalculate Rolling/Season Averages for DEF_RTG_APPROX ---
    logging.info("Recalculating rolling/season averages for Defensive Rating...")
    # Ensure sort_cols actually exist before sorting
    final_df = final_df.sort_values(by=sort_cols)
    grouped = final_df.groupby(["SEASON", "TEAM_ID"])
    recalculated_stats = []

    for (season_grp, team_id_grp), group in grouped:
        team_df = group.copy().sort_values(by="GAME_DATE")
        shifted_df = team_df.shift(1)

        # Check if DEF_RTG_APPROX column exists
        if "DEF_RTG_APPROX" not in team_df.columns:
            logging.warning(
                f"DEF_RTG_APPROX column missing for {season_grp}, {team_id_grp}. Cannot calculate averages."
            )
            # Add empty columns so concat doesn't fail
            for window in ROLLING_WINDOW_SIZES:
                team_df[f"AVG_DEF_RTG_APPROX_L{window}"] = np.nan
            team_df[f"SEASON_AVG_DEF_RTG_APPROX"] = np.nan
            recalculated_stats.append(team_df)
            continue

        # Rolling Def Rtg
        for window in ROLLING_WINDOW_SIZES:
            team_df[f"AVG_DEF_RTG_APPROX_L{window}"] = (
                shifted_df["DEF_RTG_APPROX"]
                .rolling(window=window, min_periods=MIN_GAMES_FOR_ROLLING)
                .mean()
            )
        # Season Avg Def Rtg
        cumulative_sum = shifted_df["DEF_RTG_APPROX"].cumsum()
        # Need SEASON_GAMES_PLAYED - check if it exists
        if "SEASON_GAMES_PLAYED" not in team_df.columns:
            logging.warning(
                f"SEASON_GAMES_PLAYED column missing for {season_grp}, {team_id_grp}. Setting Def Rtg season avg to NaN."
            )
            team_df[f"SEASON_AVG_DEF_RTG_APPROX"] = np.nan
        else:
            games_played = team_df["SEASON_GAMES_PLAYED"]
            # Ensure games_played is numeric and handle potential NaNs
            games_played_numeric = pd.to_numeric(games_played, errors="coerce")
            cumulative_sum_numeric = pd.to_numeric(cumulative_sum, errors="coerce")

            valid_mask = (
                (games_played_numeric > 0)
                & (~pd.isna(games_played_numeric))
                & (~pd.isna(cumulative_sum_numeric))
            )
            team_df[f"SEASON_AVG_DEF_RTG_APPROX"] = np.where(
                valid_mask, cumulative_sum_numeric / games_played_numeric, np.nan
            )
        recalculated_stats.append(team_df)

    if not recalculated_stats:
        # This case should ideally not be reached if final_df wasn't empty, but good to have
        logging.error("Failed to recalculate defensive rating averages (list empty).")
        # Return the original df before this step
        return final_df

    final_df = pd.concat(recalculated_stats).reset_index(drop=True)

    # ===> Adapt final merge step for non-indexed DataFrame <===
    # Add opponent averages for Def Rtg (requires another merge/lookup)
    logging.info("Adding opponent averages for Defensive Rating...")

    # Create a temporary mapping of game+team -> def rtg averages
    def_rtg_avg_cols = [
        col
        for col in final_df.columns
        if "AVG_DEF_RTG_APPROX" in col and not col.startswith("OPP_")
    ]
    map_cols = ["SEASON", "GAME_ID", "TEAM_ID"] + def_rtg_avg_cols
    if not all(c in final_df.columns for c in map_cols):
        logging.error(
            f"Missing columns needed for Def Rtg mapping ({[c for c in map_cols if c not in final_df.columns]}). Skipping opponent average merge."
        )
        return final_df

    def_rtg_map_df = final_df[map_cols].copy()

    # Rename columns in the map to represent the *opponent's* stats when merged
    rename_dict = {col: f"OPP_{col}" for col in def_rtg_avg_cols}
    def_rtg_map_df = def_rtg_map_df.rename(columns=rename_dict)

    # Merge onto the main df based on the opponent's ID
    final_df_merged = pd.merge(
        final_df,
        def_rtg_map_df,
        left_on=["SEASON", "GAME_ID", "OPP_TEAM_ID"],  # Match game and opponent ID
        right_on=[
            "SEASON",
            "GAME_ID",
            "TEAM_ID",
        ],  # Map is indexed by the team who *owns* the stat
        how="left",
    )

    # Drop the redundant TEAM_ID_y column from the merge
    if "TEAM_ID_y" in final_df_merged.columns:
        final_df_merged = final_df_merged.drop(columns=["TEAM_ID_y"])
    if "TEAM_ID_x" in final_df_merged.columns:
        final_df_merged = final_df_merged.rename(
            columns={"TEAM_ID_x": "TEAM_ID"}
        )  # Rename primary key back

    # # === Old Indexed Approach ===
    # # Check if required columns exist for index setting
    # if not all(col in final_df.columns for col in ['SEASON', 'GAME_ID', 'TEAM_ID']):
    #      logging.error("Missing columns required for final opponent Def Rtg average merge. Skipping.")
    #      return final_df

    # final_df_indexed = final_df.set_index(['SEASON', 'GAME_ID', 'TEAM_ID'])
    # opp_def_rtg_avg_cols = [col for col in final_df_indexed.columns if 'AVG_DEF_RTG_APPROX' in col and not col.startswith('OPP_')]
    # updated_rows = []

    # game_keys_final = final_df_indexed.index.droplevel('TEAM_ID').unique()
    # for season_f, game_id_f in game_keys_final:
    #     try:
    #         game_rows_f = final_df_indexed.loc[(season_f, game_id_f)]
    #         if len(game_rows_f) != 2: continue # Already warned

    #         team1_idx_f = game_rows_f.index[0]
    #         team2_idx_f = game_rows_f.index[1]
    #         team1_row_dict_f = game_rows_f.loc[team1_idx_f].to_dict()
    #         team2_row_dict_f = game_rows_f.loc[team2_idx_f].to_dict()

    #         # Restore index info before appending
    #         team1_row_dict_f['SEASON'], team1_row_dict_f['GAME_ID'], team1_row_dict_f['TEAM_ID'] = season_f, game_id_f, team1_idx_f[2]
    #         team2_row_dict_f['SEASON'], team2_row_dict_f['GAME_ID'], team2_row_dict_f['TEAM_ID'] = season_f, game_id_f, team2_idx_f[2]

    #         for col in opp_def_rtg_avg_cols:
    #             team1_row_dict_f[f'OPP_{col}'] = team2_row_dict_f.get(col, np.nan)
    #             team2_row_dict_f[f'OPP_{col}'] = team1_row_dict_f.get(col, np.nan)

    #         updated_rows.extend([team1_row_dict_f, team2_row_dict_f])
    #     except Exception as e:
    #         logging.error(f"Error adding opponent Def Rtg averages for {season_f}, {game_id_f}: {e}")

    # final_df_merged = pd.DataFrame(updated_rows) # Don't reset index here, it's already flat

    # # Check if the final merged df is empty
    # if final_df_merged.empty:
    #      logging.error("DataFrame became empty after merging opponent Def Rtg averages. Returning previous state.")
    #      # Reset index of the df before this last step
    #      return final_df.reset_index(drop=True)

    logging.info("Finished adding opponent data and finalizing metrics.")
    return final_df_merged


def _add_betting_lines(df):
    """Placeholder function to add betting lines."""
    # In a real scenario, fetch data from an API or file and merge based on GAME_ID or TEAMs+DATE
    logging.warning("Betting line integration is currently a placeholder.")
    df["SPREAD"] = np.nan
    df["TOTAL"] = np.nan
    df["TEAM_MONEYLINE"] = np.nan
    df["OPP_MONEYLINE"] = np.nan
    return df


def create_nba_dataset(seasons: list[str], output_file: str):
    """
    Main function to create the NBA team dataset for prediction.

    Args:
        seasons: A list of season strings (e.g., ['2022-23', '2023-24']).
        output_file: The full path to save the final CSV file.
    """
    logging.info(f"Starting dataset creation for seasons: {', '.join(seasons)}")

    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logging.info(f"Created output directory: {output_dir}")

    all_season_logs = []
    for season in seasons:
        log_df = _fetch_season_gamelogs(season)
        if not log_df.empty:
            all_season_logs.append(log_df)

    if not all_season_logs:
        logging.error("Failed to fetch any game logs. Dataset creation aborted.")
        return

    combined_log_df = pd.concat(all_season_logs).reset_index(drop=True)

    combined_log_df = _calculate_initial_metrics(combined_log_df)

    team_features_df = _calculate_team_features(combined_log_df)

    final_df = _add_opponent_h2h_and_final_metrics(team_features_df)

    if final_df.empty:
        logging.error("Final dataframe is empty after merging opponent data. Aborting.")
        return

    final_df = _add_betting_lines(final_df)

    core_info = [
        "SEASON",
        "GAME_ID",
        "GAME_DATE",
        "TEAM_ID",
        "TEAM_ABBREVIATION",
        "MATCHUP",
        "HOME_GAME",
        "WIN",
    ]
    opponent_info = ["OPP_TEAM_ID", "OPP_TEAM_ABBREVIATION"]
    context_info = [
        "REST_DAYS",
        "OPP_REST_DAYS",
        "B2B",
        "OPP_B2B",
        "SEASON_H2H_WIN_PCT",
        "OPP_SEASON_H2H_WIN_PCT",
        "WIN_STREAK",
        "LOSS_STREAK",
        "OPP_WIN_STREAK",
        "OPP_LOSS_STREAK",
    ]
    betting_info = ["SPREAD", "TOTAL", "TEAM_MONEYLINE", "OPP_MONEYLINE"]

    team_features = sorted(
        [
            col
            for col in final_df.columns
            if (col.startswith("AVG_") or col.startswith("SEASON_AVG_"))
            and not col.startswith("OPP_")
        ]
    )
    opp_features = sorted(
        [
            col
            for col in final_df.columns
            if (col.startswith("OPP_AVG_") or col.startswith("OPP_SEASON_AVG_"))
        ]
    )
    other_season_stats = sorted(
        [
            col
            for col in final_df.columns
            if col.startswith("SEASON_")
            and col not in core_info + context_info + team_features
        ]
    )
    opp_other_season_stats = sorted(
        [
            col
            for col in final_df.columns
            if col.startswith("OPP_SEASON_")
            and col not in opponent_info + context_info + opp_features
        ]
    )

    # Ensure WIN is the last column for typical ML tasks
    final_columns_ordered = (
        core_info[:-1]
        + opponent_info
        + context_info
        + team_features
        + opp_features
        + other_season_stats
        + opp_other_season_stats
        + betting_info
        + [core_info[-1]]
    )  # Add WIN last

    # Filter out columns that might not exist (e.g., if a stat calculation failed)
    final_columns_ordered = [
        col for col in final_columns_ordered if col in final_df.columns
    ]

    final_df = final_df[final_columns_ordered]

    # 7. Save the dataset
    try:
        final_df.to_csv(output_file, index=False)
        logging.info(f"Dataset successfully saved to {output_file}")
    except Exception as e:
        logging.error(f"Error saving dataset to {output_file}: {e}")

    # Print the final number of rows
    if not final_df.empty:
        logging.info(
            f"Final dataset contains {len(final_df)} rows ({len(final_df)//2} games)."
        )
    else:
        logging.warning("Final dataset is empty.")

    logging.info("Dataset creation script finished.")


if __name__ == "__main__":
    SEASONS_TO_PROCESS = ["2023-24", "2024-25"]
    OUTPUT_DIRECTORY = "shared/data"
    OUTPUT_FILENAME = "team_predictions_enhanced.csv"
    FULL_OUTPUT_PATH = os.path.join(OUTPUT_DIRECTORY, OUTPUT_FILENAME)

    create_nba_dataset(seasons=SEASONS_TO_PROCESS, output_file=FULL_OUTPUT_PATH)
