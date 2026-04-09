"""Processing jobs service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.enums import ProcessingJobStatus, ProcessingJobType
from app.domain.models import ProcessingJob


class ProcessingJobService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_job(self, session_id: str, job_type: ProcessingJobType) -> ProcessingJob:
        job = ProcessingJob(session_id=session_id, job_type=job_type, status=ProcessingJobStatus.pending)
        self.db.add(job)
        self.db.flush()
        return job

    def mark_running(self, job: ProcessingJob) -> None:
        job.status = ProcessingJobStatus.running
        job.attempts += 1
        self.db.add(job)

    def mark_success(self, job: ProcessingJob) -> None:
        job.status = ProcessingJobStatus.success
        job.error_message = None
        self.db.add(job)

    def mark_failed(self, job: ProcessingJob, error_message: str) -> None:
        job.status = ProcessingJobStatus.failed
        job.error_message = error_message[:4000]
        self.db.add(job)