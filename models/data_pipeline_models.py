import pandas as pd
from models import BaseSchema
from pydantic import ConfigDict


class DataPipelineLatestData(BaseSchema):
    player_stats: pd.DataFrame
    odds_data: pd.DataFrame

    model_config = ConfigDict(arbitrary_types_allowed=True)
