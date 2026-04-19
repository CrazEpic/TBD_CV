"""
Violin Audio Synthesis Engine

Generates and plays violin notes based on:
- Note name (C, D, E, F#, etc.)
- Bow speed (0.0-1.0)
- Note duration

Uses sine wave synthesis with harmonics to approximate violin timbre.
"""

import numpy as np
import threading
from typing import Optional
import logging

# Try to import sounddevice, fall back to minimal implementation
try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False
    logging.warning("sounddevice not available. Audio playback will be silent.")


class AudioEngine:
    """Synthesizes and plays violin notes in real-time."""
    
    # MIDI note numbers for each note (middle C = 60)
    NOTE_TO_MIDI = {
        "C": 60, "C#": 61, "Db": 61,
        "D": 62, "D#": 63, "Eb": 63,
        "E": 64,
        "F": 65, "F#": 66, "Gb": 66,
        "G": 67, "G#": 68, "Ab": 68,
        "A": 69, "A#": 70, "Bb": 70,
        "B": 71,
    }
    
    def __init__(self, sample_rate: int = 44100):
        """
        Initialize audio engine.
        
        Args:
            sample_rate: Audio sample rate in Hz (default 44100)
        """
        self.sample_rate = sample_rate
        self.is_playing = False
        self.current_note = None
        self.current_thread = None
        self.stop_flag = False
        
    def midi_to_frequency(self, midi_note: int) -> float:
        """Convert MIDI note number to frequency in Hz."""
        return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
    
    def note_to_frequency(self, note_name: str) -> Optional[float]:
        """
        Convert note name to frequency.
        
        Args:
            note_name: Note name (e.g., "C", "D#", "Bb", etc.)
            
        Returns:
            Frequency in Hz, or None if note not recognized
        """
        midi_note = self.NOTE_TO_MIDI.get(note_name.upper())
        if midi_note is None:
            logging.warning(f"Unknown note: {note_name}")
            return None
        return self.midi_to_frequency(midi_note)
    
    def generate_violin_tone(
        self,
        frequency: float,
        duration: float,
        bow_speed: float = 1.0,
        amplitude: float = 0.3
    ) -> np.ndarray:
        """
        Generate a violin-like tone using sine wave with harmonics.
        
        Args:
            frequency: Base frequency in Hz
            duration: Duration in seconds
            bow_speed: Bow speed (0.0-1.0) - affects attack and volume
            amplitude: Base amplitude (0.0-1.0)
            
        Returns:
            Audio samples as numpy array
        """
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)
        
        # ADSR envelope
        attack_time = 0.05 / (bow_speed + 0.1)  # Faster attack with faster bow
        decay_time = 0.1
        sustain_level = 0.8
        release_time = 0.3
        
        # Create envelope
        envelope = np.ones_like(t)
        
        # Attack phase
        attack_samples = int(attack_time * self.sample_rate)
        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
        
        # Decay phase
        decay_start = attack_samples
        decay_end = decay_start + int(decay_time * self.sample_rate)
        if decay_end <= num_samples:
            envelope[decay_start:decay_end] = np.linspace(1, sustain_level, decay_end - decay_start)
        
        # Release phase
        release_start = num_samples - int(release_time * self.sample_rate)
        if release_start > 0:
            envelope[release_start:] = np.linspace(sustain_level, 0, num_samples - release_start)
        
        # Fundamental frequency
        fundamental = np.sin(2 * np.pi * frequency * t)
        
        # Add harmonics (2nd, 3rd, 5th) for violin-like timbre
        harmonic_2 = 0.3 * np.sin(2 * np.pi * frequency * 2 * t)
        harmonic_3 = 0.15 * np.sin(2 * np.pi * frequency * 3 * t)
        harmonic_5 = 0.1 * np.sin(2 * np.pi * frequency * 5 * t)
        
        # Mix harmonics
        signal = fundamental + harmonic_2 + harmonic_3 + harmonic_5
        signal = signal / np.max(np.abs(signal))  # Normalize
        
        # Apply envelope and amplitude
        signal = signal * envelope * amplitude * bow_speed
        
        return signal.astype(np.float32)
    
    def play_note(
        self,
        note_name: str,
        duration: float = 0.5,
        bow_speed: float = 1.0,
        wait: bool = False
    ) -> bool:
        """
        Play a single note.
        
        Args:
            note_name: Note name (e.g., "D#", "G", "F#")
            duration: Duration in seconds
            bow_speed: Bow speed (0.0-1.0)
            wait: If True, block until note finishes playing
            
        Returns:
            True if playback started, False otherwise
        """
        if not HAS_SOUNDDEVICE:
            return False
        
        # Stop any currently playing note
        self.stop()
        
        frequency = self.note_to_frequency(note_name)
        if frequency is None:
            return False
        
        # Generate audio
        audio_data = self.generate_violin_tone(
            frequency=frequency,
            duration=duration,
            bow_speed=max(0.1, min(1.0, bow_speed)),  # Clamp to 0.1-1.0
            amplitude=0.3
        )
        
        # Play in background thread
        if wait:
            sd.play(audio_data, self.sample_rate)
            sd.wait()
            return True
        else:
            self.stop_flag = False
            self.current_thread = threading.Thread(
                target=self._play_threaded,
                args=(audio_data,)
            )
            self.current_thread.daemon = True
            self.current_thread.start()
            return True
    
    def _play_threaded(self, audio_data: np.ndarray):
        """Internal method to play audio in a thread."""
        try:
            self.is_playing = True
            sd.play(audio_data, self.sample_rate)
            sd.wait()
        except Exception as e:
            logging.error(f"Error playing audio: {e}")
        finally:
            self.is_playing = False
    
    def stop(self):
        """Stop currently playing note."""
        if HAS_SOUNDDEVICE:
            sd.stop()
        self.is_playing = False
        self.stop_flag = True
    
    def play_continuous(
        self,
        note_name: str,
        bow_speed: float = 1.0,
        max_duration: float = 10.0
    ):
        """
        Start playing a note that continues until stop() is called.
        
        Args:
            note_name: Note name to play
            bow_speed: Bow speed (0.0-1.0)
            max_duration: Maximum duration to play before auto-stop (safety)
        """
        if not HAS_SOUNDDEVICE:
            return
        
        self.stop()
        
        frequency = self.note_to_frequency(note_name)
        if frequency is None:
            return
        
        self.stop_flag = False
        self.current_thread = threading.Thread(
            target=self._play_continuous_threaded,
            args=(frequency, bow_speed, max_duration)
        )
        self.current_thread.daemon = True
        self.current_thread.start()
    
    def _play_continuous_threaded(
        self,
        frequency: float,
        bow_speed: float,
        max_duration: float
    ):
        """Internal method for continuous playback."""
        try:
            self.is_playing = True
            chunk_duration = 0.1  # Play in 100ms chunks
            elapsed = 0.0
            
            while not self.stop_flag and elapsed < max_duration:
                # Generate next chunk
                audio_chunk = self.generate_violin_tone(
                    frequency=frequency,
                    duration=chunk_duration,
                    bow_speed=max(0.1, min(1.0, bow_speed)),
                    amplitude=0.3
                )
                
                # Play chunk
                sd.play(audio_chunk, self.sample_rate)
                sd.wait()
                
                elapsed += chunk_duration
        except Exception as e:
            logging.error(f"Error in continuous playback: {e}")
        finally:
            self.is_playing = False
    
    def cleanup(self):
        """Clean up audio resources."""
        self.stop()
        if HAS_SOUNDDEVICE:
            sd.close()


# Global audio engine instance
_audio_engine = None

def get_audio_engine(sample_rate: int = 44100) -> AudioEngine:
    """Get or create the global audio engine."""
    global _audio_engine
    if _audio_engine is None:
        _audio_engine = AudioEngine(sample_rate=sample_rate)
    return _audio_engine
