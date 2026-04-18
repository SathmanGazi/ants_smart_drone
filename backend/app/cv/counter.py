from __future__ import annotations

import math
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from app.config import settings


# Cap long-lived per-track lists to avoid unbounded memory growth on
# very long videos (30-60+ min). A track alive for 90k frames would
# otherwise retain 90k floats; we care about representative stats, not
# an exhaustive log.
_MAX_CONF_SAMPLES = 512


@dataclass
class TrackState:
    track_id: int
    first_frame: int
    last_frame: int
    total_hits: int = 0
    hit_streak: int = 0
    class_votes: Counter = field(default_factory=Counter)
    # Reservoir sample of confidences — bounded even for tracks alive
    # across a full 50-min clip. Median over a 512-sample reservoir is
    # within ~1% of the true median, which is plenty for reporting.
    confidences: Deque[float] = field(
        default_factory=lambda: deque(maxlen=_MAX_CONF_SAMPLES)
    )
    trajectory: Deque[Tuple[float, float]] = field(
        default_factory=lambda: deque(maxlen=64)
    )
    counted: bool = False
    counted_at_frame: Optional[int] = None
    # True iff this track was born as a soft re-ID carry-over of an
    # already-counted track. We mark it `counted` to prevent *recounting*,
    # but it must NOT appear as its own row in the report.
    inherited: bool = False

    def majority_class(self) -> int:
        if not self.class_votes:
            return -1
        return self.class_votes.most_common(1)[0][0]

    def total_displacement(self) -> float:
        if len(self.trajectory) < 2:
            return 0.0
        xs, ys = zip(*self.trajectory)
        return math.hypot(xs[-1] - xs[0], ys[-1] - ys[0])

    def median_confidence(self) -> float:
        if not self.confidences:
            return 0.0
        return float(np.median(self.confidences))


