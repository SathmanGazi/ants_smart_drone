from __future__ import annotations

from pathlib import Path

from app.config import settings


class Storage:
    """
    Thin filesystem abstraction so we can swap to S3 / GCS later without
    touching the API or pipeline layers.
    """

    def upload_path(self, job_id: str, extension: str = "mp4") -> Path:
        return settings.uploads_dir / f"{job_id}.{extension}"

    def job_dir(self, job_id: str) -> Path:
        d = settings.outputs_dir / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def processed_video_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "processed.mp4"

    def result_json_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "result.json"

    def csv_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "report.csv"

    def xlsx_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "report.xlsx"


storage = Storage()
