import json
import os

import alsaaudio
import numpy as np
import pygame
from termcolor import colored

from dsutil.log import LocalLogger


class AudioHelper:
    """Helper class for audio handling."""

    def __init__(self, bug_zapper):
        self.logger = LocalLogger.setup_logger(self.__class__.__name__)
        self.bug_zapper = bug_zapper

        # Audio threshold for detecting loud sounds (like a zap)
        self.logging_threshold = 20.0
        self.trigger_threshold = 100.0

        # Sounds and corresponding thresholds
        self.headshot_sound = "sounds/headshot.wav"
        self.kill_sounds = [
            ("First Blood", "sounds/first_blood.wav", 1),
            ("Killing Spree", "sounds/killing_spree.wav", 2),
            ("Rampage", "sounds/rampage.wav", 3),
            ("Dominating", "sounds/dominating.wav", 4),
            ("Unstoppable", "sounds/unstoppable.wav", 5),
            ("Godlike", "sounds/godlike.wav", 6),
        ]
        self.multi_kill_sounds = [
            ("Double Kill", "sounds/double_kill.wav", 2),
            ("Multi Kill", "sounds/multi_kill.wav", 3),
            ("Ultra Kill", "sounds/ultra_kill.wav", 4),
            ("Monster Kill", "sounds/monster_kill.wav", 5),
        ]

        # Set input device name
        self.input_device_name = "hw:0,0"

        # Config file
        self.config_file = "config.json"
        self.load_config(startup=True)

        # Log at startup
        self.logger.debug(
            "Volume thresholds: logging %s, trigger %s",
            self.logging_threshold,
            self.trigger_threshold,
        )

        self.error_count = 0
        self.error_threshold = 10

    def load_config(self, startup=False):
        """Load configuration from file."""
        if os.path.exists(self.config_file):
            with open(self.config_file) as f:
                config = json.load(f)
            self.logging_threshold = config.get("logging_threshold", 30.0)
            self.trigger_threshold = config.get("trigger_threshold", 70.0)
        else:
            self.logging_threshold = 30.0
            self.trigger_threshold = 70.0
        if startup:
            self.logger.info(
                "Loaded volume thresholds from config: logging %s, trigger %s",
                self.logging_threshold,
                self.trigger_threshold,
            )
            if self.logging_threshold == -1:
                self.logger.info("Volume logging is disabled.")
            if self.trigger_threshold == -1:
                self.logger.info("Zap triggering is disabled.")

    def update_config(self):
        """Update configuration from file."""
        old_logging = self.logging_threshold
        old_trigger = self.trigger_threshold
        self.load_config()
        if old_logging != self.logging_threshold or old_trigger != self.trigger_threshold:
            self.logger.info(
                "Updated volume thresholds from config: logging %s, trigger %s",
                self.logging_threshold,
                self.trigger_threshold,
            )

    def init_audio_device(self):
        """Open the audio device with all parameters set at initialization."""
        return alsaaudio.PCM(
            alsaaudio.PCM_CAPTURE,
            alsaaudio.PCM_NONBLOCK,
            device=self.input_device_name,
            channels=1,
            rate=16000,
            format=alsaaudio.PCM_FORMAT_S16_LE,
            periodsize=1024,
        )

    def play_sound(self, file, label):
        """Play the sound file and log the event."""
        self.logger.info("Playing sound: %s", label)
        pygame.mixer.music.load(file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy(self):
            continue

    def audio_callback(self, in_data, frames, time_info, status):  # noqa: ARG001,ARG002
        """Audio callback function to handle the audio input."""
        if status:
            self.logger.debug(f"Status: {status}")

        # Convert the audio data to a numpy array
        audio_data = np.frombuffer(in_data, dtype=np.int16)

        # Calculate RMS (root mean square) to detect loud bursts of sound
        volume = np.sqrt(np.mean(audio_data**2))
        if volume > self.logging_threshold:
            self.logger.debug(f"Volume: {volume}")
        if volume > self.trigger_threshold:
            self.logger.info(colored("Zap detected!", "red"))
            self.bug_zapper.handle_kill()
