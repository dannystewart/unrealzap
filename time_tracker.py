import threading
import time as time_module
from datetime import datetime, timedelta
from datetime import time as datetime_time

from dsutil.log import LocalLogger


class TimeTracker:
    """Track time."""

    def __init__(self, kill_tracker):
        self.logger = LocalLogger.setup_logger(self.__class__.__name__, message_only=True)

        self.kill_tracker = kill_tracker

        # Cooldown period (in seconds) to prevent retriggering
        self.cooldown_period = 3

        # Quiet hours (don't play sounds during these windows)
        self.quiet_hours = [
            ((0, 0), (8, 30)),  # 12 AM to 8:30 AM
            ((19, 45), (20, 30)),  # 7:45 PM to 8:30 PM
        ]

        # Multi kill window
        self.multi_kill_window_test = timedelta(seconds=3)
        self.multi_kill_window_live = timedelta(minutes=2)
        self.multi_kill_window = (
            self.multi_kill_window_test
            if self.kill_tracker.test_mode
            else self.multi_kill_window_live
        )
        self.start_time = datetime.now()
        self.last_detection_time = None
        self.multi_kill_expired = False
        self.last_kill_time = None

        # Log at startup
        self.logger.debug("Quiet hours: %s", self.format_quiet_hours())

        # Start thread for midnight reset
        self.midnight_reset_thread = threading.Thread(target=self.reset_at_midnight, daemon=True)
        self.midnight_reset_thread.start()

    def format_quiet_hours(self):
        """Format quiet hours for logging."""
        return ", ".join(
            [
                f"{self.format_time(start)} to {self.format_time(end)}"
                for start, end in self.quiet_hours
            ]
        )

    def format_time(self, time_tuple):
        """Format time tuple in 12-hour time without leading zeros."""
        hour, minute = time_tuple
        if hour == 0 and minute == 0:
            return "12:00 AM"
        elif hour < 12:
            return f"{hour}:{minute:02d} AM"
        elif hour == 12:
            return f"12:{minute:02d} PM"
        else:
            return f"{hour - 12}:{minute:02d} PM"

    def reset_at_midnight(self):
        """Reset kills at midnight."""
        while True:
            now = datetime.now()
            next_reset = datetime.combine(now.date() + timedelta(days=1), datetime_time())
            time_until_reset = (next_reset - now).total_seconds() / 60
            display_time = time_until_reset if time_until_reset < 60 else time_until_reset / 60
            duration_str = "minutes" if time_until_reset < 60 else "hours"
            self.logger.debug("%.1f %s until midnight reset.", round(display_time, 1), duration_str)
            time_module.sleep(time_until_reset * 60)
            self.reset_kills()

    def during_quiet_hours(self):
        """Check if the current time falls within any quiet hours window."""
        now = datetime.now().time()
        for start, end in self.quiet_hours:
            start_time = datetime_time(start[0], start[1])
            end_time = datetime_time(end[0], end[1])
            if start_time <= end_time:
                if start_time <= now < end_time:
                    return True
            else:  # Overlapping midnight case
                if now >= start_time or now < end_time:
                    return True
        return False

    def time_until_quiet_hours_end(self):
        """Calculate time until the end of the current or next quiet hours period."""
        now = datetime.now()
        current_time = now.time()

        # Check if we're currently in a quiet hours period
        for start, end in self.quiet_hours:
            start_time = datetime.time(start[0], start[1])
            end_time = datetime.time(end[0], end[1])

            if start_time <= end_time:
                if start_time <= current_time < end_time:
                    return datetime.combine(now.date(), end_time) - now
            else:  # Overlapping midnight case
                if current_time >= start_time or current_time < end_time:
                    if current_time >= start_time:
                        return datetime.combine(now.date() + timedelta(days=1), end_time) - now
                    else:
                        return datetime.combine(now.date(), end_time) - now

        # If not in quiet hours, find the next quiet hours period
        next_start = None
        for start, _ in self.quiet_hours:
            start_time = datetime.time(start[0], start[1])
            if start_time > current_time:
                if next_start is None or start_time < next_start:
                    next_start = start_time

        if next_start is None:
            # If no later period today, get the first period of the next day
            next_start = datetime.time(self.quiet_hours[0][0][0], self.quiet_hours[0][0][1])
            return datetime.combine(now.date() + timedelta(days=1), next_start) - now
        else:
            return datetime.combine(now.date(), next_start) - now

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
