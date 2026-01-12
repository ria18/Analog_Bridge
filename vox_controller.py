#!/usr/bin/env python3
"""
VOX (Voice Operated Exchange) Controller Module
Intelligent PTT/VOX control with threshold, hangtime, and hard timeout.

Features:
- Real-time amplitude analysis
- PTT ON: When threshold is exceeded
- Hangtime: Delay before PTT OFF (500-800ms)
- PTT OFF: After hangtime expires during silence
- Hard Timeout: Maximum transmission time (60 seconds) to prevent "stuck" transmissions
"""

import logging
import time
import numpy as np
from queue import Queue
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)


class VOXController:
    """Intelligent VOX controller with threshold, hangtime, and hard timeout."""
    
    def __init__(self, config: dict, audio_queue: Queue, ptt_callback: Callable[[bool], None]):
        """
        Initialize VOX Controller.
        
        Args:
            config: Configuration dictionary with 'vox' section
            audio_queue: Queue to get audio data from
            ptt_callback: Callback function(transmitting: bool) to send PTT commands
        """
        self.config = config.get('vox', {})
        self.audio_queue = audio_queue
        self.ptt_callback = ptt_callback
        
        # VOX parameters
        self.threshold = self.config.get('threshold', 1000)  # Amplitude threshold
        self.hangtime_ms = self.config.get('hangtime_ms', 600)  # Hangtime in milliseconds
        self.hard_timeout_ms = self.config.get('hard_timeout_ms', 60000)  # Hard timeout (60 seconds)
        
        # State
        self.ptt_active = False
        self.last_activity_time = 0
        self.transmission_start_time = 0
        self.hangtime_seconds = self.hangtime_ms / 1000.0
        self.hard_timeout_seconds = self.hard_timeout_ms / 1000.0
        
        # Statistics
        self.ptt_activations = 0
        self.ptt_deactivations = 0
        self.hard_timeouts = 0
        self.total_transmission_time = 0.0
        
        # Sample rate for calculations (8 kHz = 8000 samples per second)
        self.sample_rate = 8000
        self.frame_time = 0.02  # 20ms frame time (typical)
        
        logger.info(f"VOX Controller initialized: threshold={self.threshold}, hangtime={self.hangtime_ms}ms, hard_timeout={self.hard_timeout_ms}ms")
    
    def _calculate_amplitude(self, pcm_data: bytes) -> float:
        """
        Calculate amplitude (RMS) of PCM audio data.
        
        Args:
            pcm_data: PCM audio data (16-bit signed integers)
            
        Returns:
            RMS amplitude value
        """
        try:
            # Convert bytes to numpy array (int16)
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
            
            # Calculate RMS (Root Mean Square)
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            
            return float(rms)
            
        except Exception as e:
            logger.error(f"Error calculating amplitude: {e}", exc_info=True)
            return 0.0
    
    def _check_hard_timeout(self) -> bool:
        """
        Check if hard timeout has been exceeded.
        
        Returns:
            True if hard timeout exceeded, False otherwise
        """
        if not self.ptt_active:
            return False
        
        current_time = time.time()
        transmission_duration = current_time - self.transmission_start_time
        
        if transmission_duration >= self.hard_timeout_seconds:
            logger.warning(f"Hard timeout exceeded: {transmission_duration:.2f}s >= {self.hard_timeout_seconds:.2f}s")
            self.hard_timeouts += 1
            return True
        
        return False
    
    def process_audio_frame(self, audio_packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process audio frame and control PTT based on VOX logic.
        
        VOX Logic:
        1. Calculate amplitude of audio frame
        2. If amplitude > threshold:
           - If PTT not active: Activate PTT (PTT ON)
           - Update last activity time
        3. If amplitude <= threshold:
           - Check hangtime: If time since last activity > hangtime, deactivate PTT (PTT OFF)
        4. Check hard timeout: If transmission time > hard timeout, force PTT OFF
        
        Args:
            audio_packet: Audio packet dictionary with 'pcm_data'
            
        Returns:
            Audio packet dictionary (may be modified with PTT state)
        """
        try:
            pcm_data = audio_packet.get('pcm_data')
            if not pcm_data:
                return audio_packet
            
            current_time = time.time()
            
            # Calculate amplitude
            amplitude = self._calculate_amplitude(pcm_data)
            
            # Check hard timeout first (safety)
            if self._check_hard_timeout():
                self._deactivate_ptt()
                return audio_packet
            
            # VOX logic
            if amplitude > self.threshold:
                # Voice detected (above threshold)
                if not self.ptt_active:
                    # Activate PTT
                    self._activate_ptt(current_time)
                
                # Update last activity time
                self.last_activity_time = current_time
                
            else:
                # Silence detected (below threshold)
                if self.ptt_active:
                    # Check hangtime
                    silence_duration = current_time - self.last_activity_time
                    
                    if silence_duration >= self.hangtime_seconds:
                        # Hangtime expired, deactivate PTT
                        self._deactivate_ptt()
            
            # Add PTT state to packet
            audio_packet['ptt_active'] = self.ptt_active
            audio_packet['amplitude'] = amplitude
            
            return audio_packet
            
        except Exception as e:
            logger.error(f"Error processing VOX frame: {e}", exc_info=True)
            return audio_packet
    
    def _activate_ptt(self, current_time: float):
        """Activate PTT (transmission start)."""
        if self.ptt_active:
            return  # Already active
        
        self.ptt_active = True
        self.transmission_start_time = current_time
        self.last_activity_time = current_time
        
        # Call PTT callback
        try:
            self.ptt_callback(True)
            self.ptt_activations += 1
            logger.debug(f"PTT ON: amplitude threshold exceeded")
        except Exception as e:
            logger.error(f"Error in PTT callback (ON): {e}", exc_info=True)
    
    def _deactivate_ptt(self):
        """Deactivate PTT (transmission end)."""
        if not self.ptt_active:
            return  # Already inactive
        
        # Calculate transmission duration
        transmission_duration = time.time() - self.transmission_start_time
        self.total_transmission_time += transmission_duration
        
        self.ptt_active = False
        
        # Call PTT callback
        try:
            self.ptt_callback(False)
            self.ptt_deactivations += 1
            logger.debug(f"PTT OFF: hangtime expired or hard timeout")
        except Exception as e:
            logger.error(f"Error in PTT callback (OFF): {e}", exc_info=True)
    
    def force_ptt_off(self):
        """Force PTT OFF (emergency stop)."""
        if self.ptt_active:
            self._deactivate_ptt()
    
    def get_stats(self) -> dict:
        """Get VOX controller statistics."""
        return {
            'ptt_active': self.ptt_active,
            'ptt_activations': self.ptt_activations,
            'ptt_deactivations': self.ptt_deactivations,
            'hard_timeouts': self.hard_timeouts,
            'total_transmission_time': self.total_transmission_time,
            'threshold': self.threshold,
            'hangtime_ms': self.hangtime_ms,
            'hard_timeout_ms': self.hard_timeout_ms
        }

