from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict, Any


class AbstractScheduler(ABC):
    """
    Abstract interface for scheduling tasks.
    All scheduler implementations must implement these methods.
    """

    @abstractmethod
    def start(self) -> None:
        """Start the scheduler."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the scheduler."""
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
            seconds: Seconds between runs
            minutes: Minutes between runs
            job_id: Optional unique identifier for the job
            **kwargs: Additional arguments to pass to the function

        Returns:
            str: The job ID
        """
        pass

    @abstractmethod
    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job.

        Args:
            job_id: The ID of the job to remove

        Returns:
            bool: True if job was removed, False otherwise
        """
        pass

    @abstractmethod
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a scheduled job.

        Args:
            job_id: The ID of the job to check

        Returns:
            Optional[Dict[str, Any]]: Job status information or None if not found
        """
        pass

    @abstractmethod
    def get_all_jobs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all scheduled jobs.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of all job statuses
        """
        pass
