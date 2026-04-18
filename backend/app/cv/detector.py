from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from app.config import settings


@dataclass
class RawDetection:
    xyxy: np.ndarray  # shape (N, 4)
    confidence: np.ndarray  # shape (N,)
    class_id: np.ndarray  # shape (N,)


class VehicleDetector:
    """
    Ultralytics YOLO wrapper. Loaded once per process. Filters to the
    COCO vehicle classes configured in settings.
    """

    _model = None
    _class_names: Optional[List[str]] = None

    def __init__(self) -> None:
        # Lazy import — keeps FastAPI startup snappy and avoids torch at
        # import time when tools introspect the module.
        from ultralytics import YOLO  # type: ignore

        if VehicleDetector._model is None:
            VehicleDetector._model = YOLO(settings.yolo_model)
            names = VehicleDetector._model.names
            if isinstance(names, dict):
                max_id = max(names.keys())
                arr = [""] * (max_id + 1)
                for k, v in names.items():
                    arr[int(k)] = v
                VehicleDetector._class_names = arr
            else:
                VehicleDetector._class_names = list(names)

    @property
    def class_names(self) -> List[str]:
        return VehicleDetector._class_names or []

    def infer(self, frame: np.ndarray) -> RawDetection:
        # verbose=False keeps stdout clean — the processor owns logging.
        results = VehicleDetector._model.predict(  # type: ignore[union-attr]
            source=frame,
            conf=settings.yolo_conf_threshold,
            iou=settings.yolo_iou_threshold,
            classes=settings.vehicle_class_ids,
            device=settings.yolo_device,
            imgsz=settings.yolo_imgsz,
            verbose=False,
        )
        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            return RawDetection(
                xyxy=np.zeros((0, 4), dtype=np.float32),
                confidence=np.zeros((0,), dtype=np.float32),
                class_id=np.zeros((0,), dtype=np.int32),
            )
        xyxy = r.boxes.xyxy.cpu().numpy().astype(np.float32)
        conf = r.boxes.conf.cpu().numpy().astype(np.float32)
        cls = r.boxes.cls.cpu().numpy().astype(np.int32)
        return RawDetection(xyxy=xyxy, confidence=conf, class_id=cls)
