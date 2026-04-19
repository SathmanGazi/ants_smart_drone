from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    storage_dir: Path = Field(default=Path("storage"), alias="STORAGE_DIR")

    yolo_model: str = Field(default="yolov8n.pt", alias="YOLO_MODEL")
    yolo_conf_threshold: float = Field(default=0.35, alias="YOLO_CONF_THRESHOLD")
    yolo_iou_threshold: float = Field(default=0.5, alias="YOLO_IOU_THRESHOLD")
    yolo_device: str = Field(default="cpu", alias="YOLO_DEVICE")
    # YOLO inference resolution. Default 640 is the Ultralytics default.
    # Dropping to 480 is ~1.8x faster on CPU at some recall cost on
    # very small far-away vehicles. 320 is ~3x faster but loses small
    # objects. Set higher (960) if you have GPU and want max accuracy.
    yolo_imgsz: int = Field(default=640, alias="YOLO_IMGSZ")

    # COCO class IDs for vehicles we care about.
    # 2 car, 3 motorcycle, 5 bus, 7 truck
    vehicle_class_ids: List[int] = Field(default=[2, 3, 5, 7])

    min_hits_to_count: int = Field(default=6, alias="MIN_HITS_TO_COUNT")
    min_streak: int = Field(default=3, alias="MIN_STREAK")
    min_displacement_px: float = Field(default=35.0, alias="MIN_DISPLACEMENT_PX")
    stationary_grace_frames: int = Field(default=60, alias="STATIONARY_GRACE_FRAMES")
    reid_window_frames: int = Field(default=30, alias="REID_WINDOW_FRAMES")
    reid_distance_px: float = Field(default=60.0, alias="REID_DISTANCE_PX")

    progress_every_n_frames: int = Field(default=10, alias="PROGRESS_EVERY_N_FRAMES")
    frame_stride: int = Field(default=1, alias="FRAME_STRIDE")
    # 8 GB default — a 50-min 1080p H.264 MP4 is ~3-5 GB. Upload is
    # streamed to disk and cut off byte-accurately past the limit.
    max_upload_mb: int = Field(default=8192, alias="MAX_UPLOAD_MB")

    cors_origins: List[str] = Field(
        default=["http://localhost:3000"], alias="CORS_ORIGINS"
    )

    # ROI as a pixel-space polygon, e.g. "[[100,200],[1800,200],[1800,900],[100,900]]"
    # Tracks whose centroid falls outside this polygon are never counted.
    # Leave empty to disable (count everywhere).
    roi_polygon_json: Optional[str] = Field(default=None, alias="ROI_POLYGON_JSON")

    # Optional virtual tripwire line for directional counting.
    # JSON pair of points in pixel space: "[[x1,y1],[x2,y2]]".
    # Labels default to "A" / "B"; swap if sides come out reversed.
    tripwire_line_json: Optional[str] = Field(default=None, alias="TRIPWIRE_LINE_JSON")
    tripwire_label_a: str = Field(default="A", alias="TRIPWIRE_LABEL_A")
    tripwire_label_b: str = Field(default="B", alias="TRIPWIRE_LABEL_B")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    def roi_polygon(self) -> Optional[list[list[float]]]:
        if not self.roi_polygon_json:
            return None
        try:
            data = json.loads(self.roi_polygon_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, list) or len(data) < 3:
            return None
        return [[float(p[0]), float(p[1])] for p in data]

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        return self.storage_dir / "outputs"

    def ensure_dirs(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
