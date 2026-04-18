from __future__ import annotations

import asyncio
import logging
import traceback
from functools import partial

from app.cv.encode import transcode_to_h264
from app.cv.pipeline import VideoPipeline
from app.report.generator import write_csv, write_xlsx
from app.schemas import JobProgress, JobStatus
from app.services.events import broker
from app.services.job_manager import job_manager
from app.services.storage import storage

logger = logging.getLogger(__name__)


async def _publish(job_id: str, payload: dict) -> None:
    await broker.publish(job_id, payload)


def _make_progress_cb(job_id: str, loop: asyncio.AbstractEventLoop):
    """
    The pipeline runs in a worker thread. Progress callback marshals
    async work back onto the main event loop.
    """

    def cb(frame_idx: int, total_frames: int, processing_fps: float) -> None:
        percent = 0.0
        if total_frames > 0:
            percent = round(min(100.0, frame_idx * 100.0 / total_frames), 2)
        progress = JobProgress(
            frame=frame_idx,
            total_frames=total_frames,
            percent=percent,
            fps_processing=round(processing_fps, 2),
        )
        asyncio.run_coroutine_threadsafe(
            job_manager.set_progress(job_id, progress), loop
        )
        asyncio.run_coroutine_threadsafe(
            _publish(
                job_id,
                {"type": "progress", "progress": progress.model_dump()},
            ),
            loop,
        )

    return cb


async def run_job(job_id: str) -> None:
    """
    Orchestrates a single job from queued → completed/failed.
    Swap this body for a Celery task to get multi-process execution.
    """
    loop = asyncio.get_running_loop()

    job = await job_manager.get(job_id)
    if job is None:
        logger.error("run_job: job %s not found", job_id)
        return

    await job_manager.set_status(job_id, JobStatus.PROCESSING)
    await _publish(job_id, {"type": "status", "status": JobStatus.PROCESSING.value})

    try:
        input_path = storage.upload_path(job_id)
        output_video = storage.processed_video_path(job_id)
        result_json = storage.result_json_path(job_id)

        pipeline = VideoPipeline(
            input_path=input_path,
            output_video_path=output_video,
            result_json_path=result_json,
            progress_cb=_make_progress_cb(job_id, loop),
        )

        # Pipeline is CPU/GPU heavy — run off the event loop.
        result = await loop.run_in_executor(None, pipeline.run)

        # Snap progress to 100% explicitly. The final in-loop tick lands
        # at frame_idx == decoded frames, which does not always equal
        # cv2's reported total_frames — this guarantees the UI bar fills.
        done_progress = JobProgress(
            frame=result.total_frames,
            total_frames=result.total_frames,
            percent=100.0,
            fps_processing=0.0,
            message="Finalizing reports",
        )
        await job_manager.set_progress(job_id, done_progress)
        await _publish(
            job_id, {"type": "progress", "progress": done_progress.model_dump()}
        )

        # Transcode the annotated output to browser-playable H.264.
        # Done on the executor because subprocess.run blocks.
        annotated_raw = storage.processed_video_path(job_id)
        web_tmp = annotated_raw.with_name("processed_web.mp4")
        transcoded = await loop.run_in_executor(
            None, transcode_to_h264, annotated_raw, web_tmp
        )
        if transcoded:
            # Atomic swap — the HTTP route keeps serving the same path.
            web_tmp.replace(annotated_raw)

        # Reports
        write_csv(result.counted_tracks, storage.csv_path(job_id))
        write_xlsx(
            result.counted_tracks,
            storage.xlsx_path(job_id),
            total_unique=result.total_unique,
            by_class=result.by_class,
            processing_duration_sec=result.processing_duration_sec,
            video_duration_sec=result.video_duration_sec,
            fps=result.fps,
            total_frames=result.total_frames,
            source_filename=job.filename,
            rejected_rows=result.rejected_tracks,
            rejection_summary=result.rejection_summary,
        )

        await job_manager.set_status(job_id, JobStatus.COMPLETED)
        await _publish(
            job_id,
            {
                "type": "status",
                "status": JobStatus.COMPLETED.value,
                "total_unique": result.total_unique,
                "by_class": result.by_class,
            },
        )
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        logger.error("Job %s failed: %s\n%s", job_id, exc, tb)
        await job_manager.set_status(
            job_id, JobStatus.FAILED, error=str(exc)[:500]
        )
        await _publish(
            job_id,
            {"type": "status", "status": JobStatus.FAILED.value, "error": str(exc)[:500]},
        )


def submit(job_id: str) -> None:
    """
    Fire-and-forget entry point that callers (API routes) use.
    Uses asyncio for the MVP; replace with a queue.enqueue(run_job, id)
    for Celery / RQ without changing the callers.
    """
    loop = asyncio.get_event_loop()
    loop.create_task(run_job(job_id))
