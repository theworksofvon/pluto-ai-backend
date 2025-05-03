from typing import Callable, Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from logger import logger
from .abstract_scheduler import AbstractScheduler


class APSchedulerAdapter(AbstractScheduler):
    """
    APScheduler implementation of the AbstractScheduler interface.
    Uses APScheduler library for task scheduling.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.jobs: Dict[str, Dict[str, Any]] = {}

    def start(self) -> None:
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("APScheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("APScheduler stopped")

    def add_daily_job(
        self,
        func: Callable,
        hour: int,
        minute: int = 0,
        timezone: str = "America/New_York",
        job_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Add a job that runs daily at a specific time.

        Args:
            func: The function to run
            hour: Hour of the day (0-23)
            minute: Minute of the hour (0-59)
            timezone: Timezone for the schedule
            job_id: Optional unique identifier for the job
            **kwargs: Additional arguments to pass to the function

        Returns:
            str: The job ID
        """
        if job_id is None:
            job_id = f"daily_job_{len(self.jobs) + 1}"

        self.scheduler.add_job(
            func,
            CronTrigger(hour=hour, minute=minute, timezone=timezone),
            id=job_id,
            name=f"Daily job at {hour:02d}:{minute:02d}",
            replace_existing=True,
            **kwargs,
        )

        self.jobs[job_id] = {
            "type": "daily",
            "hour": hour,
            "minute": minute,
            "timezone": timezone,
            "function": func.__name__,
        }

        logger.info(
            f"Added daily job {job_id} scheduled for {hour:02d}:{minute:02d} {timezone}"
        )
        return job_id

    def add_interval_job(
        self,
        func: Callable,
        hours: int = 24,
        seconds: int = 0,
        minutes: int = 0,
        job_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Add a job that runs at regular intervals.

        Args:
            func: The function to run
            hours: Hours between runs
            job_id: Optional unique identifier for the job
            **kwargs: Additional arguments to pass to the function

        Returns:
            str: The job ID
        """
        if job_id is None:
            job_id = f"interval_job_{len(self.jobs) + 1}"

        self.scheduler.add_job(
            func,
            "interval",
            hours=hours,
            seconds=seconds,
            minutes=minutes,
            id=job_id,
            name=f"Interval job every {hours} hours and {minutes} minutes and {seconds} seconds",
            replace_existing=True,
            **kwargs,
        )

        self.jobs[job_id] = {
            "type": "interval",
            "hours": hours,
            "seconds": seconds,
            "minutes": minutes,
            "function": func.__name__,
        }

        logger.info(
            f"Added interval job {job_id} running every {hours} hours and {minutes} minutes and {seconds} seconds"
        )
        return job_id

    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job.

        Args:
            job_id: The ID of the job to remove

        Returns:
            bool: True if job was removed, False otherwise
        """
        try:
            self.scheduler.remove_job(job_id)
            self.jobs.pop(job_id, None)
            logger.info(f"Removed job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing job {job_id}: {e}")
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a scheduled job.

        Args:
            job_id: The ID of the job to check

        Returns:
            Optional[Dict[str, Any]]: Job status information or None if not found
        """
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                return {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time,
                    "job_info": self.jobs.get(job_id, {}),
                }
            return None
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return None

    def get_all_jobs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all scheduled jobs.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of all job statuses
        """
        return {job_id: self.get_job_status(job_id) for job_id in self.jobs.keys()}
