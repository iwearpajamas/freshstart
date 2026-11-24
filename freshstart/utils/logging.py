"""Logging helpers for Freshstart."""

from __future__ import annotations

import logging


def setup_logging(verbose: bool = False) -> None:
    """Configure logging: DEBUG when *verbose*, otherwise WARNING."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
