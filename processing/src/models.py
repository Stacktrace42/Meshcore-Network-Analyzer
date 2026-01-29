"""SQLAlchemy database models."""
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, ForeignKey, JSON, UniqueConstraint, BigInteger, LargeBinary, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .database import Base


class Listener(Base):
    """Network node that connects to MeshCore hardware and captures traffic."""
    __tablename__ = "listeners"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    api_key_hash = Column(String, unique=True, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    paths = relationship("Path", back_populates="listener")
    assigned_traces = relationship("TraceSchedule", back_populates="assigned_listener")


class Repeater(Base):
    """MeshCore repeater node in the network."""
    __tablename__ = "repeaters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_key = Column(LargeBinary(32), unique=True, nullable=True)  # Full Ed25519 public key
    hash = Column(String(4), nullable=False, index=True)  # First byte of public key (e.g., "0xAB")
    name = Column(String, nullable=True)
    gps_lat = Column(Float, nullable=True)
    gps_lon = Column(Float, nullable=True)
    estimated_gps_lat = Column(Float, nullable=True)
    estimated_gps_lon = Column(Float, nullable=True)
    position_confidence = Column(String(20), nullable=True)  # 'known', 'triangulated', 'unknown'
    triangulation_neighbors = Column(JSON, nullable=True)  # [neighbor_ids]
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    first_seen = Column(DateTime, default=datetime.utcnow)

    # Relationships
    edges_from = relationship("GraphEdge", foreign_keys="GraphEdge.from_repeater_id", back_populates="from_repeater")
    edges_to = relationship("GraphEdge", foreign_keys="GraphEdge.to_repeater_id", back_populates="to_repeater")
    traces_from = relationship("TraceSchedule", foreign_keys="TraceSchedule.from_repeater_id", back_populates="from_repeater")
    traces_to = relationship("TraceSchedule", foreign_keys="TraceSchedule.to_repeater_id", back_populates="to_repeater")


class Path(Base):
    """Observed packet path through the network."""
    __tablename__ = "paths"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    listener_id = Column(UUID(as_uuid=True), ForeignKey("listeners.id"), nullable=False)
    source_hash = Column(String(4), nullable=False, index=True)
    dest_hash = Column(String(4), nullable=False, index=True)
    path = Column(JSON, nullable=False)  # Array of hashes, e.g., ["0xAB", "0x12", "0x34"]
    snr = Column(Float, nullable=True)
    snr_source = Column(String(20), default='unknown', nullable=True)  # 'trace', 'reception', 'unknown'
    rssi = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    week_number = Column(Integer, nullable=False, index=True)  # ISO week number for aggregation

    # Relationships
    listener = relationship("Listener", back_populates="paths")


class GraphEdge(Base):
    """Computed edge in the network graph between two repeaters."""
    __tablename__ = "graph_edges"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    from_repeater_id = Column(UUID(as_uuid=True), ForeignKey("repeaters.id"), nullable=False)
    to_repeater_id = Column(UUID(as_uuid=True), ForeignKey("repeaters.id"), nullable=False)
    message_count = Column(Integer, default=0, nullable=False)
    avg_snr = Column(Float, nullable=True)
    week_number = Column(Integer, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_trace_at = Column(DateTime, nullable=True)  # When last trace was completed
    last_trace_path = Column(String, nullable=True)  # Formatted like "0xa0(-3.4)→0x41(12.0)"

    # Relationships
    from_repeater = relationship("Repeater", foreign_keys=[from_repeater_id], back_populates="edges_from")
    to_repeater = relationship("Repeater", foreign_keys=[to_repeater_id], back_populates="edges_to")

    __table_args__ = (
        UniqueConstraint('from_repeater_id', 'to_repeater_id', 'week_number', name='_edge_week_uc'),
    )


class TraceSchedule(Base):
    """Scheduled trace commands to verify network paths."""
    __tablename__ = "trace_schedule"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_repeater_id = Column(UUID(as_uuid=True), ForeignKey("repeaters.id"), nullable=False)
    to_repeater_id = Column(UUID(as_uuid=True), ForeignKey("repeaters.id"), nullable=False)
    assigned_listener_id = Column(UUID(as_uuid=True), ForeignKey("listeners.id"), nullable=True)
    status = Column(String, default="pending", nullable=False)  # pending, in_progress, completed, failed
    scheduled_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)  # Trace result data
    calculated_path = Column(JSON, nullable=True)  # ["0xAB", "0x12", "0x34", "0xAB"]
    path_strategy = Column(String(50), nullable=True)  # 'loop', 'direct'

    # Relationships
    from_repeater = relationship("Repeater", foreign_keys=[from_repeater_id], back_populates="traces_from")
    to_repeater = relationship("Repeater", foreign_keys=[to_repeater_id], back_populates="traces_to")
    assigned_listener = relationship("Listener", back_populates="assigned_traces")


class APIKey(Base):
    """API keys for authentication."""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash = Column(String, unique=True, nullable=False)
    key_type = Column(String, nullable=False)  # admin, listener, visualization
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)


class SystemConfig(Base):
    """System configuration key-value store."""
    __tablename__ = "system_config"

    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=False)
    value_type = Column(String(50), nullable=False)  # 'int', 'float', 'string', 'bool'
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
