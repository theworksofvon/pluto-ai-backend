from __future__ import annotations

from datetime import date

import pytest
from app.adapters.nba.sources import (
    NbaApiPlayerGameLogSource,
    NbaApiScheduleSource,
)


@pytest.mark.live_nba
async def test_live_nba_scoreboard_smoke() -> None:
    result = await NbaApiScheduleSource(timeout_seconds=10).games_for_date(
        date(2026, 4, 15)
    )

    assert result.status == "success"
    assert result.raw_payload is not None
    assert result.data


@pytest.mark.live_nba
async def test_live_nba_player_gamelog_smoke() -> None:
    result = await NbaApiPlayerGameLogSource(
        timeout_seconds=10
    ).get_player_game_logs(
        player_id=2544,
        season="2025-26",
    )

    assert result.status == "success"
    assert result.raw_payload is not None
    assert result.data
