#!/usr/bin/env python3
"""
Echo Interlock Module
Prevents echo by muting TX path when RX is active.

Features:
- Thread-safe echo interlock
- RX activity detection
- TX muting/damping when RX active
- Configurable interlock delay
"""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class EchoInterlock:
    """Echo interlock to prevent TX when RX is active."""
    
    def __init__(self, config: dict):
        """
        Initialize Echo Interlock.
        
        Args:
            config: Configuration dictionary with 'echo_interlock' section
        """
        self.config = config.get('echo_interlock', {})
        
        # Configuration
        self.enable = self.config.get('enable', True)
        self.interlock_delay_ms = self.config.get('interlock_delay_ms', 100)
        self.tx_mute_gain = self.config.get('tx_mute_gain', 0.0)  # 0.0 = mute, 0.1 = -20dB
        self.rx_timeout_ms = self.config.get('rx_timeout_ms', 200)
        
        # State
        self.rx_active = False
        self.rx_last_activity = 0
        self.tx_muted = False
        
        # Lock for thread-safe access
        self.lock = threading.Lock()
        
        logger.info(f"Echo Interlock initialized: enable={self.enable}, delay={self.interlock_delay_ms}ms, mute_gain={self.tx_mute_gain}")
    
    def set_rx_active(self, active: bool):
        """Set RX activity state (thread-safe)."""
        with self.lock:
            if active:
                self.rx_active = True
                self.rx_last_activity = time.time()
            else:
                # Check timeout
                elapsed_ms = (time.time() - self.rx_last_activity) * 1000
                if elapsed_ms > self.rx_timeout_ms:
                    self.rx_active = False
    
    def is_tx_muted(self) -> bool:
        """
        Check if TX should be muted (thread-safe).
        
        Returns:
            True if TX should be muted, False otherwise
        """
        if not self.enable:
            return False
        
        with self.lock:
            # Check if RX is active (within timeout)
            elapsed_ms = (time.time() - self.rx_last_activity) * 1000
            if elapsed_ms > self.rx_timeout_ms:
                self.rx_active = False
            
            self.tx_muted = self.rx_active
            return self.tx_muted
    
    def get_tx_gain(self, original_gain: float = 1.0) -> float:
        """
        Get TX gain with echo interlock applied (thread-safe).
        
        Args:
            original_gain: Original TX gain
            
        Returns:
            Adjusted TX gain (muted if RX active)
        """
        if not self.enable:
            return original_gain
        
        if self.is_tx_muted():
            return self.tx_mute_gain * original_gain
        
        return original_gain
    
    def get_stats(self) -> dict:
        """Get interlock statistics."""
        with self.lock:
            return {
                'enable': self.enable,
                'rx_active': self.rx_active,
                'tx_muted': self.tx_muted,
                'interlock_delay_ms': self.interlock_delay_ms
            }

