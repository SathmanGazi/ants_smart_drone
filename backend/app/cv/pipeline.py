from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np

from app.config import settings
from app.cv.annotator import FrameAnnotator
from app.cv.counter import UniqueVehicleCounter
from app.cv.detector import VehicleDetector
from app.cv.tracker import VehicleTracker
from app.cv.tripwire import TripwireCounter, parse_tripwire

logger = logging.getLogger(__name__)


ProgressCallback = Callable[[int, int, float], None]
# (frame_idx, total_frames, processing_fps)


@dataclass
class PipelineResult:
    total_unique: int
    by_class: Dict[str, int]
    processing_duration_sec: float
    video_duration_sec: float
    fps: float
    total_frames: int
    counted_tracks: List[dict]
    rejected_tracks: List[dict]
    rejection_summary: Dict[str, int]
    sample_detections: List[dict]
    processed_video_path: Path
    result_json_path: Path
    tripwire_enabled: bool = False
    tripwire_counts: Dict[str, int] = None  # type: ignore[assignment]
    tripwire_crossings: List[dict] = None  # type: ignore[assignment]


class VideoPipeline:
    """
    End-to-end: read video → detect → track → count → annotate → write.
    Emits progress callbacks at a throttled cadence.
    """

    def __init__(
        self,
        input_path: Path,
        output_video_path: Path,
        result_json_path: Path,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> None:
        self.input_path = input_path
        self.output_video_path = output_video_path
        self.result_json_path = result_json_path
        self.progress_cb = progress_cb or (lambda *_: None)

    def run(self) -> PipelineResult:
        cap = cv2.VideoCapture(str(self.input_path))
        if not cap.isOpened():
            raise RuntimeError(
                f"Could not open video '{self.input_path.name}'. "
                "The file may be corrupted or use an unsupported codec."
            )

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

        if width <= 0 or height <= 0 or fps <= 0:
            cap.release()
            raise RuntimeError(
                "Video metadata unreadable (dims/fps). "
                "Try re-encoding the file with a standard H.264 pipeline."
            )

        video_duration = total_frames / fps if fps > 0 else 0.0

        detector = VehicleDetector()
        tracker = VehicleTracker(fps=fps)

        roi_points = settings.roi_polygon()
        roi_np = np.asarray(roi_points, dtype=np.float32) if roi_points else None
        counter = UniqueVehicleCounter(
            class_names=detector.class_names, roi_polygon=roi_np
        )

        trip_line = parse_tripwire(settings.tripwire_line_json)
        tripwire: Optional[TripwireCounter] = None
        if trip_line is not None:
            tripwire = TripwireCounter(
                p1=trip_line[0],
                p2=trip_line[1],
                label_a=settings.tripwire_label_a,
                label_b=settings.tripwire_label_b,
            )

        annotator = FrameAnnotator(
            class_names=detector.class_names,
            roi_polygon=roi_np,
            tripwire=trip_line,
            tripwire_labels=(settings.tripwire_label_a, settings.tripwire_label_b),
        )

        # NOTE: mp4v is broadly writable with OpenCV but not universally
        # playable in browsers. For HTML5-guaranteed playback, transcode
        # with ffmpeg after this step (documented hook in README).
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(
            str(self.output_video_path), fourcc, fps, (width, height)
        )
        if not writer.isOpened():
            cap.release()
            raise RuntimeError("Could not open VideoWriter for the processed output.")

        stride = max(1, settings.frame_stride)
        sample_detections: List[dict] = []
        sample_cap = 1000  # bound for API payload

        start = time.time()
        frame_idx = 0
        processed = 0

        # Adaptive progress throttle: emit at most every N frames, and
        # at least every 0.5 s wall-clock. On long videos the per-frame
        # gate alone produces 10k+ WS messages; on slow CPU the wall
        # gate keeps the UI honest if a single frame stalls.
        progress_every_n = max(1, settings.progress_every_n_frames)
        min_progress_interval_sec = 0.5
        last_progress_t = start
        last_progress_frame = -progress_every_n

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                if frame_idx % stride == 0:
                    det = detector.infer(frame)
                    tracks = tracker.update(det)

                    if tracks.tracker_id is not None and len(tracks) > 0:
                        newly = counter.update(
                            frame_idx=frame_idx,
                            tracker_ids=tracks.tracker_id,
                            xyxy=tracks.xyxy,
                            class_ids=tracks.class_id
                            if tracks.class_id is not None
                            else np.zeros(len(tracks), dtype=np.int32),
                            confidences=tracks.confidence
                            if tracks.confidence is not None
                            else np.zeros(len(tracks), dtype=np.float32),
                        )
                        if tripwire is not None:
                            tripwire.update(
                                frame_idx=frame_idx,
                                fps=fps,
                                tracker_ids=tracks.tracker_id,
                                xyxy=tracks.xyxy,
                                class_ids=tracks.class_id
                                if tracks.class_id is not None
                                else np.zeros(len(tracks), dtype=np.int32),
                                class_names=detector.class_names,
                            )
                            annotator.tripwire_counts = dict(tripwire.counts)
                        total_counted, by_class = counter.live_totals()

                        if len(sample_detections) < sample_cap:
                            for i in range(len(tracks)):
                                if len(sample_detections) >= sample_cap:
                                    break
                                cls_id = int(tracks.class_id[i])
                                cls_name = (
                                    detector.class_names[cls_id]
                                    if 0 <= cls_id < len(detector.class_names)
                                    else "unknown"
                                )
                                sample_detections.append(
                                    {
                                        "frame": frame_idx,
                                        "timestamp": round(frame_idx / fps, 3),
                                        "track_id": int(tracks.tracker_id[i]),
                                        "vehicle_class": cls_name,
                                        "confidence": round(
                                            float(tracks.confidence[i]), 4
                                        ),
                                        "bbox": [
                                            round(float(v), 1)
                                            for v in tracks.xyxy[i].tolist()
                                        ],
                                    }
                                )

                        annotated = annotator.annotate(
                            frame=frame,
                            tracker_ids=tracks.tracker_id,
                            xyxy=tracks.xyxy,
                            class_ids=tracks.class_id,
                            confidences=tracks.confidence,
                            counted_set=counter.counted_ids,
                            total_counted=total_counted,
                            by_class=by_class,
                            frame_idx=frame_idx,
                            total_frames=total_frames,
                        )
                    else:
                        total_counted, by_class = counter.live_totals()
                        annotated = annotator.annotate(
                            frame=frame,
                            tracker_ids=np.zeros((0,), dtype=np.int32),
                            xyxy=np.zeros((0, 4), dtype=np.float32),
                            class_ids=np.zeros((0,), dtype=np.int32),
                            confidences=np.zeros((0,), dtype=np.float32),
                            counted_set=counter.counted_ids,
                            total_counted=total_counted,
                            by_class=by_class,
                            frame_idx=frame_idx,
                            total_frames=total_frames,
                        )
                    writer.write(annotated)
                    processed += 1
                else:
                    # For skipped frames we still write the original to
                    # keep output duration aligned with input.
                    writer.write(frame)

                now = time.time()
                if (
                    frame_idx - last_progress_frame >= progress_every_n
                    and now - last_progress_t >= min_progress_interval_sec
                ):
                    elapsed = max(1e-6, now - start)
                    self.progress_cb(frame_idx, total_frames, processed / elapsed)
                    last_progress_frame = frame_idx
                    last_progress_t = now

                frame_idx += 1
        finally:
            cap.release()
            writer.release()

        # Final progress tick. Use `frame_idx` as total because
        # cv2.CAP_PROP_FRAME_COUNT regularly over-reports by 1-2 frames,
        # which otherwise pins the UI at ~99% forever.
        elapsed_total = time.time() - start
        self.progress_cb(frame_idx, frame_idx, processed / max(1e-6, elapsed_total))

        total_unique, by_class, counted_rows = counter.summary(fps)
        rejected_rows, rejection_summary = counter.rejection_report(fps)

        if tripwire is not None:
            tw_counts, tw_rows = tripwire.report()
        else:
            tw_counts, tw_rows = {}, []

        result = PipelineResult(
            total_unique=total_unique,
            by_class=by_class,
            processing_duration_sec=round(elapsed_total, 2),
            video_duration_sec=round(video_duration, 2),
            fps=round(fps, 3),
            total_frames=frame_idx,
            counted_tracks=counted_rows,
            rejected_tracks=rejected_rows,
            rejection_summary=rejection_summary,
            sample_detections=sample_detections,
            processed_video_path=self.output_video_path,
            result_json_path=self.result_json_path,
            tripwire_enabled=tripwire is not None,
            tripwire_counts=tw_counts,
            tripwire_crossings=tw_rows,
        )

        payload = {
            "total_unique": result.total_unique,
            "by_class": result.by_class,
            "processing_duration_sec": result.processing_duration_sec,
            "video_duration_sec": result.video_duration_sec,
            "fps": result.fps,
            "total_frames": result.total_frames,
            "counted_tracks": result.counted_tracks,
            "rejected_tracks": result.rejected_tracks,
            "rejection_summary": result.rejection_summary,
            "tripwire_enabled": result.tripwire_enabled,
            "tripwire_counts": result.tripwire_counts,
            "tripwire_crossings": result.tripwire_crossings,
            "sample_detections": result.sample_detections,
        }
        self.result_json_path.write_text(json.dumps(payload, indent=2))
        return result
