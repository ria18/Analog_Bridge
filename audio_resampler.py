#!/usr/bin/env python3
"""
Audio Resampling Module
High-performance audio resampling using NumPy for Raspberry Pi 5 (ARM64).

Features:
- Dynamic resampling from any input sample rate to 8000 Hz
- Format conversion to 16-bit Mono PCM (Little Endian)
- Zero-latency design using linear interpolation
- Optimized for real-time processing
"""

import numpy as np
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class AudioResampler:
    """High-performance audio resampler using NumPy with pre-allocated buffers."""
    
    def __init__(self, target_sample_rate: int = 8000, target_channels: int = 1):
        """
        Initialize Audio Resampler.
        
        Args:
            target_sample_rate: Target sample rate (default: 8000 Hz)
            target_channels: Target channels (default: 1 = Mono)
        """
        self.target_sample_rate = target_sample_rate
        self.target_channels = target_channels
        self.bytes_per_sample = 2  # 16-bit = 2 bytes
        
        # Pre-allocated buffers for performance (max 4096 samples)
        self.max_samples = 4096
        self.float_buffer = np.empty(self.max_samples, dtype=np.float32)
        self.int16_buffer = np.empty(self.max_samples, dtype=np.int16)
        self.output_indices_buffer = np.empty(self.max_samples, dtype=np.float32)
        
        # State for resampling
        self.last_input_rate = None
        self.resample_ratio = None
        
        logger.info(f"Audio Resampler initialized: target={target_sample_rate}Hz, {target_channels} channel(s), pre-allocated buffers")
    
    def _linear_resample(self, audio_array: np.ndarray, input_rate: int, output_rate: int) -> np.ndarray:
        """
        Linear interpolation resampling (zero-latency) with pre-allocated buffers.
        
        Args:
            audio_array: Input audio as numpy array (int16)
            input_rate: Input sample rate
            output_rate: Output sample rate
            
        Returns:
            Resampled audio array
        """
        if input_rate == output_rate:
            return audio_array
        
        # Calculate resampling ratio
        ratio = output_rate / input_rate
        
        # Calculate output length
        output_length = int(len(audio_array) * ratio)
        
        # Use pre-allocated buffer if possible, otherwise allocate
        if output_length <= self.max_samples:
            output_indices = self.output_indices_buffer[:output_length]
            np.arange(output_length, out=output_indices, dtype=np.float32)
            output_indices /= ratio
        else:
            # Fallback for larger buffers
            output_indices = np.arange(output_length, dtype=np.float32) / ratio
        
        # Linear interpolation
        # Use floor indices and fractional parts
        floor_indices = np.floor(output_indices).astype(np.int32)
        fractional = output_indices - floor_indices
        
        # Clamp indices to valid range
        floor_indices = np.clip(floor_indices, 0, len(audio_array) - 2)
        
        # Interpolate (optimized NumPy operations)
        resampled = (
            audio_array[floor_indices].astype(np.float32) * (1 - fractional) +
            audio_array[floor_indices + 1].astype(np.float32) * fractional
        )
        
        # Convert back to int16 (use pre-allocated buffer if possible)
        if output_length <= self.max_samples:
            np.clip(resampled, -32768, 32767, out=self.int16_buffer[:output_length])
            return self.int16_buffer[:output_length].copy()
        else:
            return np.clip(resampled, -32768, 32767).astype(np.int16)
    
    def _convert_to_mono(self, audio_array: np.ndarray, channels: int) -> np.ndarray:
        """
        Convert multi-channel audio to mono.
        
        Args:
            audio_array: Input audio array (may be multi-channel)
            channels: Number of input channels
            
        Returns:
            Mono audio array
        """
        if channels == 1:
            return audio_array
        
        # Reshape to (samples, channels)
        samples = len(audio_array) // channels
        reshaped = audio_array.reshape(samples, channels)
        
        # Average all channels to mono
        mono = np.mean(reshaped, axis=1, dtype=np.float32)
        
        # Convert back to int16
        mono = np.clip(mono, -32768, 32767).astype(np.int16)
        
        return mono
    
    def resample(self, pcm_data: bytes, input_sample_rate: int, input_channels: int = 1) -> bytes:
        """
        Resample audio data to target format.
        
        Args:
            pcm_data: Input PCM audio data (16-bit, little-endian)
            input_sample_rate: Input sample rate (e.g., 16000, 8000)
            input_channels: Number of input channels
            
        Returns:
            Resampled PCM data (8000 Hz, 16-bit Mono, Little Endian)
        """
        try:
            # Convert bytes to numpy array (int16, little-endian)
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
            
            # Convert to mono if needed
            if input_channels != self.target_channels:
                audio_array = self._convert_to_mono(audio_array, input_channels)
            
            # Resample if needed
            if input_sample_rate != self.target_sample_rate:
                audio_array = self._linear_resample(audio_array, input_sample_rate, self.target_sample_rate)
            
            # Convert back to bytes (little-endian)
            return audio_array.tobytes()
            
        except Exception as e:
            logger.error(f"Error resampling audio: {e}", exc_info=True)
            # Return original data on error (graceful degradation)
            return pcm_data
    
    def validate_format(self, pcm_data: bytes, sample_rate: int, channels: int) -> Tuple[bool, str]:
        """
        Validate audio format.
        
        Args:
            pcm_data: PCM audio data
            sample_rate: Sample rate
            channels: Number of channels
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            # Check if data length is valid (must be multiple of bytes_per_sample * channels)
            bytes_per_frame = self.bytes_per_sample * channels
            if len(pcm_data) % bytes_per_frame != 0:
                return False, f"Invalid data length: {len(pcm_data)} bytes (not multiple of {bytes_per_frame})"
            
            # Check sample rate
            if sample_rate <= 0 or sample_rate > 96000:
                return False, f"Invalid sample rate: {sample_rate} Hz"
            
            # Check channels
            if channels < 1 or channels > 8:
                return False, f"Invalid channel count: {channels}"
            
            return True, "Format valid"
            
        except Exception as e:
            return False, f"Validation error: {e}"

