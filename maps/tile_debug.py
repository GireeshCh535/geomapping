"""Small helpers for tile / R2 / proxy debug prints (grep: TILE_DEBUG, TILE_ROUTE)."""

from __future__ import annotations

import logging

from django.conf import settings

_route_logger = logging.getLogger("maps.tile_route")


def _tile_debug_enabled() -> bool:
    v = getattr(settings, "TILE_DEBUG_PRINTS", None)
    if v is True:
        return True
    if v is False:
        return False
    return bool(getattr(settings, "DEBUG", False))


def _emit(prefix: str, msg: str) -> None:
    line = f"{prefix} {msg}"
    print(line, flush=True)
    # Mirror to Django LOGGING (stderr) so lines show even if stdout is hidden; see maps.tile_route logger.
    _route_logger.info(line)


def tile_debug(msg: str) -> None:
    """Print when TILE_DEBUG_PRINTS is True, or False, or unset (then follows Django DEBUG)."""
    if _tile_debug_enabled():
        _emit("[TILE_DEBUG]", msg)


def tile_debug_always(msg: str) -> None:
    """Always print — use sparingly (SQS job boundaries, hard errors)."""
    line = f"[TILE_DEBUG] {msg}"
    print(line, flush=True)
    _route_logger.info(line)


def tile_route(msg: str) -> None:
    """Per-request tile routing (client → Django → CDN/R2/local). Same enable gate as tile_debug; grep: TILE_ROUTE."""
    if _tile_debug_enabled():
        _emit("[TILE_ROUTE]", msg)
