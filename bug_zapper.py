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

TEST_MODE = True  # Set to True for testing mode (manual trigger)
pygame.mixer.init()

# Initialize the kill and timing variables
LAST_KILL_TIME = None
KILL_COUNT = 0
MULTI_KILL_COUNT = 0
MULTI_KILL_WINDOW = timedelta(seconds=3) if TEST_MODE else timedelta(minutes=2)
KILL_RESET_TIME = timedelta(minutes=1) if TEST_MODE else timedelta(hours=24)
START_TIME = datetime.now()
MULTI_KILL_EXPIRED = False

# Audio threshold for detecting loud sounds (like a zap)
AUDIO_THRESHOLD = 0.5
SAMPLE_RATE = 44100
SAMPLE_DURATION = 0.1  # Duration of each audio sample in seconds


def get_key():
    """Read a single keypress from the user."""
    if os.name == "nt":
        return msvcrt.getch().decode("utf-8")
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def play_sound(file, label):
    """Play the sound file and log the event."""
    logger.info(colored(f"Playing sound: {label}", "blue"))
    pygame.mixer.music.load(file)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        continue


def reset_kills():
    """Reset the kill count if the time has passed."""
    global KILL_COUNT, LAST_KILL_TIME, START_TIME
    now = datetime.now()
    if now - START_TIME >= KILL_RESET_TIME:
        logger.info("Cumulative kill timer reset.")
        KILL_COUNT = 0
        LAST_KILL_TIME = None
        START_TIME = now


def multi_kill_expired():
    """Set the multi-kill window to expired."""
    global MULTI_KILL_COUNT, MULTI_KILL_EXPIRED
    multi_kills = MULTI_KILL_COUNT - 1
    count_text = colored(
        f"{multi_kills} kill{'s' if multi_kills != 1 else ''}", f"{'yellow' if multi_kills > 0 else 'cyan'}"
    )
    expired_text = colored(f"Multi-kill window expired after {count_text}.", "cyan")
    logger.info("%s\r", expired_text)
    MULTI_KILL_EXPIRED = True


def check_multi_kill_window():
    """Check if the multi-kill window has expired."""
    global MULTI_KILL_EXPIRED, LAST_KILL_TIME
    now = datetime.now()
    if LAST_KILL_TIME and now - LAST_KILL_TIME > MULTI_KILL_WINDOW:
        if not MULTI_KILL_EXPIRED:
            multi_kill_expired()


def handle_kill():
    """Handle a single kill event."""
    global KILL_COUNT, LAST_KILL_TIME, MULTI_KILL_COUNT, MULTI_KILL_EXPIRED

    now = datetime.now()
    multi_kill_occurred = False

    if LAST_KILL_TIME and now - LAST_KILL_TIME <= MULTI_KILL_WINDOW:
        MULTI_KILL_COUNT += 1
        multi_kill_occurred = True
        if MULTI_KILL_COUNT in [sound[2] for sound in MULTI_KILL_SOUNDS]:
            sound = next(filter(lambda x: x[2] == MULTI_KILL_COUNT, MULTI_KILL_SOUNDS))
            play_sound(sound[1], sound[0])
    else:
        if LAST_KILL_TIME and not MULTI_KILL_EXPIRED:
            multi_kill_expired()
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

    logger.debug(colored(f"Total kills so far: {KILL_COUNT}", "yellow"))


def audio_callback(indata, status):
    """Audio callback function to handle the audio input."""
    if status:
        logger.debug(status, flush=True)

    # Calculate RMS (root mean square) to detect loud bursts of sound
    volume = np.sqrt(np.mean(indata**2))
    if volume > AUDIO_THRESHOLD:
        logger.debug(colored("Zap detected!", "red"))
        handle_kill()


def main():
    """Start the audio stream and handle the logic."""
    logger.info(colored("Started bug zapper kill streak tracker.", "green"))

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
                print(colored("Exiting.", "green"))
                sys.exit(0)
    else:
        with sd.InputStream(
            callback=audio_callback,
            channels=1,
            samplerate=SAMPLE_RATE,
            blocksize=int(SAMPLE_RATE * SAMPLE_DURATION),
            dtype="float32",
        ):
            while True:
                try:
                    check_multi_kill_window()
                    reset_kills()
                    time.sleep(1)
                except KeyboardInterrupt:
                    print(colored("Exiting.", "green"))
                    sys.exit(0)


if __name__ == "__main__":
    main()
