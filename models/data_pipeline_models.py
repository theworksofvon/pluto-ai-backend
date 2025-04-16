from pydantic import BaseModel
import pandas as pd


class DataPipelineLatestData(BaseModel):
    player_stats: pd.DataFrame
    odds_data: pd.DataFrame
