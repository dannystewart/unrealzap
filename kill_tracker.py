import logging
import sys
import threading
import time
from collections import deque
from datetime import datetime

from termcolor import colored

from audio_helper import AudioHelper
from db_helper import DatabaseHelper
from dsutil.log import LocalLogger
from dsutil.shell import get_single_char_input
from time_tracker import TimeTracker


class KillTracker:
    """Track kills."""

    def __init__(self, test_mode):
        self.test_mode = test_mode
        self.logger = LocalLogger.setup_logger(self.__class__.__name__)
        self.db_helper = DatabaseHelper()
        self.time = TimeTracker(self)
        self.audio = AudioHelper(self)
        self.kill_count = 0
        self.zap_queue = deque(maxlen=100)  # Store last 100 zap times

    def rate_limited_log(self, message, level=logging.INFO, limit=5):
        """Log a message with rate limiting."""
        current_time = time()
        self.zap_queue.append(current_time)

        if len(self.zap_queue) == 1 or current_time - self.zap_queue[0] > limit:
            self.logger.log(level, message)
            if len(self.zap_queue) > 1:
                self.logger.log(
                    level,
                    "Suppressed %s similar log messages in the last %s seconds.",
                    len(self.zap_queue) - 1,
                    limit,
                )
            self.zap_queue.clear()

    def handle_regular_kill(self):
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

    def handle_multi_kill(self, now):
        """Handle multi-kill logic."""
        if (
            self.time.last_kill_time
            and now - self.time.last_kill_time <= self.time.multi_kill_window
        ):
            self.multi_kill_count += 1
            if self.multi_kill_count > 5:
                self.audio.play_sound(self.audio.headshot_sound, "Headshot!")
            elif self.multi_kill_count in [sound[2] for sound in self.audio.multi_kill_sounds]:
                sound = next(
                    filter(lambda x: x[2] == self.multi_kill_count, self.audio.multi_kill_sounds)
                )
                self.audio.play_sound(sound[1], sound[0])
            return True
        return False

    def handle_kill(self):
        """Handle a single kill event."""
        now = datetime.now()

        if self.time.in_cooldown(now):
            self.logger.debug("Detection ignored due to cooldown period.")
            return

        if self.time.during_quiet_hours():
            self.rate_limited_log(
                "Zap detected during quiet hours. Not counting kill.", logging.DEBUG
            )
            return

        if not self.handle_multi_kill(now):
            self.handle_regular_kill()

        self.time.last_kill_time = now
        self.time.multi_kill_expired = False

        self.logger.debug("Kills so far today (excluding multi-kills): %s", self.kill_count)

    def handle_test_mode(self):
        """Run the program in test mode."""

        def check_expirations(self):
            while True:
                self.time.check.multi_kill_window()
                self.time.reset_kills()
                time.sleep(1)

        expiration_thread = threading.Thread(target=check_expirations, daemon=True)
        expiration_thread.start()
        while True:
            try:
                self.logger.info(colored("Press any key to simulate a zap.", "green"))
                get_single_char_input()
                self.logger.debug(colored("Zap!", "cyan"))
                self.handle_kill()
            except KeyboardInterrupt:
                self.logger.info("Exiting.")
                sys.exit(0)

    def handle_live_mode(self):
        """Run the program in live mode."""
        # Open the audio device with all parameters set at initialization
        inp = self.audio.init_audio_device()

        self.logger.info("Audio stream started successfully.")

        while True:  # Read data from device
            lv, data = inp.read()
            if lv:
                self.audio.audio_callback(data, lv, None, None)

            self.time.check_multi_kill_window()
            self.time.reset_kills()
            time.sleep(0.001)  # Small sleep to prevent CPU hogging
