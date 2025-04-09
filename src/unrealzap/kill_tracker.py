from __future__ import annotations

import sys
import threading
import time
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING

from polykit.cli import get_single_char_input
from polykit.formatters import TZ, color
from polykit.log import PolyLog

from unrealzap.audio_helper import AudioHelper
from unrealzap.config import ConfigManager
from unrealzap.time_tracker import TimeTracker

if TYPE_CHECKING:
    from unrealzap.db_helper import DatabaseHelper


class KillTracker:
    """Track kills."""

    def __init__(self, test_mode: bool, db_helper: DatabaseHelper) -> None:
        self.test_mode = test_mode
        self.logger = PolyLog.get_logger(self.__class__.__name__, simple=True)
        self.config = ConfigManager()
        self.db_helper = db_helper
        self.time = TimeTracker(self)
        self.audio = AudioHelper(self, db_helper)
        self.kill_count = 0
        self.multi_kill_count = 0
        self.zap_queue = deque(maxlen=100)  # Store last 100 zap times

        # Set up threaded database maintenance
        self.maintenance_thread = threading.Thread(target=self.periodic_maintenance, daemon=True)
        self.maintenance_thread.start()

    def handle_kill(self) -> None:
        """Handle a single kill event."""
        now = datetime.now(tz=TZ)

        if self.time.in_cooldown(now):
            self.logger.debug("Detection ignored due to cooldown period.")
            return

        if self.time.during_quiet_hours():
            return

        if not self.handle_multi_kill(now):
            self.handle_regular_kill()

        self.time.last_kill_time = now
        self.time.multi_kill_expired = False

        self.logger.debug("Kills so far today (excluding multi-kills): %s", self.kill_count)

    def handle_regular_kill(self) -> None:
        """Handle regular kill logic."""
        if self.time.last_kill_time and not self.time.multi_kill_expired:
            self.time.multi_kill_window_expired()
        self.multi_kill_count = 1
        self.kill_count += 1

        if self.kill_count > 6:
            self.audio.play_sound(self.audio.headshot_sound, "Headshot!")
        elif self.kill_count in [sound[2] for sound in self.audio.kill_sounds]:
            sound = next(filter(lambda x: x[2] == self.kill_count, self.audio.kill_sounds))
            self.audio.play_sound(sound[1], sound[0])

    def handle_multi_kill(self, now: datetime) -> bool:
        """Handle multi-kill logic."""
        if (
            self.time.last_kill_time
            and now - self.time.last_kill_time <= self.time.multi_kill_window
        ):
            self.multi_kill_count += 1
            if self.multi_kill_count in [sound[2] for sound in self.audio.multi_kill_sounds]:
                sound = next(
                    filter(
                        lambda x: x[2] == self.multi_kill_count,
                        self.audio.multi_kill_sounds,
                    )
                )
                self.audio.play_sound(sound[1], sound[0])
            return True
        return False

    def handle_test_mode(self) -> None:
        """Run the program in test mode."""

        def check_expirations() -> None:
            while True:
                self.time.check_multi_kill_window()
                self.time.reset_kills()
                time.sleep(1)

        expiration_thread = threading.Thread(target=check_expirations, daemon=True)
        expiration_thread.start()

        while True:
            try:
                self.logger.info(color("Press any key to simulate a zap.", "green"))
                get_single_char_input()
                self.logger.debug(color("Zap!", "cyan"))
                self.handle_kill()
            except KeyboardInterrupt:
                self.logger.info("Exiting.")
                sys.exit(0)

    def handle_live_mode(self) -> None:
        """Run the program in live mode."""
        inp = self.audio.init_audio_device()
        self.logger.info("Audio stream started successfully.")

        while True:
            try:
                lv, data = inp.read()
                if lv:
                    if lv > 0:
                        self.audio.audio_callback(data, lv, None, None)
                    else:
                        self.logger.warning("Received non-positive audio data length: %s", lv)
                else:
                    self.logger.debug("No audio data read")

                self.time.check_multi_kill_window()
                self.time.reset_kills()
                time.sleep(0.001)  # Small sleep to prevent CPU hogging
            except Exception as e:
                self.logger.error("Error in audio processing: %s", str(e))
                time.sleep(1)  # Wait a bit before trying again
                inp = self.audio.init_audio_device()  # Reinitialize audio device

    def periodic_maintenance(self):
        """Periodically perform database maintenance in a separate thread."""
        while True:
            try:
                self.logger.info("Starting database maintenance...")
                self.db_helper.maintain_database()
                self.logger.info("Database maintenance completed.")
            except Exception as e:
                self.logger.error("Error during database maintenance: %s", str(e))

            # Sleep for 1 hour before next maintenance
            time.sleep(3600)
