"""Background optimization thread management for ContextManager."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class BackgroundOptimizer:
    """Run context optimization in a background thread."""

    def __init__(self, optimize: Callable[[], None], interval: float) -> None:
        self._optimize = optimize
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.last_run: float = 0.0

    def start(self) -> None:
        """Start the optimization loop."""
        if self._thread and self._thread.is_alive():
            logger.warning("Background optimization thread already running")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.debug("Started background optimization thread")

    def stop(self) -> None:
        """Stop the optimization loop."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            logger.debug("Stopped background optimization thread")

    def _loop(self) -> None:
        while self._running:
            try:
                if time.time() - self.last_run >= self.interval:
                    self._optimize()
                    self.last_run = time.time()
                time.sleep(1.0)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Error in background optimization: %s", exc)
                time.sleep(5.0)
