from typing import TYPE_CHECKING

import alsaaudio  # type: ignore # noqa: I201
import numpy as np
import pygame
from scipy.fftpack import fft
from scipy.signal import find_peaks
from termcolor import colored

from dsutil.log import LocalLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kill_tracker import KillTracker


class AudioHelper:
    """Helper class for audio handling."""

    def __init__(self, kill_tracker: "KillTracker"):
        self.logger = LocalLogger.setup_logger(self.__class__.__name__, message_only=True)

        self.kill_tracker = kill_tracker

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
        self.sample_rate = 16000

        # Track number of errors
        self.error_count = 0
        self.error_threshold = 10

        self.init_mixer()

    def init_audio_device(self) -> alsaaudio.PCM:
        """Open the audio device with all parameters set at initialization."""
        return alsaaudio.PCM(
            alsaaudio.PCM_CAPTURE,
            alsaaudio.PCM_NONBLOCK,
            device=self.input_device_name,
            channels=1,
            rate=self.sample_rate,
            format=alsaaudio.PCM_FORMAT_S16_LE,
            periodsize=1024,
        )

    def init_mixer(self) -> bool:
        """Initialize the Pygame mixer."""
        try:
            pygame.mixer.quit()
            pygame.mixer.init()
            self.logger.info("Pygame mixer initialized successfully.")
            return True
        except pygame.error as e:
            self.logger.error("Failed to initialize Pygame mixer: %s", str(e))
            return False

    def play_sound(self, file: str, label: str) -> None:
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

    def analyze_frequency(self, audio_data):
        """Analyze the frequency of sound data."""
        # Perform FFT
        fft_result = fft(audio_data)

        # Get the power spectrum
        power_spectrum = np.abs(fft_result) ** 2

        # Get corresponding frequencies
        freqs = np.fft.fftfreq(len(audio_data), 1 / self.sample_rate)

        # Only take the positive frequencies
        positive_freq_idx = np.where(freqs > 0)
        freqs = freqs[positive_freq_idx]
        power_spectrum = power_spectrum[positive_freq_idx]

        # Find the dominant frequency
        dominant_freq = freqs[np.argmax(power_spectrum)]

        # Calculate energy in different frequency bands
        low_freq_energy = np.sum(power_spectrum[(freqs > 100) & (freqs < 1000)])
        mid_freq_energy = np.sum(power_spectrum[(freqs > 1000) & (freqs < 5000)])
        high_freq_energy = np.sum(power_spectrum[freqs > 5000])

        return dominant_freq, low_freq_energy, mid_freq_energy, high_freq_energy

    def detect_zap(self, audio_data):
        """Detect zaps based on frequency analysis, waveform shape, and sharp attack with quick decay."""
        # Duration check
        duration = len(audio_data) / self.sample_rate
        if duration > 0.1:  # Longer than 100ms
            return False

        # Frequency analysis
        dominant_freq, low_energy, mid_energy, high_energy = self.analyze_frequency(audio_data)

        # Check for high frequency dominance (typical of electrical discharges)
        if dominant_freq < 5000:  # Adjust this threshold based on your observations
            return False

        # Check for energy distribution (zaps should have more energy in high frequencies)
        total_energy = low_energy + mid_energy + high_energy
        if total_energy == 0:
            return False
        high_energy_ratio = high_energy / total_energy
        if high_energy_ratio < 0.5:  # Adjust this threshold as needed
            return False

        # Waveform shape analysis
        envelope = np.abs(audio_data)
        peaks, _ = find_peaks(
            envelope, height=np.max(envelope) * 0.8, distance=len(audio_data) // 2
        )
        if len(peaks) != 1:  # We expect one clear peak for a zap
            return False

        # Check for sharp rise and quick decay
        peak_index = peaks[0]
        rise_time = peak_index / self.sample_rate
        decay_time = (len(audio_data) - peak_index) / self.sample_rate
        if rise_time > 0.01 or decay_time > 0.05:  # Adjust these thresholds as needed
            return False

        # Log the characteristics of the detected zap
        self.logger.debug(
            "Potential zap detected - Duration: %(duration).3fs, Dominant Frequency: %(freq).2fHz, High Energy Ratio: %(ratio).2f",
            {"duration": duration, "freq": dominant_freq, "ratio": high_energy_ratio},
        )

        return True

    def audio_callback(self, in_data, frames, time_info, status) -> None:  # noqa: ARG001,ARG002
        """Audio callback function to handle the audio input."""
        if status:
            self.logger.debug("Status: %s", status)

        self.logger.debug(
            "Received audio data length: %s. Expected frames: %s", len(in_data), frames
        )

        if len(in_data) <= 0:
            self.logger.warning("Received non-positive audio data length: %s", len(in_data))
            if self.error_count >= self.error_threshold:
                self.logger.info("Error threshold reached. Resetting internal state.")
                self.reset_internal_state()
            return

        self.error_count = 0  # Reset error count on successful data receipt

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

        if volume > self.kill_tracker.config.logging_threshold:
            self.logger.debug("Volume: %s", volume)

        if self.detect_zap(audio_data):
            self.logger.info(colored("Zap detected!", "red"))
            self.kill_tracker.handle_kill()

    def reset_internal_state(self) -> None:
        """Reset the error count and any other internal state variables."""
        self.error_count = 0
        self.logger.info("Internal state reset complete.")
