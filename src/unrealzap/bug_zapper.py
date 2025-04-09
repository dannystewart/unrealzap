"""Bug zapper kill tracker."""

from __future__ import annotations

import argparse
import signal
import sys

from polykit.log import PolyLog

from unrealzap.db_helper import DatabaseHelper
from unrealzap.kill_tracker import KillTracker

# Set TEST_MODE to True for testing mode (manual trigger)
TEST_MODE = False

# Track whether to keep running
RUNNING = True

# Set up logger
logger = PolyLog.get_logger("main", simple=True)


def signal_handler(sig, frame):  # type: ignore # noqa: ARG001
    """Signal handler to shut down the program."""
    print("Received shutdown signal. Exiting gracefully...")
    sys.exit(0)


# Set up signal handler to close the program
signal.signal(signal.SIGTERM, signal_handler)


def check_for_quiet_hours(kill_tracker: KillTracker) -> None:
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


def analysis_mode(db_helper: DatabaseHelper) -> None:
    """Enter analysis mode to monitor recent events and statistics."""
    while True:
        print("\n1. View recent events")
        print("2. View zap statistics")
        print("3. Exit")
        choice = input("Enter your choice: ")

        if choice == "1":
            events = db_helper.get_recent_events(10)
            if not events:
                print("No recent events found.")
            else:
                for event in events:
                    print(
                        f"ID: {event[0]}, Time: {event[1]}, Duration: {event[2]:.3f}, "
                        f"Dominant Freq: {event[3]:.2f}, High Energy Ratio: {event[4]:.2f}"
                    )
        elif choice == "2":
            stats = db_helper.get_zap_statistics()
            if stats and all(stat for stat in stats):
                print(f"Average Duration: {stats[0]:.3f}")
                print(f"Average Dominant Frequency: {stats[1]:.2f}")
                print(f"Average High Energy Ratio: {stats[2]:.2f}")
                print(f"Average Peak Amplitude: {stats[3]:.2f}")
            else:
                print("No zap statistics available yet.")
        elif choice == "3":
            break
        else:
            print("Invalid choice. Please try again.")


def main() -> None:
    """Start the audio stream and handle the logic based on command line arguments."""
    parser = argparse.ArgumentParser(description="Bug Zapper Kill Tracker")
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    parser.add_argument("--analysis", action="store_true", help="Run in analysis mode")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, signal_handler)

    db_helper = DatabaseHelper()
    kill_tracker = KillTracker(args.test, db_helper)

    logger.info("Started bug zapper kill tracker.")

    check_for_quiet_hours(kill_tracker)

    if args.test:
        logger.info("Running in test mode.")
        kill_tracker.handle_test_mode()
    elif args.analysis:
        logger.info("Running in analysis mode.")
        analysis_mode(db_helper)
    else:
        logger.info("Running in live mode.")
        kill_tracker.handle_live_mode()


if __name__ == "__main__":
    main()
