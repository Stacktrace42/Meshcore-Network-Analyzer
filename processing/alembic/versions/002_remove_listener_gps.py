"""Remove GPS coordinates from listeners table

Revision ID: 002_remove_listener_gps
Revises: 001_add_config_and_path_features
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_remove_listener_gps'
down_revision = '001_add_config_and_path_features'
branch_labels = None
depends_on = None


def upgrade():
    """Remove GPS columns from listeners table.

    Listener selection is now based on reception quality (message count + SNR)
    rather than GPS distance, so listener GPS coordinates are no longer needed.
    """
    # Drop GPS columns from listeners table
    op.drop_column('listeners', 'gps_lat')
    op.drop_column('listeners', 'gps_lon')


def downgrade():
    """Add GPS columns back to listeners table."""
    op.add_column('listeners', sa.Column('gps_lat', sa.Float(), nullable=True))
    op.add_column('listeners', sa.Column('gps_lon', sa.Float(), nullable=True))
