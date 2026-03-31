"""
Bounded background execution for webhook handlers.

Bulk uploads can fire hundreds or thousands of webhooks at once. Spawning one
thread per request exhausts the DB pool and memory; we queue work on a shared
ThreadPoolExecutor instead (see WEBHOOK_BACKGROUND_MAX_WORKERS).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None


def _max_workers() -> int:
    n = int(getattr(settings, "WEBHOOK_BACKGROUND_MAX_WORKERS", 2))
    return max(1, min(n, 128))


def get_webhook_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=_max_workers(),
            thread_name_prefix="webhook_bg",
        )
    return _executor


def submit_webhook_job(func: Callable[..., Any], *args: Any) -> None:
    """
    Run func(*args) on the shared executor. Tasks wait in FIFO order when load
    exceeds max_workers. Always closes DB connections for this thread after
    each task (executor threads are reused).
    """

    def _run() -> None:
        try:
            func(*args)
        except Exception:
            logger.exception(
                "Webhook background job failed func=%s",
                getattr(func, "__name__", repr(func)),
            )
        finally:
            close_old_connections()

    get_webhook_executor().submit(_run)
