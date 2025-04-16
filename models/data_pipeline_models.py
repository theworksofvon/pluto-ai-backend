from pydantic import BaseModel, ConfigDict
import pandas as pd


class DataPipelineLatestData(BaseModel):
    player_stats: pd.DataFrame
    odds_data: pd.DataFrame

    model_config = ConfigDict(arbitrary_types_allowed=True)
