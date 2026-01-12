#!/usr/bin/env python3
"""
DMR Gateway Module
Handles communication with MMDVM_Bridge via UDP on port 33100.

Protocol: PCM Pass-Through mode compatible with MMDVM_Bridge expectations.
Supports PTT (Push-To-Talk) control commands.
"""

import socket
import logging
import struct
import threading
from queue import Queue
from typing import Optional, Dict, Any
import time

logger = logging.getLogger(__name__)


class DMRGateway:
    """Gateway to MMDVM_Bridge for DMR communication with PTT control."""
    
    # TLV Frame types
    TLV_TYPE_PCM = 0x00
    TLV_TYPE_AMBE = 0x01
    TLV_TYPE_PTT_START = 0x05  # PTT Start command
    TLV_TYPE_PTT_STOP = 0x06   # PTT Stop command
    
    def __init__(self, config: dict, audio_queue: Queue):
        """
        Initialize DMR Gateway.
        
        Args:
            config: Configuration dictionary with 'mmdvm' section
            audio_queue: Queue to get processed audio data from
        """
        self.config = config['mmdvm']
        self.audio_queue = audio_queue
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # PTT state
        self.ptt_active = False
        
        # Extract configuration
        self.mmdvm_address = self.config.get('address', '127.0.0.1')
        self.mmdvm_port = self.config.get('port', 33100)
        self.buffer_size = self.config.get('buffer_size', 4096)
        
        # Statistics
        self.packets_sent = 0
        self.errors = 0
        self.bytes_sent = 0
        self.ptt_commands_sent = 0
        
        logger.info(f"DMR Gateway initialized: {self.mmdvm_address}:{self.mmdvm_port}")
    
    def _create_tlv_frame(self, pcm_data: bytes, sequence: int = 0) -> bytes:
        """
        Create TLV frame for MMDVM_Bridge (PCM pass-through mode).
        
        Simplified TLV format for PCM:
        - Type: 1 byte (0x00 = PCM)
        - Length: 2 bytes (little-endian)
        - Value: PCM data
        
        Args:
            pcm_data: PCM audio data
            sequence: Sequence number
            
        Returns:
            TLV frame bytes
        """
        try:
            # Type: PCM
            frame_type = bytes([self.TLV_TYPE_PCM])
            
            # Length: 2 bytes (little-endian)
            length = len(pcm_data)
            length_bytes = struct.pack('<H', length)
            
            # Value: PCM data
            value = pcm_data
            
            # Combine: Type + Length + Value
            frame = frame_type + length_bytes + value
            
            return frame
            
        except Exception as e:
            logger.error(f"Error creating TLV frame: {e}", exc_info=True)
            return b''
    
    def _create_ptt_command(self, ptt_on: bool) -> bytes:
        """
        Create PTT command frame for MMDVM_Bridge.
        
        TLV format for PTT:
        - Type: 1 byte (0x05 = PTT Start, 0x06 = PTT Stop)
        - Length: 2 bytes (little-endian) - always 0 for PTT commands
        - Value: empty (no payload)
        
        Args:
            ptt_on: True for PTT Start, False for PTT Stop
            
        Returns:
            TLV frame bytes
        """
        try:
            # Type: PTT Start or Stop
            frame_type = bytes([self.TLV_TYPE_PTT_START if ptt_on else self.TLV_TYPE_PTT_STOP])
            
            # Length: 0 (no payload)
            length_bytes = struct.pack('<H', 0)
            
            # Value: empty
            value = b''
            
            # Combine: Type + Length + Value
            frame = frame_type + length_bytes + value
            
            return frame
            
        except Exception as e:
            logger.error(f"Error creating PTT command: {e}", exc_info=True)
            return b''
    
    def send_ptt_command(self, ptt_on: bool):
        """
        Send PTT command to MMDVM_Bridge.
        
        Args:
            ptt_on: True for PTT Start, False for PTT Stop
        """
        if not self.socket:
            logger.warning("Socket not initialized, cannot send PTT command")
            return
        
        try:
            # Create PTT command frame
            frame = self._create_ptt_command(ptt_on)
            
            if len(frame) == 0:
                logger.warning("Empty PTT frame, skipping send")
                return
            
            # Send UDP packet
            self.socket.sendto(frame, (self.mmdvm_address, self.mmdvm_port))
            
            self.ptt_active = ptt_on
            self.ptt_commands_sent += 1
            
            logger.debug(f"PTT command sent: {'ON' if ptt_on else 'OFF'}")
            
        except socket.error as e:
            logger.error(f"Socket error sending PTT command: {e}")
            self.errors += 1
        except Exception as e:
            logger.error(f"Error sending PTT command: {e}", exc_info=True)
            self.errors += 1
    
    def _send_pcm_data(self, pcm_data: bytes, sequence: int = 0):
        """
        Send PCM data to MMDVM_Bridge.
        
        Args:
            pcm_data: PCM audio data to send
            sequence: Sequence number
        """
        if not self.socket:
            logger.error("Socket not initialized")
            return
        
        try:
            # Create TLV frame
            frame = self._create_tlv_frame(pcm_data, sequence)
            
            if len(frame) == 0:
                logger.warning("Empty frame, skipping send")
                return
            
            # Send UDP packet
            self.socket.sendto(frame, (self.mmdvm_address, self.mmdvm_port))
            
            self.packets_sent += 1
            self.bytes_sent += len(frame)
            
        except socket.error as e:
            logger.error(f"Socket error sending to MMDVM_Bridge: {e}")
            self.errors += 1
        except Exception as e:
            logger.error(f"Error sending PCM data: {e}", exc_info=True)
            self.errors += 1
    
    def _send_loop(self):
        """Main send loop in separate thread."""
        logger.info(f"DMR Gateway started, sending to {self.mmdvm_address}:{self.mmdvm_port}")
        
        while self.running:
            try:
                # Get audio packet from queue
                audio_packet = self.audio_queue.get(timeout=1.0)
                
                # Extract data
                pcm_data = audio_packet.get('pcm_data')
                sequence = audio_packet.get('sequence', 0)
                
                if not pcm_data:
                    logger.warning("No PCM data in audio packet")
                    continue
                
                # Only send if PTT is active (VOX-controlled)
                ptt_active = audio_packet.get('ptt_active', False)
                
                if ptt_active:
                    # Send to MMDVM_Bridge
                    self._send_pcm_data(pcm_data, sequence)
                
            except Exception as e:
                if self.running:
                    logger.debug(f"Queue timeout or error: {e}")
                continue
        
        logger.info("DMR Gateway send loop stopped")
    
    def start(self):
        """Start the DMR Gateway."""
        if self.running:
            logger.warning("DMR Gateway already running")
            return
        
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            self.running = True
            
            # Start send thread
            self.thread = threading.Thread(target=self._send_loop, daemon=True)
            self.thread.start()
            
            logger.info(f"DMR Gateway started successfully, target: {self.mmdvm_address}:{self.mmdvm_port}")
            
        except Exception as e:
            logger.error(f"Failed to start DMR Gateway: {e}", exc_info=True)
            self.running = False
            if self.socket:
                self.socket.close()
                self.socket = None
            raise
    
    def stop(self):
        """Stop the DMR Gateway."""
        if not self.running:
            return
        
        logger.info("Stopping DMR Gateway...")
        self.running = False
        
        # Send PTT OFF command before stopping
        if self.ptt_active:
            try:
                self.send_ptt_command(False)
            except:
                pass
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        logger.info("DMR Gateway stopped")
        logger.info(f"Statistics: Packets={self.packets_sent}, PTT Commands={self.ptt_commands_sent}, Errors={self.errors}, Bytes={self.bytes_sent}")
    
    def get_stats(self) -> dict:
        """Get gateway statistics."""
        return {
            'packets_sent': self.packets_sent,
            'errors': self.errors,
            'bytes_sent': self.bytes_sent,
            'ptt_commands_sent': self.ptt_commands_sent,
            'ptt_active': self.ptt_active,
            'running': self.running
        }
