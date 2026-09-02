"""Research scheduler: APScheduler-driven periodic research tasks.

Runs a configurable set of jobs — the daily briefing (default 06:00 local),
hourly research collection and weekly memory consolidation — in a background
``AsyncIOScheduler`` attached to the running event loop. Jobs are lightweight
wrappers that open a fresh app context so they can be scheduled from the CLI
(``mysti research schedule``) or embedded in the API server without blocking.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from mysti.security.audit import AuditLog

logger = logging.getLogger(__name__)

# Keep the scheduler light: every job runs in its own task via to_thread-style
# coroutines (they only await I/O), so a slow source never blocks the loop.
JOB_DAILY_BRIEFING = "daily_briefing"
JOB_HOURLY_COLLECT = "hourly_collect"
JOB_WEEKLY_CONSOLIDATE = "weekly_consolidate"


@dataclass
class SchedulerConfig:
    """Timing configuration for the periodic research jobs."""

    briefing_hour: int = 6
    briefing_minute: int = 0
    collect_minutes: int = 60
    consolidate_day: str = "sun"
    consolidate_hour: int = 3
    consolidate_minute: int = 0
    enabled: bool = False


@dataclass
class ResearchScheduler:
    """Thin APScheduler wrapper wiring research/consolidation callbacks."""

    config: SchedulerConfig
    audit: AuditLog
    briefing_cb: Callable[[], Awaitable[None]] | None = None
    collect_cb: Callable[[], Awaitable[None]] | None = None
    consolidate_cb: Callable[[], Awaitable[None]] | None = None
    _scheduler: AsyncIOScheduler = field(default_factory=AsyncIOScheduler, init=False, repr=False)

    def _wrap(self, callback: Callable[[], Awaitable[None]]) -> Callable[[], Awaitable[None]]:
        """Wrap a callback so failures are logged and never crash the loop."""

        async def _run() -> None:
            try:
                await callback()
            except Exception as exc:  # noqa: BLE001 - scheduled jobs must not die
                logger.error("scheduled job %r failed: %s", getattr(callback, "__name__", "?"), exc)
                self.audit.log("research.scheduler", "job", status="failed", reason=str(exc))

        return _run

    def start(self) -> None:
        """Register and start the configured jobs.

        Only jobs with a callback are registered, so tests can inject a subset;
        when ``config.enabled`` is False the scheduler is not started at all.
        """
        if not self.config.enabled or self._scheduler.running:
            return
        if self.briefing_cb is not None:
            self._scheduler.add_job(
                self._wrap(self.briefing_cb),
                CronTrigger(hour=self.config.briefing_hour, minute=self.config.briefing_minute),
                id=JOB_DAILY_BRIEFING,
                replace_existing=True,
            )
        if self.collect_cb is not None:
            self._scheduler.add_job(
                self._wrap(self.collect_cb),
                IntervalTrigger(minutes=max(1, self.config.collect_minutes)),
                id=JOB_HOURLY_COLLECT,
                replace_existing=True,
            )
        if self.consolidate_cb is not None:
            self._scheduler.add_job(
                self._wrap(self.consolidate_cb),
                CronTrigger(
                    day_of_week=self.config.consolidate_day,
                    hour=self.config.consolidate_hour,
                    minute=self.config.consolidate_minute,
                ),
                id=JOB_WEEKLY_CONSOLIDATE,
                replace_existing=True,
            )
        self.audit.log(
            "research.scheduler.start",
            "scheduler",
            metadata={"jobs": list(self._scheduler.get_jobs())},
        )
        self._scheduler.start()

    def stop(self) -> None:
        """Shut the scheduler down if it is running."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self.audit.log("research.scheduler.stop", "scheduler")

    @property
    def running(self) -> bool:
        return self._scheduler.running

    def jobs(self) -> list[str]:
        """Return the ids of registered jobs."""
        return [job.id for job in self._scheduler.get_jobs()]
