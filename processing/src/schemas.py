"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# Listener Data Schemas
class GPSCoordinates(BaseModel):
    lat: float
    lon: float


class PathData(BaseModel):
    source_hash: str
    dest_hash: str
    path: List[str]  # List of hashes like ["0xAB", "0x12", "0x34"]
    snr: Optional[float] = None
    rssi: Optional[float] = None


class ContactData(BaseModel):
    public_key: str  # Hex string
    hash: str  # First byte, e.g., "0xAB"
    name: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    is_repeater: bool = True


class TraceResultData(BaseModel):
    trace_id: UUID
    path: List[str]
    snr_values: List[float]
    success: bool
    error: Optional[str] = None


class ListenerDataSubmission(BaseModel):
    listener_id: UUID
    timestamp: datetime
    data_type: str  # "path", "contact", "trace_result"
    data: Dict[str, Any]  # Flexible data field


# Repeater Schemas
class RepeaterBase(BaseModel):
    hash: str
    name: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None


class RepeaterCreate(RepeaterBase):
    public_key: Optional[str] = None


class RepeaterResponse(RepeaterBase):
    id: UUID
    public_key: Optional[str] = None
    last_seen: datetime
    first_seen: datetime

    @field_validator('public_key', mode='before')
    @classmethod
    def validate_public_key(cls, value):
        """Convert bytes public key to hex string."""
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.hex()
        return value

    class Config:
        from_attributes = True


# Graph Schemas
class GraphEdgeResponse(BaseModel):
    id: int
    from_repeater_id: UUID
    to_repeater_id: UUID
    message_count: int
    avg_snr: Optional[float] = None
    week_number: int
    last_updated: datetime
    sample_path: Optional[List[str]] = None  # Example path that uses this edge
    last_trace_at: Optional[datetime] = None  # When last trace was completed
    last_trace_path: Optional[str] = None  # Formatted like "0xa0(-3.4)→0x41(12.0)"

    class Config:
        from_attributes = True


class GraphResponse(BaseModel):
    repeaters: List[RepeaterResponse]
    edges: List[GraphEdgeResponse]


# Listener Management Schemas
class ListenerCreate(BaseModel):
    name: str


class ListenerResponse(BaseModel):
    id: UUID
    name: str
    last_seen: Optional[datetime] = None
    active: bool
    created_at: datetime
    api_key: Optional[str] = None  # Only included on creation

    class Config:
        from_attributes = True


# Trace Schemas
class PendingTraceResponse(BaseModel):
    id: UUID
    from_repeater_hash: str
    to_repeater_hash: str
    from_repeater_public_key: Optional[str] = None
    to_repeater_public_key: Optional[str] = None
    scheduled_at: datetime

    class Config:
        from_attributes = True


class TraceScheduleResponse(BaseModel):
    id: UUID
    from_repeater_id: UUID
    from_repeater_name: Optional[str] = None
    from_repeater_hash: str
    to_repeater_id: UUID
    to_repeater_name: Optional[str] = None
    to_repeater_hash: str
    assigned_listener_id: Optional[UUID] = None
    assigned_listener_name: Optional[str] = None
    status: str  # pending, in_progress, completed, failed
    scheduled_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    calculated_path: Optional[List[str]] = None  # Planned path for this trace
    path_strategy: Optional[str] = None  # 'direct', 'loop', etc.

    class Config:
        from_attributes = True


class TraceSchedulerStatus(BaseModel):
    enabled: bool
    paused: bool
    total_scheduled: int
    pending: int
    in_progress: int
    completed: int
    failed: int


class TraceResultSubmission(BaseModel):
    trace_id: UUID
    success: bool
    path: Optional[List[str]] = None
    snr_values: Optional[List[float]] = None
    formatted_path: Optional[str] = None  # Formatted like "0xa0(-3.4)→0x41(12.0)"
    error: Optional[str] = None


# Admin Schemas
class TraceConfigUpdate(BaseModel):
    throttle_seconds: Optional[int] = None
    verification_interval_hours: Optional[int] = None
    enabled: Optional[bool] = None


class TraceConfigResponse(BaseModel):
    throttle_seconds: int
    verification_interval_hours: int
    enabled: bool
    last_trace_at: Optional[datetime] = None


class SystemStats(BaseModel):
    total_repeaters: int
    total_listeners: int
    active_listeners: int
    total_paths: int
    paths_this_week: int
    total_traces: int
    pending_traces: int
    completed_traces: int
    failed_traces: int
    last_graph_update: Optional[datetime] = None


# API Key Schemas
class APIKeyCreate(BaseModel):
    key_type: str = Field(..., pattern="^(admin|listener|visualization)$")
    description: Optional[str] = None


class APIKeyResponse(BaseModel):
    id: UUID
    key: str  # Plain text key, only returned on creation
    key_type: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
