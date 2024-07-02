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
        self.logging_threshold = 0.0
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

    def reinit_mixer(self):
        """Reinitialize the Pygame mixer."""
        try:
            pygame.mixer.quit()
            pygame.mixer.init()
            self.logger.info("Pygame mixer reinitialized successfully.")
            return True
        except pygame.error as e:
            self.logger.error("Failed to reinitialize Pygame mixer: %s", str(e))
            return False

    def play_sound(self, file, label):
        """Play the sound file and log the event."""
        self.logger.info("Playing sound: %s", label)
        try:
            pygame.mixer.music.load(file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except pygame.error as e:
            self.logger.error("Failed to play sound: %s", str(e))
            if "mixer not initialized" in str(e):
                if self.reinit_mixer():
                    self.logger.info("Retrying to play sound after mixer reinitialization.")
                    self.play_sound(file, label)
                else:
                    self.logger.error("Unable to reinitialize mixer. Sound playback failed.")

    def audio_callback(self, in_data, frames, time_info, status):  # noqa: ARG001,ARG002
        """Audio callback function to handle the audio input."""
        if status:
            self.logger.debug("Status: %s", status)

        # Convert the audio data to a numpy array
        audio_data = np.frombuffer(in_data, dtype=np.int16)

        # Check if audio_data is empty
        if audio_data.size == 0:
            self.logger.warning("Received empty audio data")
            return

        # Calculate RMS (root mean square) to detect loud bursts of sound
        # Use np.abs() to ensure we're not taking the square root of a negative number
        # Use np.maximum to avoid division by zero
        mean_square = np.mean(np.abs(audio_data) ** 2)
        volume = np.sqrt(np.maximum(mean_square, 1e-10))  # Avoid sqrt of values very close to zero

        if volume > self.logging_threshold:
            self.logger.debug("Volume: %s", volume)
        if volume > self.trigger_threshold:
            self.logger.info(colored("Zap detected!", "red"))
            self.bug_zapper.handle_kill()
