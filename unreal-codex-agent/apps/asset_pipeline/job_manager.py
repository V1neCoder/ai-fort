"""Async job manager for pipeline operations — runs generation in background threads."""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from typing import Any, Callable


class Job:
    """Represents a single pipeline job."""

    def __init__(self, job_id: str, prompt: str, project: str, auto_approve: bool):
        self.job_id = job_id
        self.prompt = prompt
        self.project = project
        self.auto_approve = auto_approve
        self.status: str = "queued"  # queued, running, completed, failed, cancelled
        self.progress: float = 0.0
        self.progress_message: str = "Queued"
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.created_at: float = time.time()
        self.started_at: float | None = None
        self.completed_at: float | None = None
        self._cancelled = threading.Event()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "job_id": self.job_id,
            "prompt": self.prompt,
            "project": self.project,
            "status": self.status,
            "progress": round(self.progress, 2),
            "progress_message": self.progress_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
        if self.result:
            d["result"] = self.result
        if self.error:
            d["error"] = self.error
        return d

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()


class JobManager:
    """Thread-safe async job manager for the asset pipeline."""

    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            from .pipeline import AssetPipeline
            self._pipeline = AssetPipeline()
        return self._pipeline

    def create_job(self, prompt: str, project: str = "default",
                   auto_approve: bool = False) -> str:
        """Create a new generation job and start it in a background thread.

        Returns the job_id immediately.
        """
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id, prompt, project, auto_approve)

        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(
            target=self._run_job,
            args=(job,),
            daemon=True,
            name=f"pipeline-job-{job_id}",
        )
        thread.start()

        return job_id

    def _run_job(self, job: Job) -> None:
        """Execute the pipeline in a background thread."""
        job.status = "running"
        job.started_at = time.time()
        job.progress_message = "Starting..."

        def on_progress(message: str, progress: float) -> None:
            if job.is_cancelled:
                raise InterruptedError("Job cancelled")
            job.progress_message = message
            job.progress = progress

        try:
            pipeline = self._get_pipeline()
            result = pipeline.generate(
                prompt=job.prompt,
                project=job.project,
                auto_approve=job.auto_approve,
                on_progress=on_progress,
            )
            job.result = result
            job.status = "completed"
            job.progress = 1.0
            job.progress_message = "Done"
        except InterruptedError:
            job.status = "cancelled"
            job.progress_message = "Cancelled"
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.progress_message = f"Failed: {e}"
        finally:
            job.completed_at = time.time()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return None
        return job.to_dict()

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in jobs[:limit]]

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status in ("completed", "failed", "cancelled"):
            return False
        job.cancel()
        return True

    def create_edit_job(self, asset_id: str, edit_prompt: str) -> str:
        """Create an async edit job for Model AI."""
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id, edit_prompt, "default", False)
        job.prompt = f"[EDIT:{asset_id}] {edit_prompt}"

        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(
            target=self._run_edit_job,
            args=(job, asset_id, edit_prompt),
            daemon=True,
            name=f"edit-job-{job_id}",
        )
        thread.start()

        return job_id

    def _run_edit_job(self, job: Job, asset_id: str, edit_prompt: str) -> None:
        """Execute an edit operation in a background thread."""
        job.status = "running"
        job.started_at = time.time()
        job.progress_message = "Editing model..."

        try:
            from .editor import edit_asset
            pipeline = self._get_pipeline()
            result = edit_asset(asset_id, edit_prompt, pipeline.registry)

            job.result = result
            job.status = "completed"
            job.progress = 1.0
            job.progress_message = "Edit complete"
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.progress_message = f"Edit failed: {e}"
        finally:
            job.completed_at = time.time()
