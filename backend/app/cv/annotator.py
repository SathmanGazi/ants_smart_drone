from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np


# Consistent color per class_id (BGR for OpenCV)
_CLASS_COLORS: Dict[int, Tuple[int, int, int]] = {
    2: (59, 189, 255),   # car — amber
    3: (237, 125, 49),   # motorcycle — blue-orange
    5: (99, 214, 146),   # bus — green
    7: (204, 112, 255),  # truck — magenta
}
_DEFAULT_COLOR = (180, 180, 180)


class FrameAnnotator:
    """
    Draws bounding boxes, class+id labels, and a lightweight trail
    showing the last few centroids per track.
    """

    def __init__(
        self,
        class_names: List[str],
        trail_length: int = 24,
        roi_polygon: Optional[np.ndarray] = None,
        tripwire: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None,
        tripwire_labels: Tuple[str, str] = ("A", "B"),
    ) -> None:
        self.class_names = class_names
        self.trail_length = trail_length
        self._trails: Dict[int, Deque[Tuple[int, int]]] = defaultdict(
            lambda: deque(maxlen=trail_length)
        )
        # Last frame each trail was touched, used to evict stale entries
        # so memory stays bounded on long videos. Grace window is wide
        # enough to survive a brief occlusion (ByteTrack can reacquire
        # the same ID) without wiping the visible trail.
        self._trail_last_frame: Dict[int, int] = {}
        self._trail_grace_frames = 60
        self.roi_polygon = roi_polygon
        self.tripwire = tripwire
        self.tripwire_labels = tripwire_labels
        self.tripwire_counts: Dict[str, int] = {tripwire_labels[0]: 0, tripwire_labels[1]: 0}

    def annotate(
        self,
        frame: np.ndarray,
        tracker_ids: np.ndarray,
        xyxy: np.ndarray,
        class_ids: np.ndarray,
        confidences: np.ndarray,
        counted_set: set[int],
        total_counted: int,
        by_class: Dict[str, int],
        frame_idx: int,
        total_frames: int,
    ) -> np.ndarray:
        out = frame
        h, w = out.shape[:2]

        if self.roi_polygon is not None and len(self.roi_polygon) >= 3:
            pts = self.roi_polygon.astype(np.int32).reshape(-1, 1, 2)
            overlay = out.copy()
            cv2.fillPoly(overlay, [pts], (91, 157, 255))
            cv2.addWeighted(overlay, 0.08, out, 0.92, 0, dst=out)
            cv2.polylines(out, [pts], True, (91, 157, 255), 2, cv2.LINE_AA)

        # Draw boxes + trails
        for i, tid in enumerate(tracker_ids):
            tid_int = int(tid)
            cls_id = int(class_ids[i])
            color = _CLASS_COLORS.get(cls_id, _DEFAULT_COLOR)
            x1, y1, x2, y2 = xyxy[i].astype(int).tolist()
            is_counted = tid_int in counted_set

            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            self._trails[tid_int].append((cx, cy))
            self._trail_last_frame[tid_int] = frame_idx
            trail = list(self._trails[tid_int])
            for p in range(1, len(trail)):
                cv2.line(out, trail[p - 1], trail[p], color, 2, cv2.LINE_AA)

            thickness = 3 if is_counted else 2
            cv2.rectangle(out, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)

            cls_name = (
                self.class_names[cls_id]
                if 0 <= cls_id < len(self.class_names)
                else "obj"
            )
            label = f"#{tid_int} {cls_name} {confidences[i]:.2f}"
            self._draw_label(out, (x1, y1), label, color)

        # Evict trails whose track hasn't been seen for `_trail_grace_frames`.
        # Without this the dict accumulates every track_id ever produced —
        # harmless for correctness, but inflates RAM on long videos.
        cutoff = frame_idx - self._trail_grace_frames
        stale = [tid for tid, last in self._trail_last_frame.items() if last < cutoff]
        for tid in stale:
            self._trails.pop(tid, None)
            self._trail_last_frame.pop(tid, None)

        # Tripwire line
        if self.tripwire is not None:
            (x1, y1), (x2, y2) = self.tripwire
            p1 = (int(x1), int(y1))
            p2 = (int(x2), int(y2))
            cv2.line(out, p1, p2, (60, 220, 255), 2, cv2.LINE_AA)
            # Endpoint labels for direction clarity
            cv2.circle(out, p1, 5, (60, 220, 255), -1, cv2.LINE_AA)
            cv2.circle(out, p2, 5, (60, 220, 255), -1, cv2.LINE_AA)

        # HUD
        self._draw_hud(out, frame_idx, total_frames, total_counted, by_class)
        return out

    def _draw_label(
        self,
        img: np.ndarray,
        origin: Tuple[int, int],
        text: str,
        color: Tuple[int, int, int],
    ) -> None:
        x, y = origin
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.5
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
        pad = 4
        top_left = (x, max(0, y - th - 2 * pad))
        bottom_right = (x + tw + 2 * pad, max(0, y))
        cv2.rectangle(img, top_left, bottom_right, color, -1, cv2.LINE_AA)
        cv2.putText(
            img,
            text,
            (x + pad, y - pad),
            font,
            scale,
            (20, 20, 20),
            thickness,
            cv2.LINE_AA,
        )

    def _draw_hud(
        self,
        img: np.ndarray,
        frame_idx: int,
        total_frames: int,
        total_counted: int,
        by_class: Dict[str, int],
    ) -> None:
        h, w = img.shape[:2]
        panel_w = 260
        extra_rows = 1 if self.tripwire is not None else 0
        panel_h = 24 + 22 * (1 + max(1, len(by_class)) + extra_rows)
        overlay = img.copy()
        cv2.rectangle(overlay, (12, 12), (12 + panel_w, 12 + panel_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, img, 0.45, 0, dst=img)

        cv2.putText(
            img,
            f"Unique vehicles: {total_counted}",
            (24, 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        y = 62
        if by_class:
            for cls, n in sorted(by_class.items()):
                cv2.putText(
                    img,
                    f"{cls}: {n}",
                    (24, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (220, 220, 220),
                    1,
                    cv2.LINE_AA,
                )
                y += 22
        else:
            cv2.putText(
                img,
                "no vehicles counted yet",
                (24, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (180, 180, 180),
                1,
                cv2.LINE_AA,
            )
            y += 22

        if self.tripwire is not None:
            la, lb = self.tripwire_labels
            trip_txt = f"tripwire {la}: {self.tripwire_counts.get(la,0)}  {lb}: {self.tripwire_counts.get(lb,0)}"
            cv2.putText(
                img,
                trip_txt,
                (24, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (60, 220, 255),
                1,
                cv2.LINE_AA,
            )

        # Progress bar
        bar_y = h - 20
        bar_w = w - 24
        pct = 0.0 if total_frames <= 0 else min(1.0, frame_idx / total_frames)
        cv2.rectangle(img, (12, bar_y), (12 + bar_w, bar_y + 8), (50, 50, 50), -1)
        cv2.rectangle(
            img,
            (12, bar_y),
            (12 + int(bar_w * pct), bar_y + 8),
            (80, 200, 120),
            -1,
        )
