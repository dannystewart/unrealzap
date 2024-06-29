"""Bug zapper kill streak tracker."""

import logging
import time
from datetime import datetime, timedelta

import numpy as np
import pygame
import sounddevice as sd
from termcolor import colored

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
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


def play_sound(file, label):
    """Play the sound file and log the event."""
    logger.debug(colored(f"Playing sound: {label}", "blue"))
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


def check_multi_kill_window():
    """Check if the multi-kill window has expired."""
    global MULTI_KILL_EXPIRED, LAST_KILL_TIME
    now = datetime.now()
    if LAST_KILL_TIME and now - LAST_KILL_TIME > MULTI_KILL_WINDOW:
        if not MULTI_KILL_EXPIRED:
            logger.debug("Multi-kill window expired.")
            MULTI_KILL_EXPIRED = True


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
            logger.debug("Multi-kill window expired.")
            MULTI_KILL_EXPIRED = True
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

    volume_norm = np.linalg.norm(indata) * 10
    threshold = 0.1

    if volume_norm > threshold:
        handle_kill()


def main():
    """Start the audio stream and handle the logic."""
    logger.info(colored("Started bug zapper kill streak tracker.", "green"))
    if TEST_MODE:
        import threading

        def check_expirations():
            while True:
                check_multi_kill_window()
                reset_kills()
                time.sleep(1)

        expiration_thread = threading.Thread(target=check_expirations, daemon=True)
        expiration_thread.start()

        while True:
            logger.info(colored("Press Enter to simulate a zap.", "green"))
            input()
            logger.debug(colored("Zap!", "cyan"))
            handle_kill()
    else:
        with sd.InputStream(callback=audio_callback):
            while True:
                check_multi_kill_window()
                reset_kills()
                time.sleep(1)


if __name__ == "__main__":
    main()
