"""adjust_prediction_tables

Revision ID: 79000ace831e
Revises: 71ea306f4a8f
Create Date: 2025-03-09 16:15:09.945340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '79000ace831e'
down_revision: Union[str, None] = '71ea306f4a8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create new game-level predictions table.
    op.create_table(
        'game_predictions',
        sa.Column('prediction_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('home_team_win_percentage', sa.Float(), nullable=False),
        sa.Column('opposing_team_win_percentage', sa.Float(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('predicted_winner_team_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['predicted_winner_team_id'], ['teams.team_id']),
        sa.PrimaryKeyConstraint('prediction_id')
    )
    # Create new individual player predictions table.
    op.create_table(
        'player_predictions',
        sa.Column('prediction_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('predicted_points', sa.Float(), nullable=False),
        sa.Column('predicted_assists', sa.Float(), nullable=True),
        sa.Column('predicted_rebounds', sa.Float(), nullable=True),
        sa.Column('explanation', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('range_low', sa.Float(), nullable=True),
        sa.Column('range_high', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id']),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id']),
        sa.PrimaryKeyConstraint('prediction_id')
    )
    # Drop old tables.
    op.execute("DROP TABLE predictions CASCADE")
    op.drop_table('player_game_stats')
    op.drop_table('player_stats_predictions')
    # Adjust columns to enforce NOT NULL constraints.
    op.alter_column('games', 'date',
               existing_type=sa.DATE(),
               nullable=False)
    op.alter_column('games', 'home_team_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('games', 'away_team_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('players', 'name',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('players', 'team_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('teams', 'name',
               existing_type=sa.VARCHAR(),
               nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Relax NOT NULL constraints.
    op.alter_column('teams', 'name',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('players', 'team_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('players', 'name',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('games', 'away_team_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('games', 'home_team_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('games', 'date',
               existing_type=sa.DATE(),
               nullable=True)
    # Recreate the old tables.
    op.create_table(
        'player_stats_predictions',
        sa.Column('prediction_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('player_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('predicted_points', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
        sa.Column('predicted_assists', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
        sa.Column('predicted_rebounds', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], name='player_stats_predictions_player_id_fkey'),
        sa.ForeignKeyConstraint(['prediction_id'], ['predictions.prediction_id'], name='player_stats_predictions_prediction_id_fkey'),
        sa.PrimaryKeyConstraint('prediction_id', 'player_id', name='player_stats_predictions_pkey')
    )
    op.create_table(
        'player_game_stats',
        sa.Column('game_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('player_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('points', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('assists', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('rebounds', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id'], name='player_game_stats_game_id_fkey'),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], name='player_game_stats_player_id_fkey'),
        sa.PrimaryKeyConstraint('game_id', 'player_id', name='player_game_stats_pkey')
    )
    op.create_table(
        'predictions',
        sa.Column('prediction_id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('predicted_winner_team_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('timestamp', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.game_id'], name='predictions_game_id_fkey'),
        sa.ForeignKeyConstraint(['predicted_winner_team_id'], ['teams.team_id'], name='predictions_predicted_winner_team_id_fkey'),
        sa.PrimaryKeyConstraint('prediction_id', name='predictions_pkey')
    )
    # Drop the new tables.
    op.drop_table('player_predictions')
    op.drop_table('game_predictions')