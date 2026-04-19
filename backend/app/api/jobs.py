from __future__ import annotations

import json
import logging

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.schemas import (
    JobCreateResponse,
    JobRecord,
    JobResult,
    JobStatus,
)
from app.services import processor
from app.services.job_manager import job_manager
from app.services.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


ALLOWED_EXTENSIONS = {".mp4"}
ALLOWED_MIME_PREFIXES = ("video/",)


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_job(file: UploadFile) -> JobCreateResponse:
    filename = file.filename or "upload.mp4"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(sorted(ALLOWED_EXTENSIONS))} uploads are supported.",
        )

    if file.content_type and not file.content_type.startswith(ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"Unexpected content type '{file.content_type}'.",
        )

    record = await job_manager.create(filename=filename)

    target = storage.upload_path(record.id)
    size_bytes = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    try:
        async with aiofiles.open(target, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    await out.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {settings.max_upload_mb} MB limit.",
                    )
                await out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Upload failed for job %s", record.id)
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Failed to persist uploaded file.") from exc

    if size_bytes == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    processor.submit(record.id)

    return JobCreateResponse(
        job_id=record.id, status=record.status, filename=record.filename
    )


@router.get("/{job_id}", response_model=JobRecord)
async def get_job(job_id: str) -> JobRecord:
    job = await job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.get("/{job_id}/result", response_model=JobResult)
async def get_result(job_id: str) -> JobResult:
    job = await job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Job is '{job.status.value}', result not ready.",
        )

    result_path = storage.result_json_path(job_id)
    if not result_path.exists():
        raise HTTPException(status_code=500, detail="Result file missing on disk.")

    data = json.loads(result_path.read_text())

    return JobResult(
        job_id=job_id,
        total_unique=data["total_unique"],
        by_class=data["by_class"],
        processing_duration_sec=data["processing_duration_sec"],
        video_duration_sec=data["video_duration_sec"],
        fps=data["fps"],
        total_frames=data["total_frames"],
        counted_tracks=data["counted_tracks"],
        rejected_tracks=data.get("rejected_tracks", []),
        rejection_summary=data.get("rejection_summary", {}),
        tripwire_enabled=data.get("tripwire_enabled", False),
        tripwire_counts=data.get("tripwire_counts", {}),
        tripwire_crossings=data.get("tripwire_crossings", []),
        sample_detections=data.get("sample_detections", []),
        processed_video_url=f"/jobs/{job_id}/video",
        csv_url=f"/jobs/{job_id}/report.csv",
        xlsx_url=f"/jobs/{job_id}/report.xlsx",
    )


@router.get("/{job_id}/video")
async def get_video(job_id: str):
    path = storage.processed_video_path(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Processed video not found.")
    # FileResponse handles Range requests for <video> playback.
    return FileResponse(
        path, media_type="video/mp4", filename=f"processed_{job_id}.mp4"
    )


@router.get("/{job_id}/report.csv")
async def get_csv(job_id: str):
    path = storage.csv_path(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="CSV report not found.")
    return FileResponse(
        path, media_type="text/csv", filename=f"report_{job_id}.csv"
    )


@router.get("/{job_id}/report.xlsx")
async def get_xlsx(job_id: str):
    path = storage.xlsx_path(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="XLSX report not found.")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"report_{job_id}.xlsx",
    )
