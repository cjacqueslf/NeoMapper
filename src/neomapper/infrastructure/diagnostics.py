"""Best-effort diagnostics for failures reported by the desktop interface."""
import logging
import traceback

from neomapper.infrastructure.paths import logs_dir


def record_exception(filename: str) -> None:
    details = traceback.format_exc()
    try:
        (logs_dir() / filename).write_text(details, encoding="utf-8")
    except OSError:
        logging.getLogger(__name__).error("Could not write diagnostic log: %s", details)
