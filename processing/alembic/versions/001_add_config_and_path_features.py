"""Add SystemConfig table and enhance TraceSchedule and Repeater models

Revision ID: 001
Revises:
Create Date: 2026-01-29 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create system_config table
    op.create_table(
        'system_config',
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )

    # Add position estimation fields to repeaters table
    op.add_column('repeaters', sa.Column('estimated_gps_lat', sa.Float(), nullable=True))
    op.add_column('repeaters', sa.Column('estimated_gps_lon', sa.Float(), nullable=True))
    op.add_column('repeaters', sa.Column('position_confidence', sa.String(20), nullable=True))
    op.add_column('repeaters', sa.Column('triangulation_neighbors', postgresql.JSON(astext_type=sa.Text()), nullable=True))

    # Add snr_source to paths table and null out existing SNR data
    op.add_column('paths', sa.Column('snr_source', sa.String(20), nullable=True))
    op.execute("UPDATE paths SET snr = NULL, snr_source = 'unknown'")

    # Null out avg_snr in graph_edges (will be repopulated from trace results)
    op.execute("UPDATE graph_edges SET avg_snr = NULL")

    # Add calculated_path and path_strategy to trace_schedule table
    op.add_column('trace_schedule', sa.Column('calculated_path', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('trace_schedule', sa.Column('path_strategy', sa.String(50), nullable=True))

    # Insert initial configuration values
    op.execute("""
        INSERT INTO system_config (key, value, value_type, description, updated_at) VALUES
        ('trace_throttle_seconds', '30', 'int', 'Seconds between scheduled trace commands', NOW()),
        ('trace_verification_interval_hours', '24', 'int', 'Hours before re-verifying an edge with a new trace', NOW()),
        ('max_pending_traces_per_listener', '50', 'int', 'Maximum number of pending traces per listener', NOW())
    """)


def downgrade():
    # Remove trace_schedule columns
    op.drop_column('trace_schedule', 'path_strategy')
    op.drop_column('trace_schedule', 'calculated_path')

    # Remove paths column
    op.drop_column('paths', 'snr_source')

    # Remove repeaters columns
    op.drop_column('repeaters', 'triangulation_neighbors')
    op.drop_column('repeaters', 'position_confidence')
    op.drop_column('repeaters', 'estimated_gps_lon')
    op.drop_column('repeaters', 'estimated_gps_lat')

    # Drop system_config table
    op.drop_table('system_config')
