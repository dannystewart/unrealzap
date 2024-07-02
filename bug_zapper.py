"""Bug zapper kill streak tracker."""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta

import alsaaudio
import numpy as np
import pygame
import sounddevice as sd
from termcolor import colored

if os.name == "nt":
    import msvcrt
else:
    import termios
    import tty


def signal_handler(sig, frame):  # noqa: ARG001
    """Signal handler to shut down the program."""
    print("Received shutdown signal. Exiting gracefully...")
    # Add any cleanup code here if necessary
    sys.exit(0)


# Set up signal handler to close the program
signal.signal(signal.SIGTERM, signal_handler)

# Set TEST_MODE to True for testing mode (manual trigger)
TEST_MODE = False

# Audio threshold for detecting loud sounds (like a zap)
LOGGING_THRESHOLD = 30.0
TRIGGER_THRESHOLD = 70.0

# Cooldown period (in seconds) to prevent retriggering
COOLDOWN_PERIOD = 4

# Quiet hours (don't play sounds during this window)
QUIET_HOURS_START = 0  # 12 AM
QUIET_HOURS_END = 8  # 8 AM

# Sounds and corresponding thresholds
HEADSHOT_SOUND = "sounds/headshot.wav"
KILL_SOUNDS = [
    ("First Blood", "sounds/first_blood.wav", 1),
    ("Killing Spree", "sounds/killing_spree.wav", 2),
    ("Rampage", "sounds/rampage.wav", 3),
    ("Dominating", "sounds/dominating.wav", 4),
    ("Unstoppable", "sounds/unstoppable.wav", 5),
    ("Godlike", "sounds/godlike.wav", 6),
]
MULTI_KILL_SOUNDS = [
    ("Double Kill", "sounds/double_kill.wav", 2),
    ("Multi Kill", "sounds/multi_kill.wav", 3),
    ("Ultra Kill", "sounds/ultra_kill.wav", 4),
    ("Monster Kill", "sounds/monster_kill.wav", 5),
]

# Set input device name
INPUT_DEVICE_NAME = "hw:0,0"

# Initialize the kill and timing variables
LAST_KILL_TIME = None
KILL_COUNT = 0
MULTI_KILL_COUNT = 0
MULTI_KILL_WINDOW = timedelta(seconds=3) if TEST_MODE else timedelta(minutes=1)
START_TIME = datetime.now()
MULTI_KILL_EXPIRED = False
LAST_DETECTION_TIME = None

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Initialize mixer
pygame.mixer.init()

# Track whether to keep running
running = True


def get_key():
    """Read a single keypress from the user."""
    if os.name == "nt":
        return msvcrt.getch().decode("utf-8")
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def reset_at_midnight():
    """Reset kills at midnight."""
    while True:
        now = datetime.now()
        next_reset = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        time_until_reset = (next_reset - now).seconds / 60
        display_time = time_until_reset if time_until_reset < 60 else time_until_reset / 60
        duration_str = "minutes" if time_until_reset < 60 else "hours"
        logger.debug("%.1f %s until midnight reset.", round(display_time, 1), duration_str)
        time.sleep(time_until_reset)
        reset_kills()


def during_quiet_hours():
    """Check if the current time falls within quiet hours."""
    now = datetime.now().time()
    if QUIET_HOURS_START <= QUIET_HOURS_END:
        return QUIET_HOURS_START <= now.hour < QUIET_HOURS_END
    else:  # Overlapping midnight case
        return now.hour >= QUIET_HOURS_START or now.hour < QUIET_HOURS_END


def play_sound(file, label):
    """Play the sound file and log the event."""
    logger.info("Playing sound: %s", label)
    pygame.mixer.music.load(file)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        continue


def reset_kills():
    """Reset the kill count if the time has passed."""
    global KILL_COUNT, LAST_KILL_TIME, START_TIME
    now = datetime.now()
    if now - START_TIME >= timedelta(hours=24):
        logger.info("Cumulative kill timer reset.")
        KILL_COUNT = 0
        LAST_KILL_TIME = None
        START_TIME = now


def multi_kill_window_expired():
    """Set the multi-kill window to expired."""
    global MULTI_KILL_COUNT, MULTI_KILL_EXPIRED
    multi_kills = MULTI_KILL_COUNT - 1
    logger.debug(
        "Multi-kill window expired after %s additional kill%s.\r",
        multi_kills,
        "s" if multi_kills != 1 else "",
    )
    MULTI_KILL_EXPIRED = True


def check_multi_kill_window():
    """Check if the multi-kill window has expired."""
    global MULTI_KILL_EXPIRED, LAST_KILL_TIME
    now = datetime.now()
    if LAST_KILL_TIME and now - LAST_KILL_TIME > MULTI_KILL_WINDOW and not MULTI_KILL_EXPIRED:
        multi_kill_window_expired()


