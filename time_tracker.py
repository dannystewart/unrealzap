import threading
import time
from datetime import datetime, timedelta

from dsutil.log import LocalLogger


class TimeTracker:
    """Track time."""

    def __init__(self, kill_tracker):
        self.logger = LocalLogger.setup_logger(self.__class__.__name__)

        self.kill_tracker = kill_tracker

        # Cooldown period (in seconds) to prevent retriggering
        self.cooldown_period = 4

        # Quiet hours (don't play sounds during this window)
        self.quiet_hours_start = 0  # 12 AM
        self.quiet_hours_end = 8  # 8 AM

        self.multi_kill_window = (
            timedelta(seconds=3) if self.kill_tracker.test_mode else timedelta(minutes=1)
        )
        self.start_time = datetime.now()
        self.last_detection_time = None
        self.multi_kill_expired = False
        self.last_kill_time = None

        # Log at startup
        self.logger.debug(
            "Quiet hours: start %s, end %s",
            self.format_hour(self.quiet_hours_start),
            self.format_hour(self.quiet_hours_end),
        )

        # Start thread for midnight reset
        self.midnight_reset_thread = threading.Thread(target=self.reset_at_midnight, daemon=True)
        self.midnight_reset_thread.start()

    def format_hour(self, hour):
        """Format hour in 12-hour time without leading zeros."""
        if hour == 0:
            return "12 AM"
        elif hour < 12:
            return f"{hour} AM"
        elif hour == 12:
            return "12 PM"
        else:
            return f"{hour - 12} PM"

    def reset_at_midnight(self):
        """Reset kills at midnight."""
        while True:
            now = datetime.now()
            next_reset = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
            time_until_reset = (next_reset - now).seconds / 60
            display_time = time_until_reset if time_until_reset < 60 else time_until_reset / 60
            duration_str = "minutes" if time_until_reset < 60 else "hours"
            self.logger.debug("%.1f %s until midnight reset.", round(display_time, 1), duration_str)
            time.sleep(time_until_reset)
            self.reset_kills()

    def during_quiet_hours(self):
        """Check if the current time falls within quiet hours."""
        now = datetime.now().time()
        if self.quiet_hours_start <= self.quiet_hours_end:
            return self.quiet_hours_start <= now.hour < self.quiet_hours_end
        else:  # Overlapping midnight case
            return now.hour >= self.quiet_hours_start or now.hour < self.quiet_hours_end

    def time_until_quiet_hours_end(self):
        """Calculate time until quiet hours end."""
        now = datetime.now()
        if self.quiet_hours_start <= self.quiet_hours_end:
            end_time = now.replace(hour=self.quiet_hours_end, minute=0, second=0, microsecond=0)
        else:
            end_time = (now + timedelta(days=1)).replace(
                hour=self.quiet_hours_end, minute=0, second=0, microsecond=0
            )

        if end_time <= now:
            end_time += timedelta(days=1)

        return end_time - now

    def reset_kills(self):
        """Reset the kill count if the time has passed."""
        now = datetime.now()
        if now - self.start_time >= timedelta(hours=24):
            self.logger.info("Cumulative kill timer reset.")
            self.kill_count = 0
            self.last_kill_time = None
            self.start_time = now

    def multi_kill_window_expired(self):
        """Set the multi-kill window to expired."""
        multi_kills = self.kill_tracker.multi_kill_count - 1
        self.logger.debug(
            "Multi-kill window expired after %s additional kill%s.\r",
            multi_kills,
            "s" if multi_kills != 1 else "",
        )
        self.multi_kill_expired = True

    def check_multi_kill_window(self):
        """Check if the multi-kill window has expired."""
        now = datetime.now()
        if (
            self.last_kill_time
            and now - self.last_kill_time > self.multi_kill_window
            and not self.multi_kill_expired
        ):
            self.multi_kill_window_expired()

    def in_cooldown(self, now):
        """Check if we're still in the cooldown period."""
        if (
            self.last_detection_time
            and (now - self.last_detection_time).total_seconds() < self.cooldown_period
        ):
            return True
        self.last_detection_time = now
        return False
