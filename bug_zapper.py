"""Bug zapper kill streak tracker."""

import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta

import numpy as np
import pygame
import sounddevice as sd
from termcolor import colored

if os.name == "nt":
    import msvcrt
else:
    import termios
    import tty

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Kill sounds and corresponding thresholds
KILL_SOUNDS = [
    ("First Blood", "sounds/first_blood.wav", 1),
    ("Killing Spree", "sounds/killing_spree.wav", 2),
    ("Rampage", "sounds/rampage.wav", 3),
    ("Dominating", "sounds/dominating.wav", 4),
    ("Unstoppable", "sounds/unstoppable.wav", 5),
    ("Godlike", "sounds/godlike.wav", 6),
]

# Multi kill sounds and corresponding thresholds
MULTI_KILL_SOUNDS = [
    ("Double Kill", "sounds/double_kill.wav", 2),
    ("Multi Kill", "sounds/multi_kill.wav", 3),
    ("Ultra Kill", "sounds/ultra_kill.wav", 4),
    ("Monster Kill", "sounds/monster_kill.wav", 5),
]

HEADSHOT_SOUND = "sounds/headshot.wav"

# Set input device index for the correct audio device
INPUT_DEVICE_INDEX = 2

# Set TEST_MODE to True for testing mode (manual trigger)
TEST_MODE = False
pygame.mixer.init()

# Initialize the kill and timing variables
LAST_KILL_TIME = None
KILL_COUNT = 0
MULTI_KILL_COUNT = 0
MULTI_KILL_WINDOW = timedelta(seconds=3) if TEST_MODE else timedelta(minutes=1)
START_TIME = datetime.now()
MULTI_KILL_EXPIRED = False

# Audio threshold for detecting loud sounds (like a zap)
TEST_THRESHOLD = 0.05
TRIGGER_THRESHOLD = 0.2
SAMPLE_RATE = 44100
SAMPLE_DURATION = 0.1  # Duration of each audio sample in seconds

# Quiet hours (don't play sounds during this window)
QUIET_HOURS_START = 0  # 12 AM
QUIET_HOURS_END = 8  # 8 AM


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
    global KILL_COUNT, LAST_KILL_TIME, MULTI_KILL_COUNT, MULTI_KILL_EXPIRED

    if during_quiet_hours():
        logger.info("Quiet hours in effect. Not counting kill.")
        return

    now = datetime.now()
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


def audio_callback(indata, frames, time, status):  # noqa: ARG001
    """Audio callback function to handle the audio input."""
    if status:
        logger.debug("Status: %s", status)
        logger.debug(status, flush=True)

    # Calculate RMS (root mean square) to detect loud bursts of sound
    volume = np.sqrt(np.mean(indata**2))
    if volume > TEST_THRESHOLD:
        logger.debug("Volume: %f", volume)
    if volume > TRIGGER_THRESHOLD:
        logger.info(colored("Zap detected!", "red"))
        handle_kill()


def main():
    """Start the audio stream and handle the logic."""
    logger.info("Started bug zapper kill streak tracker.")

    if TEST_MODE:

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
    else:
        midnight_reset_thread = threading.Thread(target=reset_at_midnight, daemon=True)
        midnight_reset_thread.start()
        try:
            device_info = sd.query_devices(kind="input")
            logger.debug("Using device: %s", device_info)
            with sd.InputStream(
                device=INPUT_DEVICE_INDEX,  # Specify the input device
                callback=audio_callback,
                channels=1,
                samplerate=SAMPLE_RATE,
                blocksize=int(SAMPLE_RATE * SAMPLE_DURATION),
                dtype="float32",
            ):
                logger.info("Audio stream started successfully.")
                while True:
                    check_multi_kill_window()
                    reset_kills()
                    time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Exiting.")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            logger.error("Make sure you have allowed microphone access to the terminal.")
            sys.exit(1)


if __name__ == "__main__":
    main()
