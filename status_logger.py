#!/usr/bin/env python3
"""
Status Logger Module
Central status logging instance for PTT state and audio levels visualization.

Features:
- PTT state visualization
- Audio level monitoring
- Console output with color codes
- Periodic status updates
"""

import logging
import time
import threading
from typing import Optional, Dict, Any
from queue import Queue

logger = logging.getLogger(__name__)


class StatusLogger:
    """Central status logger for PTT state and audio levels."""
    
    def __init__(self, config: dict, update_interval: float = 1.0):
        """
        Initialize Status Logger.
        
        Args:
            config: Configuration dictionary with 'logging' section
            update_interval: Update interval in seconds
        """
        self.config = config.get('logging', {})
        self.update_interval = update_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Status tracking
        self.tx_ptt_active = False
        self.rx_active = False
        self.tx_audio_level = 0.0
        self.rx_audio_level = 0.0
        self.tx_sequence = 0
        self.rx_sequence = 0
        
        # Statistics
        self.tx_packets = 0
        self.rx_packets = 0
        self.tx_bytes = 0
        self.rx_bytes = 0
        
        # Lock for thread-safe access
        self.lock = threading.Lock()
        
        logger.info(f"Status Logger initialized: update_interval={update_interval}s")
    
    def update_tx_status(self, ptt_active: bool, audio_level: float = 0.0, sequence: int = 0):
        """Update TX (Telefon -> Funk) status."""
        with self.lock:
            self.tx_ptt_active = ptt_active
            self.tx_audio_level = audio_level
            self.tx_sequence = sequence
            if ptt_active:
                self.tx_packets += 1
    
    def update_rx_status(self, active: bool, audio_level: float = 0.0, sequence: int = 0):
        """Update RX (Funk -> Telefon) status."""
        with self.lock:
            self.rx_active = active
            self.rx_audio_level = audio_level
            self.rx_sequence = sequence
            if active:
                self.rx_packets += 1
    
    def _format_audio_level(self, level: float) -> str:
        """Format audio level as bar."""
        # Normalize level (0-32768 -> 0-100)
        normalized = min(100, max(0, (level / 32768.0) * 100))
        bars = int(normalized / 5)  # 20 bars max
        bar_str = '=' * bars + ' ' * (20 - bars)
        return f"[{bar_str}] {normalized:.1f}%"
    
    def _format_status_line(self) -> str:
        """Format status line for console output."""
        with self.lock:
            # PTT status
            ptt_status = "PTT ON " if self.tx_ptt_active else "PTT OFF"
            ptt_color = "\033[92m" if self.tx_ptt_active else "\033[90m"  # Green / Dark gray
            
            # RX status
            rx_status = "RX ACTIVE" if self.rx_active else "RX IDLE"
            rx_color = "\033[94m" if self.rx_active else "\033[90m"  # Blue / Dark gray
            
            # Audio levels
            tx_level = self._format_audio_level(self.tx_audio_level)
            rx_level = self._format_audio_level(self.rx_audio_level)
            
            # Format line
            line = (
                f"{ptt_color}{ptt_status:8}\033[0m | "
                f"TX: {tx_level} | "
                f"{rx_color}{rx_status:10}\033[0m | "
                f"RX: {rx_level} | "
                f"TX Seq: {self.tx_sequence:6} | "
                f"RX Seq: {self.rx_sequence:6}"
            )
            
            return line
    
    def _status_loop(self):
        """Main status loop in separate thread."""
        logger.info("Status Logger started")
        
        while self.running:
            try:
                time.sleep(self.update_interval)
                
                if not self.running:
                    break
                
                # Print status line
                status_line = self._format_status_line()
                print(f"\r{status_line}", end='', flush=True)
                
            except Exception as e:
                logger.error(f"Error in status loop: {e}", exc_info=True)
                break
        
        # Clear status line on exit
        print("\r" + " " * 120 + "\r", end='', flush=True)
        logger.info("Status Logger stopped")
    
    def start(self):
        """Start the status logger."""
        if self.running:
            logger.warning("Status Logger already running")
            return
        
        try:
            self.running = True
            
            # Start status thread
            self.thread = threading.Thread(target=self._status_loop, daemon=True)
            self.thread.start()
            
            logger.info("Status Logger started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Status Logger: {e}", exc_info=True)
            self.running = False
            raise
    
    def stop(self):
        """Stop the status logger."""
        if not self.running:
            return
        
        logger.info("Stopping Status Logger...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        logger.info("Status Logger stopped")
    
    def get_stats(self) -> dict:
        """Get status logger statistics."""
        with self.lock:
            return {
                'tx_ptt_active': self.tx_ptt_active,
                'rx_active': self.rx_active,
                'tx_audio_level': self.tx_audio_level,
                'rx_audio_level': self.rx_audio_level,
                'tx_packets': self.tx_packets,
                'rx_packets': self.rx_packets,
                'tx_sequence': self.tx_sequence,
                'rx_sequence': self.rx_sequence
            }

