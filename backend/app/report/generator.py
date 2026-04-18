from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd


def write_csv(rows: List[dict], out_path: Path) -> None:
    if rows:
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(
            columns=[
                "track_id",
                "vehicle_class",
                "first_seen_frame",
                "last_seen_frame",
                "first_seen_ts",
                "last_seen_ts",
                "total_hits",
                "median_confidence",
                "counted_at_frame",
            ]
        )
    df.to_csv(out_path, index=False)


def write_xlsx(
    rows: List[dict],
    out_path: Path,
    *,
    total_unique: int,
    by_class: Dict[str, int],
    processing_duration_sec: float,
    video_duration_sec: float,
    fps: float,
    total_frames: int,
    source_filename: str,
    rejected_rows: List[dict] | None = None,
    rejection_summary: Dict[str, int] | None = None,
) -> None:
    rejected_rows = rejected_rows or []
    rejection_summary = rejection_summary or {}

    summary_rows = [
        ("Source file", source_filename),
        ("Total unique vehicles", total_unique),
        ("Rejected candidate tracks", len(rejected_rows)),
        ("Processing duration (s)", processing_duration_sec),
        ("Video duration (s)", video_duration_sec),
        ("FPS", fps),
        ("Total frames", total_frames),
    ]
    summary_df = pd.DataFrame(summary_rows, columns=["Metric", "Value"])
    by_class_df = pd.DataFrame(
        sorted(by_class.items()), columns=["Vehicle class", "Count"]
    )
    detail_df = (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame(
            columns=[
                "track_id",
                "vehicle_class",
                "first_seen_frame",
                "last_seen_frame",
                "first_seen_ts",
                "last_seen_ts",
                "total_hits",
                "median_confidence",
                "counted_at_frame",
            ]
        )
    )
    rejections_df = (
        pd.DataFrame(rejected_rows)
        if rejected_rows
        else pd.DataFrame(
            columns=[
                "track_id",
                "vehicle_class",
                "first_seen_frame",
                "last_seen_frame",
                "first_seen_ts",
                "last_seen_ts",
                "total_hits",
                "displacement_px",
                "median_confidence",
                "rejection_reason",
            ]
        )
    )
    rejection_summary_df = pd.DataFrame(
        sorted(rejection_summary.items(), key=lambda x: -x[1]),
        columns=["Rejection reason", "Tracks"],
    )

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        by_class_df.to_excel(writer, sheet_name="By class", index=False)
        detail_df.to_excel(writer, sheet_name="Counted tracks", index=False)
        rejection_summary_df.to_excel(
            writer, sheet_name="Rejections summary", index=False
        )
        rejections_df.to_excel(writer, sheet_name="Rejected tracks", index=False)
