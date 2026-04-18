from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    filename: str


class JobProgress(BaseModel):
    frame: int = 0
    total_frames: int = 0
    percent: float = 0.0
    fps_processing: float = 0.0
    message: Optional[str] = None


class JobRecord(BaseModel):
    id: str
    filename: str
    status: JobStatus = JobStatus.QUEUED
    progress: JobProgress = Field(default_factory=JobProgress)
    error: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


class TrackReport(BaseModel):
    track_id: int
    vehicle_class: str
    first_seen_frame: int
    last_seen_frame: int
    first_seen_ts: float
    last_seen_ts: float
    total_hits: int
    median_confidence: float
    counted_at_frame: int


class DetectionRow(BaseModel):
    frame: int
    timestamp: float
    track_id: int
    vehicle_class: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]


class RejectedTrack(BaseModel):
    track_id: int
    vehicle_class: str
    first_seen_frame: int
    last_seen_frame: int
    first_seen_ts: float
    last_seen_ts: float
    total_hits: int
    displacement_px: float
    median_confidence: float
    rejection_reason: str


class JobResult(BaseModel):
    job_id: str
    total_unique: int
    by_class: Dict[str, int]
    processing_duration_sec: float
    video_duration_sec: float
    fps: float
    total_frames: int
    counted_tracks: List[TrackReport]
    rejected_tracks: List[RejectedTrack] = Field(default_factory=list)
    rejection_summary: Dict[str, int] = Field(default_factory=dict)
    # Keep detections optional/bounded in API payload to avoid huge responses.
    sample_detections: List[DetectionRow] = Field(default_factory=list)
    processed_video_url: str
    csv_url: str
    xlsx_url: str


class ErrorResponse(BaseModel):
    detail: str
