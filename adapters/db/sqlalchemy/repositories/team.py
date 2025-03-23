from sqlalchemy.ext.asyncio import AsyncSession
from adapters.db.repositories import TeamRepository
from adapters.db.sqlalchemy.tables import Team
from schemas import TeamCreate, TeamRead, TeamReadWithPlayers
from typing import List, Optional
from sqlalchemy.orm import joinedload


class SQLAlchemyTeamRepository(TeamRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, team: TeamCreate) -> TeamRead:
        team_instance = Team(**team.dict())
        self.session.add(team_instance)
        await self.session.refresh(team_instance)
        return TeamRead.from_orm(team_instance)

    async def add_batch(self, teams: List[TeamCreate]) -> List[TeamRead]:
        team_instances = [Team(**team.dict()) for team in teams]
        self.session.add_all(team_instances)
        return [TeamRead.from_orm(team) for team in team_instances]

    async def get_by_id(self, team_id: int) -> Optional[TeamRead]:
        team = await self.session.get(Team, team_id)
        return TeamRead.from_orm(team) if team else None

    async def query(self, **kwargs) -> List[TeamRead]:
        query = self.session.query(Team)
        return [TeamRead.from_orm(team) for team in await query.all()]

    async def get_with_players(self, team_id: int) -> Optional[TeamReadWithPlayers]:
        query = self.session.query(Team).options(joinedload(Team.players))
        team = await query.filter(Team.team_id == team_id).first()
        return TeamReadWithPlayers.from_orm(team) if team else None