def handle_kill():
    """Handle a single kill event."""
    global KILL_COUNT, LAST_KILL_TIME, MULTI_KILL_COUNT, MULTI_KILL_EXPIRED, LAST_DETECTION_TIME

    if during_quiet_hours():
        logger.info("Quiet hours in effect. Not counting kill.")
        return

    now = datetime.now()

    # Check if we're still in the cooldown period
    if LAST_DETECTION_TIME and (now - LAST_DETECTION_TIME).total_seconds() < COOLDOWN_PERIOD:
        logger.debug("Detection ignored due to cooldown period.")
        return

    LAST_DETECTION_TIME = now
    multi_kill_occurred = False

    if LAST_KILL_TIME and now - LAST_KILL_TIME <= MULTI_KILL_WINDOW:
        MULTI_KILL_COUNT += 1
        multi_kill_occurred = True
        if MULTI_KILL_COUNT > 5:
            play_sound(HEADSHOT_SOUND, "Headshot!")
        elif MULTI_KILL_COUNT in [sound[2] for sound in MULTI_KILL_SOUNDS]:
            sound = next(filter(lambda x: x[2] == MULTI_KILL_COUNT, MULTI_KILL_SOUNDS))
            play_sound(sound[1], sound[0])
    else:
        if LAST_KILL_TIME and not MULTI_KILL_EXPIRED:
            multi_kill_window_expired()
        MULTI_KILL_COUNT = 1
        KILL_COUNT += 1

    LAST_KILL_TIME = now
    MULTI_KILL_EXPIRED = False

    if not multi_kill_occurred:
        if KILL_COUNT > 6:
            play_sound(HEADSHOT_SOUND, "Headshot!")
        elif KILL_COUNT in [sound[2] for sound in KILL_SOUNDS]:
            sound = next(filter(lambda x: x[2] == KILL_COUNT, KILL_SOUNDS))
            play_sound(sound[1], sound[0])

    logger.debug("Kills so far today (excluding multi-kills): %s", KILL_COUNT)


def audio_callback(in_data, frames, time_info, status):  # noqa: ARG001
    """Audio callback function to handle the audio input."""
    if status:
        logger.debug(f"Status: {status}")

    # Convert the audio data to a numpy array
    audio_data = np.frombuffer(in_data, dtype=np.int16)

    # Calculate RMS (root mean square) to detect loud bursts of sound
    volume = np.sqrt(np.mean(audio_data**2))
    if volume > LOGGING_THRESHOLD:
        logger.debug(f"Volume: {volume}")
    if volume > TRIGGER_THRESHOLD:
        logger.info(colored("Zap detected!", "red"))
        handle_kill()


def find_input_device():
    """Find the input device that matches our criteria."""
    devices = sd.query_devices()
    for device in devices:
        if device["max_input_channels"] > 0 and "Luna" in device["name"]:
            return device["index"]
    raise ValueError("No suitable input device found")


def handle_test_mode():
    """Run the program in test mode."""

    def check_expirations():
        while True:
            check_multi_kill_window()
            reset_kills()
            time.sleep(1)

    expiration_thread = threading.Thread(target=check_expirations, daemon=True)
    expiration_thread.start()
    while True:
        try:
            logger.info(colored("Press any key to simulate a zap.", "green"))
            get_key()
            logger.debug(colored("Zap!", "cyan"))
            handle_kill()
        except KeyboardInterrupt:
            logger.info("Exiting.")
            sys.exit(0)


def handle_live_mode():
    """Run the program in live mode."""
    # Open the audio device
    inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK, device=INPUT_DEVICE_NAME)

    # Set attributes
    inp.setchannels(1)
    inp.setrate(16000)
    inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    inp.setperiodsize(1024)

    logger.info("Audio stream started successfully.")

    while True:  # Read data from device
        lv, data = inp.read()
        if lv:
            audio_callback(data, lv, None, None)

        check_multi_kill_window()
        reset_kills()
        time.sleep(0.001)  # Small sleep to prevent CPU hogging


def main():
    """Start the audio stream and handle the logic."""
    signal.signal(signal.SIGTERM, signal_handler)
    logger.info("Started bug zapper kill streak tracker.")
    logger.debug("Volume thresholds: logging %s, trigger %s", LOGGING_THRESHOLD, TRIGGER_THRESHOLD)

    if TEST_MODE:
        handle_test_mode()
    else:
        midnight_reset_thread = threading.Thread(target=reset_at_midnight, daemon=True)
        midnight_reset_thread.start()

        while running:
            try:
                handle_live_mode()

            except KeyboardInterrupt:
                logger.info("Exiting.")
                sys.exit(0)
            except Exception as e:
                logger.error(f"Failed to start audio stream: {e}")
                logger.error("Make sure you have allowed microphone access to the terminal.")
                sys.exit(1)


if __name__ == "__main__":
    main()
