from __future__ import annotations

import asyncio
import time
import uuid
from typing import Dict, Optional

from app.schemas import JobProgress, JobRecord, JobStatus


class JobManager:
    """
    In-memory job registry. Interface is deliberately narrow so it can
    be re-implemented against Redis / Postgres without changing callers.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, filename: str) -> JobRecord:
        job_id = uuid.uuid4().hex
        record = JobRecord(
            id=job_id,
            filename=filename,
            status=JobStatus.QUEUED,
            created_at=time.time(),
        )
        async with self._lock:
            self._jobs[job_id] = record
        return record

    async def get(self, job_id: str) -> Optional[JobRecord]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def set_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None,
    ) -> Optional[JobRecord]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.status = status
            if status == JobStatus.PROCESSING and job.started_at is None:
                job.started_at = time.time()
            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                job.finished_at = time.time()
            if error is not None:
                job.error = error
            return job

    async def set_progress(self, job_id: str, progress: JobProgress) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.progress = progress


job_manager = JobManager()
