#!/usr/bin/env python3
"""
Audio Processor Module
Handles audio processing, resampling, gain adjustment, and provides interception pipe for Phase 7 AI modules.

Features:
- Dynamic resampling to 8000 Hz, 16-Bit Mono PCM (Little Endian)
- Gain adjustment
- AGC (Automatic Gain Control) - optional
- Interception pipe for plugins (Phase 7: Noise Cancelling)
- Audio enhancement pipeline
"""

import logging
import struct
from queue import Queue
from typing import Optional, Callable, List, Dict, Any
import numpy as np

from audio_resampler import AudioResampler

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Processes audio data with resampling and provides interception pipe for AI modules."""
    
    def __init__(self, config: dict, input_queue: Queue, output_queue: Queue):
        """
        Initialize Audio Processor.
        
        Args:
            config: Configuration dictionary with 'audio' and 'processing' sections
            input_queue: Queue to get audio data from
            output_queue: Queue to put processed audio data
        """
        self.config = config
        self.audio_config = config.get('audio', {})
        self.processing_config = config.get('processing', {})
        self.input_queue = input_queue
        self.output_queue = output_queue
        
        # Audio parameters (target format)
        self.target_sample_rate = self.audio_config.get('sample_rate', 8000)
        self.target_channels = self.audio_config.get('channels', 1)
        self.sample_width = self.audio_config.get('sample_width', 2)
        self.bytes_per_sample = self.audio_config.get('bytes_per_sample', 2)
        self.samples_per_frame = self.audio_config.get('samples_per_frame', 160)
        
        # Initialize resampler
        self.resampler = AudioResampler(
            target_sample_rate=self.target_sample_rate,
            target_channels=self.target_channels
        )
        
        # Gain settings
        self.gain = self.audio_config.get('gain', 1.0)
        self.gain_min = self.audio_config.get('gain_min', 0.0)
        self.gain_max = self.audio_config.get('gain_max', 10.0)
        
        # AGC settings
        self.enable_agc = self.audio_config.get('enable_agc', False)
        self.agc_threshold_db = self.audio_config.get('agc_threshold_db', -20.0)
        self.agc_slope_db = self.audio_config.get('agc_slope_db', 10.0)
        self.agc_decay_ms = self.audio_config.get('agc_decay_ms', 100)
        
        # Interception pipe (Phase 7)
        self.interception_pipe_enabled = self.processing_config.get('enable_interception_pipe', True)
        self.interception_plugins: List[Callable] = []
        
        # Statistics
        self.processed_frames = 0
        self.dropped_frames = 0
        self.resampled_frames = 0
        
        logger.info(f"Audio Processor initialized: target={self.target_sample_rate}Hz, {self.target_channels} channel(s)")
        logger.info(f"Gain: {self.gain}, AGC: {self.enable_agc}, Interception Pipe: {self.interception_pipe_enabled}")
    
    def register_interception_plugin(self, plugin: Callable[[bytes], bytes]):
        """
        Register a plugin for the interception pipe (Phase 7: AI modules).
        
        Args:
            plugin: Callable that takes PCM audio bytes and returns processed PCM audio bytes
        """
        if not callable(plugin):
            raise ValueError("Plugin must be callable")
        
        self.interception_plugins.append(plugin)
        logger.info(f"Registered interception plugin: {plugin.__name__ if hasattr(plugin, '__name__') else 'unknown'}")
    
    def _apply_gain(self, pcm_data: bytes, gain: float) -> bytes:
        """
        Apply gain to PCM audio data.
        
        Args:
            pcm_data: Raw PCM audio data (16-bit signed integers)
            gain: Gain multiplier
            
        Returns:
            Processed PCM audio data
        """
        try:
            # Convert bytes to numpy array of int16
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
            
            # Apply gain with clipping protection
            processed = audio_array * gain
            processed = np.clip(processed, -32768, 32767)
            
            # Convert back to int16
            processed = processed.astype(np.int16)
            
            # Convert back to bytes
            return processed.tobytes()
            
        except Exception as e:
            logger.error(f"Error applying gain: {e}", exc_info=True)
            return pcm_data  # Return original on error
    
    def _apply_agc(self, pcm_data: bytes) -> bytes:
        """
        Apply Automatic Gain Control (AGC).
        
        Args:
            pcm_data: Raw PCM audio data
            
        Returns:
            Processed PCM audio data with AGC applied
        """
        # Simplified AGC implementation
        # TODO: Implement full AGC with threshold, slope, and decay
        if not self.enable_agc:
            return pcm_data
        
        try:
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
            
            # Calculate RMS level
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            if rms == 0:
                return pcm_data
            
            # Convert RMS to dB
            rms_db = 20 * np.log10(rms / 32768.0)
            
            # Calculate required gain
            target_db = self.agc_threshold_db
            gain_db = target_db - rms_db
            gain_linear = 10 ** (gain_db / 20.0)
            
            # Apply gain with limits
            gain_linear = max(0.1, min(10.0, gain_linear))
            
            return self._apply_gain(pcm_data, gain_linear)
            
        except Exception as e:
            logger.error(f"Error applying AGC: {e}", exc_info=True)
            return pcm_data
    
    def _process_interception_pipe(self, pcm_data: bytes) -> bytes:
        """
        Process audio through interception pipe (Phase 7: AI modules).
        
        Args:
            pcm_data: Raw PCM audio data
            
        Returns:
            Processed PCM audio data
        """
        if not self.interception_pipe_enabled:
            return pcm_data
        
        processed_data = pcm_data
        
        # Apply each plugin in sequence
        for plugin in self.interception_plugins:
            try:
                processed_data = plugin(processed_data)
            except Exception as e:
                logger.error(f"Error in interception plugin {plugin.__name__ if hasattr(plugin, '__name__') else 'unknown'}: {e}", exc_info=True)
                # Continue with unprocessed data on error
                break
        
        return processed_data
    
    def process_audio(self, audio_packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process audio packet through the processing pipeline.
        
        Pipeline:
        1. Extract PCM data and format information
        2. Resample to target format (8000 Hz, 16-Bit Mono, Little Endian)
        3. Apply gain (from packet or configured)
        4. Apply AGC (if enabled)
        5. Process through interception pipe (Phase 7)
        6. Return processed packet
        
        Args:
            audio_packet: Dictionary with 'pcm_data', 'sample_rate', 'channels', etc.
            
        Returns:
            Processed audio packet dictionary or None on error
        """
        try:
            pcm_data = audio_packet.get('pcm_data')
            if not pcm_data:
                logger.warning("No PCM data in audio packet")
                return None
            
            # Get format information
            input_sample_rate = audio_packet.get('sample_rate', self.target_sample_rate)
            input_channels = audio_packet.get('channels', self.target_channels)
            
            # Resample to target format (8000 Hz, 16-Bit Mono, Little Endian)
            if input_sample_rate != self.target_sample_rate or input_channels != self.target_channels:
                pcm_data = self.resampler.resample(pcm_data, input_sample_rate, input_channels)
                self.resampled_frames += 1
            
            # Use gain from packet or configured gain
            gain = audio_packet.get('gain', self.gain)
            gain = max(self.gain_min, min(self.gain_max, gain))
            
            # Apply gain
            processed_data = self._apply_gain(pcm_data, gain)
            
            # Apply AGC (if enabled)
            if self.enable_agc:
                processed_data = self._apply_agc(processed_data)
            
            # Process through interception pipe (Phase 7: AI modules)
            processed_data = self._process_interception_pipe(processed_data)
            
            # Create output packet
            output_packet = audio_packet.copy()
            output_packet['pcm_data'] = processed_data
            output_packet['sample_rate'] = self.target_sample_rate
            output_packet['channels'] = self.target_channels
            output_packet['processed'] = True
            
            self.processed_frames += 1
            return output_packet
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)
            self.dropped_frames += 1
            return None
    
    def process_tx_audio(self, audio_packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process TX audio (Telefon -> Funk) - Phase 7 AI-ready function.
        
        This function serves as a placeholder for AI noise reduction modules.
        Currently delegates to process_audio().
        
        Args:
            audio_packet: Audio packet dictionary with 'pcm_data'
            
        Returns:
            Processed audio packet dictionary or None on error
        """
        # Phase 7: AI modules can be inserted here
        # Example: processed_data = ai_noise_reduction(pcm_data)
        
        # Delegate to standard process_audio() for now
        return self.process_audio(audio_packet)
    
    def process_rx_audio(self, audio_packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process RX audio (Funk -> Telefon) - Phase 7 AI-ready function.
        
        This function serves as a placeholder for AI noise reduction modules.
        
        Args:
            audio_packet: Audio packet dictionary with 'pcm_data'
            
        Returns:
            Processed audio packet dictionary or None on error
        """
        try:
            pcm_data = audio_packet.get('pcm_data')
            if not pcm_data:
                logger.warning("No PCM data in RX audio packet")
                return None
            
            # Phase 7: AI modules can be inserted here
            # Example: processed_data = ai_noise_reduction(pcm_data)
            
            # Apply gain
            gain = audio_packet.get('gain', self.gain)
            gain = max(self.gain_min, min(self.gain_max, gain))
            processed_data = self._apply_gain(pcm_data, gain)
            
            # Apply AGC (if enabled)
            if self.enable_agc:
                processed_data = self._apply_agc(processed_data)
            
            # Process through interception pipe (Phase 7: AI modules)
            processed_data = self._process_interception_pipe(processed_data)
            
            # Create output packet
            output_packet = audio_packet.copy()
            output_packet['pcm_data'] = processed_data
            output_packet['processed'] = True
            
            return output_packet
            
        except Exception as e:
            logger.error(f"Error processing RX audio: {e}", exc_info=True)
            return None
    
    def get_stats(self) -> dict:
        """Get processor statistics."""
        return {
            'processed_frames': self.processed_frames,
            'dropped_frames': self.dropped_frames,
            'resampled_frames': self.resampled_frames,
            'plugins_registered': len(self.interception_plugins),
            'interception_pipe_enabled': self.interception_pipe_enabled
        }
