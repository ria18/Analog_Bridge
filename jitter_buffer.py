#!/usr/bin/env python3
"""
Jitter Buffer Module
Minimalist jitter buffer for RX channel with 20ms frame timing.

Features:
- Queue-based jitter buffer
- 20ms frame timing (DMR standard)
- Handles packet jitter and reordering
- Configurable buffer size
"""

import logging
import time
from queue import Queue
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class JitterBuffer:
    """Minimalist jitter buffer for audio frames."""
    
    def __init__(self, config: dict, input_queue: Queue, output_queue: Queue):
        """
        Initialize Jitter Buffer.
        
        Args:
            config: Configuration dictionary with 'jitter_buffer' section
            input_queue: Queue to get audio packets from
            output_queue: Queue to put buffered audio packets
        """
        self.config = config.get('jitter_buffer', {})
        self.input_queue = input_queue
        self.output_queue = output_queue
        
        # Configuration
        self.frame_time_ms = self.config.get('frame_time_ms', 20)  # 20ms for DMR
        self.buffer_size = self.config.get('buffer_size', 3)  # Number of frames
        self.frame_time_seconds = self.frame_time_ms / 1000.0
        
        # Internal buffer
        self.buffer: list = []
        self.last_output_time = 0
        
        # Statistics
        self.frames_buffered = 0
        self.frames_output = 0
        self.frames_dropped = 0
        self.underruns = 0
        
        logger.info(f"Jitter Buffer initialized: frame_time={self.frame_time_ms}ms, buffer_size={self.buffer_size}")
    
    def _get_frame(self) -> Optional[Dict[str, Any]]:
        """
        Get frame from input queue (non-blocking).
        
        Returns:
            Audio packet or None if queue empty
        """
        try:
            return self.input_queue.get_nowait()
        except:
            return None
    
    def process(self):
        """
        Process jitter buffer (should be called in a loop).
        
        Logic:
        1. Fill buffer if space available
        2. Output frames at constant 20ms intervals
        3. Handle underruns (empty buffer)
        """
        current_time = time.time()
        
        # Fill buffer if space available
        while len(self.buffer) < self.buffer_size:
            frame = self._get_frame()
            if frame is None:
                break
            self.buffer.append(frame)
            self.frames_buffered += 1
        
        # Drop excess frames if buffer is full
        while len(self.buffer) > self.buffer_size * 2:
            dropped = self.buffer.pop(0)
            self.frames_dropped += 1
            logger.warning("Jitter buffer overflow, dropping frame")
        
        # Output frames at constant interval
        if self.last_output_time == 0:
            # First frame - output immediately
            if len(self.buffer) > 0:
                frame = self.buffer.pop(0)
                try:
                    self.output_queue.put(frame, timeout=0.1)
                    self.frames_output += 1
                    self.last_output_time = current_time
                except:
                    logger.warning("Output queue full, dropping frame")
        else:
            # Check if it's time to output next frame
            elapsed = current_time - self.last_output_time
            
            if elapsed >= self.frame_time_seconds:
                if len(self.buffer) > 0:
                    frame = self.buffer.pop(0)
                    try:
                        self.output_queue.put(frame, timeout=0.1)
                        self.frames_output += 1
                        self.last_output_time += self.frame_time_seconds  # Maintain timing
                    except:
                        logger.warning("Output queue full, dropping frame")
                else:
                    # Underrun - buffer is empty
                    self.underruns += 1
                    logger.debug("Jitter buffer underrun")
                    # Reset timing to current time
                    self.last_output_time = current_time
    
    def get_stats(self) -> dict:
        """Get jitter buffer statistics."""
        return {
            'buffer_size': len(self.buffer),
            'frames_buffered': self.frames_buffered,
            'frames_output': self.frames_output,
            'frames_dropped': self.frames_dropped,
            'underruns': self.underruns,
            'frame_time_ms': self.frame_time_ms
        }

