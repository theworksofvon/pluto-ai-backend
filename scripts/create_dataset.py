import os
import sys
from pathlib import Path

# project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

import pandas as pd
from adapters import Adapters
from datetime import datetime


def parse_matchup(matchup_str: str):
    """
    Given a string like 'LAL vs. GSW' or 'LAL @ LAC',
    return (home_away_flag, opponent).
    home_away_flag = 1 if home (vs.), 0 if away (@).
    opponent = e.g. 'GSW', 'LAC'.
    """
    parts = matchup_str.split()
    if len(parts) >= 3:
        location_token = parts[1]
        opponent = parts[2]
        home_away_flag = 1 if location_token.lower() == "vs." else 0
    else:
        home_away_flag = None
        opponent = None

    return home_away_flag, opponent


def convert_game_date(date_str: str | pd.Timestamp):
    """
    Convert a date string like 'FEB 06, 2025' to a Python datetime.
    We'll attempt the format '%b %d, %Y'.
    If input is already a Timestamp, return it as is.
    """
    if isinstance(date_str, pd.Timestamp):
        return date_str
        
    try:
        return datetime.strptime(date_str, "%b %d, %Y")
    except:
        return pd.NaT  # If parsing fails


def save_to_csv(df: pd.DataFrame, filename: str | None = None) -> str:
    """
    Save the DataFrame to a CSV file.
    If no filename is provided, creates one with timestamp.
    Returns the path to the saved file.
    """
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)

    # Generate filename if not provided
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pluto_dataset_{timestamp}.csv"

    filepath = os.path.join("data", filename)
    df.to_csv(filepath, index=False)
    print(f"Dataset saved to: {filepath}")
    return filepath


