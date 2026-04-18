from __future__ import annotations

from typing import Optional

import numpy as np
import supervision as sv

from app.cv.detector import RawDetection


class VehicleTracker:
    """
    ByteTrack via supervision. Stable IDs across short occlusions
    (lost_track_buffer) and low-confidence associations.
    """

    def __init__(self, fps: float = 30.0) -> None:
        # Parameters tuned for aerial / drone-like footage:
        # - track_activation_threshold: accept tracks a bit more eagerly
        # - lost_track_buffer: tolerate ~1s occlusion at fps
        self._tracker = sv.ByteTrack(
            track_activation_threshold=0.35,
            lost_track_buffer=max(30, int(fps * 1.0)),
            minimum_matching_threshold=0.8,
            frame_rate=int(max(1, round(fps))),
            minimum_consecutive_frames=1,
        )

    def update(self, det: RawDetection) -> sv.Detections:
        if det.xyxy.shape[0] == 0:
            empty = sv.Detections.empty()
            return self._tracker.update_with_detections(empty)
        detections = sv.Detections(
            xyxy=det.xyxy,
            confidence=det.confidence,
            class_id=det.class_id,
        )
        return self._tracker.update_with_detections(detections)
