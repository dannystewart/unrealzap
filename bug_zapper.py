"""Bug zapper kill streak tracker."""

import signal
import sys

from dsutil.log import LocalLogger
from kill_tracker import KillTracker

# Set TEST_MODE to True for testing mode (manual trigger)
TEST_MODE = False

# Track whether to keep running
RUNNING = True

# Set up logger
logger = LocalLogger.setup_logger("main")


def signal_handler(sig, frame):  # noqa: ARG001
    """Signal handler to shut down the program."""
    print("Received shutdown signal. Exiting gracefully...")
    sys.exit(0)


# Set up signal handler to close the program
signal.signal(signal.SIGTERM, signal_handler)


def check_for_quiet_hours(kill_tracker):
    """Check for quiet hours and log."""
    if kill_tracker.time.during_quiet_hours():
        time_left = kill_tracker.time.time_until_quiet_hours_end()
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        logger.info(
            "Currently in quiet hours. %d hours and %d minutes until quiet hours end.",
            hours,
            minutes,
        )
    else:
        logger.debug("Not currently in quiet hours.")


def main():
    """Start the audio stream and handle the logic."""
    signal.signal(signal.SIGTERM, signal_handler)

    kill_tracker = KillTracker(TEST_MODE)
    logger.info("Started bug zapper kill streak tracker.")

    check_for_quiet_hours(kill_tracker)

    if kill_tracker.test_mode:
        kill_tracker.handle_test_mode()

    else:
        while RUNNING:
            try:
                kill_tracker.handle_live_mode()
            except KeyboardInterrupt:
                logger.info("Exiting.")
                sys.exit(0)
            except Exception as e:
                logger.error("Failed to start audio stream: %s", str(e))
                sys.exit(1)


if __name__ == "__main__":
    main()
