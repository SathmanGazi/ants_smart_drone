from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


def _side(line: Tuple[Tuple[float, float], Tuple[float, float]], p: Tuple[float, float]) -> float:
    """
    Signed 2D cross product of line-vector and (point - line_start).
    Positive on one side, negative on the other, zero on the line.
    """
    (x1, y1), (x2, y2) = line
    return (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1)


@dataclass
class CrossingEvent:
    track_id: int
    frame: int
    timestamp: float
    vehicle_class: str
    direction: str  # label_a or label_b


@dataclass
class TripwireCounter:
    """
    Virtual tripwire. Each tracked centroid is classified onto one side
    of the line; a sign change = a crossing. Direction is named by the
    configured A/B labels — A when crossing from the B-side to the A-side
    (positive cross product becomes negative → this convention matches the
    right-hand rule: A is 'to the right of line A→B as you walk from p1
    to p2'. Reverse labels if counts come out swapped for your scene).

    Each track_id is counted at most once per direction per lifetime,
    which prevents a vehicle wobbling across the line from inflating the
    count. This is consistent with the app's unique-vehicle philosophy.
    """

    p1: Tuple[float, float]
    p2: Tuple[float, float]
    label_a: str = "A"
    label_b: str = "B"

    _last_side: Dict[int, float] = field(default_factory=dict)
    _crossed: Dict[int, set] = field(default_factory=dict)  # tid -> {"A","B"}
    events: List[CrossingEvent] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.counts = {self.label_a: 0, self.label_b: 0}

    def update(
        self,
        frame_idx: int,
        fps: float,
        tracker_ids: np.ndarray,
        xyxy: np.ndarray,
        class_ids: np.ndarray,
        class_names: List[str],
    ) -> List[CrossingEvent]:
        fired: List[CrossingEvent] = []
        line = (self.p1, self.p2)
        for i, tid in enumerate(tracker_ids):
            tid_int = int(tid)
            cx = float((xyxy[i, 0] + xyxy[i, 2]) / 2.0)
            cy = float((xyxy[i, 1] + xyxy[i, 3]) / 2.0)
            s = _side(line, (cx, cy))
            prev = self._last_side.get(tid_int)
            self._last_side[tid_int] = s
            if prev is None or s == 0 or prev == 0:
                continue
            if (prev > 0) == (s > 0):
                continue  # same side, no crossing

            # Sign flipped → crossing. Direction by the side we moved TO.
            direction = self.label_a if s < 0 else self.label_b
            already = self._crossed.setdefault(tid_int, set())
            if direction in already:
                continue  # only count each direction once per track
            already.add(direction)

            cls_id = int(class_ids[i])
            cls_name = class_names[cls_id] if 0 <= cls_id < len(class_names) else "unknown"
            evt = CrossingEvent(
                track_id=tid_int,
                frame=frame_idx,
                timestamp=round(frame_idx / fps, 3) if fps > 0 else 0.0,
                vehicle_class=cls_name,
                direction=direction,
            )
            self.events.append(evt)
            self.counts[direction] = self.counts.get(direction, 0) + 1
            fired.append(evt)
        return fired

    def report(self) -> Tuple[Dict[str, int], List[dict]]:
        rows = [
            {
                "track_id": e.track_id,
                "frame": e.frame,
                "timestamp": e.timestamp,
                "vehicle_class": e.vehicle_class,
                "direction": e.direction,
            }
            for e in self.events
        ]
        rows.sort(key=lambda r: r["frame"])
        return dict(self.counts), rows


def parse_tripwire(spec: Optional[str]) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Accept '[[x1,y1],[x2,y2]]' JSON. Returns None if unset / malformed.
    """
    import json

    if not spec:
        return None
    try:
        data = json.loads(spec)
    except json.JSONDecodeError:
        return None
    if (
        not isinstance(data, list)
        or len(data) != 2
        or not all(isinstance(p, list) and len(p) == 2 for p in data)
    ):
        return None
    return (
        (float(data[0][0]), float(data[0][1])),
        (float(data[1][0]), float(data[1][1])),
    )