class UniqueVehicleCounter:
    """
    The heart of the app. Decides when a tracked ID becomes a *counted*
    vehicle.

    Strategy (see README for the rationale):

      1. Require a minimum number of hits AND a minimum consecutive hit
         streak before considering a track real.
      2. Require either non-trivial displacement OR a stationary-grace
         window. Handles both moving and parked vehicles without
         double-counting.
      3. Use majority-vote class assignment over the track's lifetime.
      4. Keep a permanent counted-ID set so recovered tracks cannot
         recount.
      5. Soft re-ID: if a new track ID is born near a recently-lost
         counted track's last position and matches class, inherit the
         counted flag.
      6. Optional ROI gate (polygon). Default: disabled (full frame).
    """

    def __init__(
        self,
        class_names: List[str],
        roi_polygon: Optional[np.ndarray] = None,
    ) -> None:
        self.class_names = class_names
        self.roi_polygon = roi_polygon  # shape (N, 2) or None
        self.states: Dict[int, TrackState] = {}
        self.counted_ids: set[int] = set()

        # Shadow state for re-ID across lost/resurrected IDs
        # (id -> (frame_lost, last_centroid, class_id))
        self._recent_lost: Dict[int, Tuple[int, Tuple[float, float], int]] = {}

        self.frame_idx = 0
        self._last_seen_ids: set[int] = set()

    # --- public API -------------------------------------------------------

    def update(
        self,
        frame_idx: int,
        tracker_ids: np.ndarray,
        xyxy: np.ndarray,
        class_ids: np.ndarray,
        confidences: np.ndarray,
    ) -> List[int]:
        """
        Returns the list of track_ids newly counted on this frame (for
        logging / events).
        """
        self.frame_idx = frame_idx
        newly_counted: List[int] = []
        current_ids: set[int] = set()

        for i, tid in enumerate(tracker_ids):
            tid_int = int(tid)
            current_ids.add(tid_int)

            cx = float((xyxy[i, 0] + xyxy[i, 2]) / 2.0)
            cy = float((xyxy[i, 1] + xyxy[i, 3]) / 2.0)

            if not self._inside_roi(cx, cy):
                continue

            state = self.states.get(tid_int)
            if state is None:
                state = self._maybe_inherit_from_lost(
                    tid_int, frame_idx, (cx, cy), int(class_ids[i])
                )
                self.states[tid_int] = state

            was_seen_last_frame = tid_int in self._last_seen_ids
            state.last_frame = frame_idx
            state.total_hits += 1
            state.hit_streak = state.hit_streak + 1 if was_seen_last_frame else 1
            state.class_votes[int(class_ids[i])] += 1
            state.confidences.append(float(confidences[i]))
            state.trajectory.append((cx, cy))

            if not state.counted and self._should_count(state):
                state.counted = True
                state.counted_at_frame = frame_idx
                self.counted_ids.add(tid_int)
                newly_counted.append(tid_int)

        # Mark tracks that disappeared this frame
        disappeared = self._last_seen_ids - current_ids
        for tid_int in disappeared:
            st = self.states.get(tid_int)
            if st is None:
                continue
            st.hit_streak = 0
            # Record for re-ID fallback only if it was counted.
            if st.counted and st.trajectory:
                self._recent_lost[tid_int] = (
                    frame_idx,
                    st.trajectory[-1],
                    st.majority_class(),
                )

        # Prune the re-ID shadow map
        cutoff = frame_idx - settings.reid_window_frames
        for k in [k for k, (f, _, _) in self._recent_lost.items() if f < cutoff]:
            self._recent_lost.pop(k, None)

        self._last_seen_ids = current_ids
        return newly_counted

    # --- counting gate ----------------------------------------------------

    def _should_count(self, st: TrackState) -> bool:
        if st.total_hits < settings.min_hits_to_count:
            return False
        if st.hit_streak < settings.min_streak:
            return False
        age = st.last_frame - st.first_frame + 1
        displacement = st.total_displacement()
        if (
            displacement < settings.min_displacement_px
            and age < settings.stationary_grace_frames
        ):
            return False
        return True

    # --- helpers ----------------------------------------------------------

    def _inside_roi(self, x: float, y: float) -> bool:
        if self.roi_polygon is None:
            return True
        # Ray-casting point-in-polygon test
        poly = self.roi_polygon
        inside = False
        n = len(poly)
        j = n - 1
        for i in range(n):
            xi, yi = poly[i]
            xj, yj = poly[j]
            intersect = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
            )
            if intersect:
                inside = not inside
            j = i
        return inside

    def _maybe_inherit_from_lost(
        self,
        new_id: int,
        frame: int,
        centroid: Tuple[float, float],
        class_id: int,
    ) -> TrackState:
        st = TrackState(track_id=new_id, first_frame=frame, last_frame=frame)
        best = None
        best_dist = settings.reid_distance_px
        for lost_id, (lost_frame, lost_xy, lost_cls) in self._recent_lost.items():
            if class_id != lost_cls:
                continue
            d = math.hypot(centroid[0] - lost_xy[0], centroid[1] - lost_xy[1])
            if d <= best_dist:
                best_dist = d
                best = lost_id
        if best is not None:
            st.counted = True
            st.counted_at_frame = frame
            # The original counted track is the authoritative row; this
            # re-emerged ID exists only to suppress a recount. It is
            # excluded from summary() via the `inherited` flag so we
            # don't double-report the same physical vehicle.
            st.inherited = True
            self._recent_lost.pop(best, None)
        return st

    # --- reporting --------------------------------------------------------

    def summary(self, fps: float) -> Tuple[int, Dict[str, int], List[dict]]:
        by_class: Counter = Counter()
        rows: List[dict] = []
        for st in self.states.values():
            if not st.counted:
                continue
            # Soft re-ID carry-overs were marked counted only to suppress
            # a duplicate count. The parent track already has a row.
            if st.inherited:
                continue
            cls_id = st.majority_class()
            cls_name = (
                self.class_names[cls_id]
                if 0 <= cls_id < len(self.class_names)
                else "unknown"
            )
            by_class[cls_name] += 1
            rows.append(
                {
                    "track_id": st.track_id,
                    "vehicle_class": cls_name,
                    "first_seen_frame": st.first_frame,
                    "last_seen_frame": st.last_frame,
                    "first_seen_ts": st.first_frame / fps if fps > 0 else 0.0,
                    "last_seen_ts": st.last_frame / fps if fps > 0 else 0.0,
                    "total_hits": st.total_hits,
                    "median_confidence": round(st.median_confidence(), 4),
                    "counted_at_frame": st.counted_at_frame or st.first_frame,
                }
            )
        rows.sort(key=lambda r: r["counted_at_frame"])
        return sum(by_class.values()), dict(by_class), rows

    def rejection_reason(self, st: TrackState) -> str:
        """
        Human-readable reason the counting gate rejected a track.
        Mirrors the conditions in _should_count, evaluated at end-of-run.
        """
        if st.total_hits < settings.min_hits_to_count:
            return f"total_hits<{settings.min_hits_to_count}"
        if st.hit_streak < settings.min_streak:
            # hit_streak at end-of-run reflects the most recent run-length,
            # which is a reasonable proxy for "never seen consistently".
            return f"streak<{settings.min_streak}"
        age = st.last_frame - st.first_frame + 1
        disp = st.total_displacement()
        if disp < settings.min_displacement_px and age < settings.stationary_grace_frames:
            return f"displacement<{settings.min_displacement_px:.0f}px & age<{settings.stationary_grace_frames}f"
        return "unknown"

    def rejection_report(self, fps: float) -> Tuple[List[dict], Dict[str, int]]:
        """
        Returns (rows, summary_by_reason) for every track that was opened
        by the tracker but NOT counted. Purely diagnostic — confirms the
        counting gate is filtering out what we expect (flickers, stationary
        short-lived boxes, edge flashes), not real vehicles.
        """
        rows: List[dict] = []
        reasons: Counter = Counter()
        for st in self.states.values():
            if st.counted:
                continue
            cls_id = st.majority_class()
            cls_name = (
                self.class_names[cls_id]
                if 0 <= cls_id < len(self.class_names)
                else "unknown"
            )
            reason = self.rejection_reason(st)
            reasons[reason] += 1
            rows.append(
                {
                    "track_id": st.track_id,
                    "vehicle_class": cls_name,
                    "first_seen_frame": st.first_frame,
                    "last_seen_frame": st.last_frame,
                    "first_seen_ts": st.first_frame / fps if fps > 0 else 0.0,
                    "last_seen_ts": st.last_frame / fps if fps > 0 else 0.0,
                    "total_hits": st.total_hits,
                    "displacement_px": round(st.total_displacement(), 1),
                    "median_confidence": round(st.median_confidence(), 4),
                    "rejection_reason": reason,
                }
            )
        rows.sort(key=lambda r: r["first_seen_frame"])
        return rows, dict(reasons)
