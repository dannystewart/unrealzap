from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from polykit.log import PolyLog


class ConfigManager:
    """Manage configuration values."""

    def __init__(self):
        self.logger = PolyLog.get_logger(self.__class__.__name__, simple=True)

        # Config file
        self.config_file = "config.json"

        # Initialize audio thresholds for detecting sounds
        self.logging_threshold = 0
        self.trigger_threshold = 0

        # How often to check the config file for changes
        self.config_check_interval = 60

        # Load initial config on startup
        self.load_config()

        # Start thread to watch for config changes
        self.config_thread = threading.Thread(target=self.check_config_updates, daemon=True)
        self.config_thread.start()

    def check_config_updates(self) -> None:
        """Periodically check for configuration updates."""
        while True:
            self.update_config()
            time.sleep(self.config_check_interval)

    def load_config(self) -> None:
        """Load configuration from file."""
        if Path(self.config_file).exists():
            with Path(self.config_file).open(encoding="utf-8") as f:
                config = json.load(f)
            self.logging_threshold = config.get("logging_threshold", 0.0)
            self.trigger_threshold = config.get("trigger_threshold", 120.0)

    def update_config(self) -> None:
        """Update configuration from file."""
        old_logging = self.logging_threshold
        old_trigger = self.trigger_threshold
        self.load_config()
        if old_logging != self.logging_threshold or old_trigger != self.trigger_threshold:
            self.logger.info(
                "Updated volume thresholds from config: logging %s, trigger %s",
                self.logging_threshold,
                self.trigger_threshold,
            )