async def create_pluto_dataset(
    players: list[str] | None = None, seasons: list[str] | None = ["2023-24", "2024-25"]
) -> pd.DataFrame:
    """
    Creates a dataset of (optionally) multiple seasons of player game logs,
    avoiding data leakage for next-game points prediction.
    Returns a single pandas DataFrame with one row per game.
    'players': list of player names
    'seasons': list of seasons to fetch (e.g. ['2024-25', '2023-24']).
    """
    adapters = Adapters()

    final_df = pd.DataFrame()

    if players:
        for player in players:
            try:
                # 1. Get player info
                info = adapters.nba_analytics.find_player_info(player)
                player_info_dict = info.to_dict()

                print(f"{player} found. Fetching game logs...")

                # 2. Fetch logs (for multiple seasons if provided)
                if not seasons:
                    # Single season or default fetch
                    player_game_logs_dict = adapters.nba_analytics.get_player_game_logs(
                        name=player
                    )
                    df_logs = pd.DataFrame(
                        {
                            col_name: pd.Series(col_values)
                            for col_name, col_values in player_game_logs_dict.items()
                        }
                    )
                else:
                    season_frames = []
                    for season in seasons:
                        logs_dict = adapters.nba_analytics.get_player_game_logs(
                            name=player, season=season
                        )
                        season_df = pd.DataFrame(
                            {
                                col_name: pd.Series(col_values)
                                for col_name, col_values in logs_dict.items()
                            }
                        )
                        season_frames.append(season_df)
                    df_logs = pd.concat(season_frames, ignore_index=True)

                # 3. Add a column for player's name
                df_logs["player_name"] = player_info_dict.get(
                    "display_first_last", player
                )

                print(f"{player} logs appended with shape: {df_logs.shape}")

                # 4. Parse MATCHUP to get home/away & opponent
                df_logs["home_away_flag"] = None
                df_logs["opponent"] = None
                if "MATCHUP" in df_logs.columns:
                    parsed = df_logs["MATCHUP"].apply(parse_matchup)
                    df_logs["home_away_flag"] = parsed.apply(lambda x: x[0])
                    df_logs["opponent"] = parsed.apply(lambda x: x[1])

                # 5. Convert GAME_DATE to a datetime
                if "GAME_DATE" in df_logs.columns:
                    df_logs["game_date_parsed"] = df_logs["GAME_DATE"].apply(
                        convert_game_date
                    )
                else:
                    df_logs["game_date_parsed"] = pd.NaT

                # 6. Sort logs by player and date
                df_logs.sort_values(
                    by=["player_name", "game_date_parsed"], inplace=True
                )

                # ----------------------------------------------------------------
                # 7. Create rolling features for PTS, MIN, FGA, FG_PCT
                # ----------------------------------------------------------------

                # We must check if these columns exist (some might be missing).
                # Then we group by player, do rolling(5), shift(1), and .mean().

                # Rolling PTS
                if "PTS" in df_logs.columns:
                    df_logs["rolling_pts_5"] = (
                        df_logs.groupby("player_name")["PTS"]
                        .rolling(window=5, min_periods=1)
                        .mean()
                        .shift(1)
                        .values
                    )

                # Rolling MIN
                if "MIN" in df_logs.columns:
                    df_logs["rolling_min_5"] = (
                        df_logs.groupby("player_name")["MIN"]
                        .rolling(window=5, min_periods=1)
                        .mean()
                        .shift(1)
                        .values
                    )

                # Rolling FGA
                if "FGA" in df_logs.columns:
                    df_logs["rolling_fga_5"] = (
                        df_logs.groupby("player_name")["FGA"]
                        .rolling(window=5, min_periods=1)
                        .mean()
                        .shift(1)
                        .values
                    )

                # Rolling FG_PCT
                if "FG_PCT" in df_logs.columns:
                    df_logs["rolling_fg_pct_5"] = (
                        df_logs.groupby("player_name")["FG_PCT"]
                        .rolling(window=5, min_periods=1)
                        .mean()
                        .shift(1)
                        .values
                    )

                # ----------------------------------------------------------------
                # 8. Calculate days_since_last_game & back_to_back_flag
                # ----------------------------------------------------------------
                df_logs["days_since_last_game"] = (
                    df_logs.groupby("player_name")["game_date_parsed"].diff().dt.days
                )
                df_logs["back_to_back_flag"] = df_logs["days_since_last_game"].apply(
                    lambda x: 1 if x == 1 else 0
                )

                # ----------------------------------------------------------------
                # 9. (Optional) Drop same-game stats to avoid leakage
                #    after we've created rolling features
                # ----------------------------------------------------------------
                drop_cols = [
                    "SEASON_ID",
                    "VIDEO_AVAILABLE",
                    "Player_ID",
                    "MIN",
                    "FGA",
                    "FGM",
                    "FG_PCT",
                    "FG3M",
                    "FG3A",
                    "FG3_PCT",
                    "FTM",
                    "FTA",
                    "FT_PCT",
                    "OREB",
                    "DREB",
                    "REB",
                    "AST",
                    "STL",
                    "BLK",
                    "TOV",
                    "PF",
                    "PLUS_MINUS",
                ]
                df_logs.drop(
                    columns=[c for c in drop_cols if c in df_logs.columns],
                    inplace=True,
                    errors="ignore",
                )

                # 10. Append to final DataFrame
                final_df = pd.concat([final_df, df_logs], ignore_index=True)

                print(f"After processing {player}, final_df has {len(final_df)} rows.")

            except Exception as error:
                print(f"Failed to process player '{player}': {error}")
                continue

    # Sort the final DataFrame by (player_name, game_date_parsed) if you want
    final_df.sort_values(by=["player_name", "game_date_parsed"], inplace=True)
    final_df.reset_index(drop=True, inplace=True)

    return final_df


async def main():
    players = ["LeBron James", "Stephen Curry", "Kevin Durant"]
    seasons = ["2023-24", "2024-25"]

    df = await create_pluto_dataset(players=players, seasons=seasons)
    save_to_csv(df)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
