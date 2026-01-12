#!/usr/bin/env python3
"""
USRP Client Module
Sends USRP protocol packets to pjsua (SIP client) on port 40001.

Features:
- UDP sender to port 40001
- USRP protocol format (32-byte header)
- PCM data packaging
- Queue-based input
"""

import socket
import struct
import logging
import threading
from queue import Queue
from typing import Optional
import time

logger = logging.getLogger(__name__)


class USRPClient:
    """Sends USRP protocol packets to pjsua (RX channel: Funk -> Telefon)."""
    
    USRP_MAGIC = b'USRP'
    HEADER_SIZE = 32
    PACKET_TYPE_AUDIO = 0
    
    def __init__(self, config: dict, audio_queue: Queue):
        """
        Initialize USRP Client.
        
        Args:
            config: Configuration dictionary with 'usrp_client' section
            audio_queue: Queue to get audio data from
        """
        self.config = config.get('usrp_client', config.get('usrp', {}))
        self.audio_queue = audio_queue
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Extract configuration
        self.target_address = self.config.get('target_address', '127.0.0.1')
        self.target_port = self.config.get('target_port', 40001)
        self.buffer_size = self.config.get('buffer_size', 4096)
        
        # Audio format
        self.sample_rate = config.get('audio', {}).get('sample_rate', 8000)
        self.channels = config.get('audio', {}).get('channels', 1)
        self.sample_width = config.get('audio', {}).get('sample_width', 2)
        
        # Sequence counter
        self.sequence_counter = 0
        
        # Statistics
        self.packets_sent = 0
        self.errors = 0
        self.bytes_sent = 0
        
        logger.info(f"USRP Client initialized: {self.target_address}:{self.target_port}")
    
    def _create_usrp_packet(self, pcm_data: bytes) -> bytes:
        """
        Create USRP protocol packet with 32-byte header.
        
        Format:
        - Magic: "USRP" (4 bytes)
        - Packet Type: uint32 (4 bytes, little-endian) - 0=Audio
        - Sequence: uint32 (4 bytes, little-endian)
        - Timestamp: uint64 (8 bytes, little-endian) - microseconds since epoch
        - Sample Rate: uint32 (4 bytes, little-endian)
        - Channels: uint16 (2 bytes, little-endian)
        - Sample Width: uint16 (2 bytes, little-endian)
        - Reserved: uint16 (2 bytes)
        - Payload Length: uint32 (4 bytes, little-endian)
        - Payload: PCM data
        
        Args:
            pcm_data: PCM audio data
            
        Returns:
            USRP packet bytes
        """
        try:
            packet = bytearray(self.HEADER_SIZE)
            
            # Magic string
            packet[0:4] = self.USRP_MAGIC
            
            # Packet type (Audio)
            struct.pack_into('<I', packet, 4, self.PACKET_TYPE_AUDIO)
            
            # Sequence number
            struct.pack_into('<I', packet, 8, self.sequence_counter)
            self.sequence_counter += 1
            
            # Timestamp (microseconds since epoch)
            timestamp_us = int(time.time() * 1000000)
            struct.pack_into('<Q', packet, 12, timestamp_us)
            
            # Sample rate
            struct.pack_into('<I', packet, 20, self.sample_rate)
            
            # Channels
            struct.pack_into('<H', packet, 24, self.channels)
            
            # Sample width
            struct.pack_into('<H', packet, 26, self.sample_width)
            
            # Reserved
            struct.pack_into('<H', packet, 28, 0)
            
            # Payload length
            payload_length = len(pcm_data)
            struct.pack_into('<I', packet, 30, payload_length)
            
            # Combine header + payload
            full_packet = bytes(packet) + pcm_data
            
            return full_packet
            
        except Exception as e:
            logger.error(f"Error creating USRP packet: {e}", exc_info=True)
            return b''
    
    def _send_loop(self):
        """Main send loop in separate thread."""
        logger.info(f"USRP Client started, sending to {self.target_address}:{self.target_port}")
        
        while self.running:
            try:
                # Get audio packet from queue
                audio_packet = self.audio_queue.get(timeout=1.0)
                
                # Extract PCM data
                pcm_data = audio_packet.get('pcm_data')
                if not pcm_data:
                    logger.warning("No PCM data in audio packet")
                    continue
                
                # Create USRP packet
                usrp_packet = self._create_usrp_packet(pcm_data)
                
                if len(usrp_packet) == 0:
                    logger.warning("Empty USRP packet, skipping send")
                    continue
                
                # Send UDP packet
                if self.socket:
                    self.socket.sendto(usrp_packet, (self.target_address, self.target_port))
                    self.packets_sent += 1
                    self.bytes_sent += len(usrp_packet)
                
            except Exception as e:
                if self.running:
                    logger.debug(f"Queue timeout or error: {e}")
                continue
        
        logger.info("USRP Client send loop stopped")
    
    def start(self):
        """Start the USRP Client."""
        if self.running:
            logger.warning("USRP Client already running")
            return
        
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            self.running = True
            
            # Start send thread
            self.thread = threading.Thread(target=self._send_loop, daemon=True)
            self.thread.start()
            
            logger.info(f"USRP Client started successfully, target: {self.target_address}:{self.target_port}")
            
        except Exception as e:
            logger.error(f"Failed to start USRP Client: {e}", exc_info=True)
            self.running = False
            if self.socket:
                self.socket.close()
                self.socket = None
            raise
    
    def stop(self):
        """Stop the USRP Client."""
        if not self.running:
            return
        
        logger.info("Stopping USRP Client...")
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        logger.info("USRP Client stopped")
        logger.info(f"Statistics: Packets={self.packets_sent}, Errors={self.errors}, Bytes={self.bytes_sent}")
    
    def get_stats(self) -> dict:
        """Get client statistics."""
        return {
            'packets_sent': self.packets_sent,
            'errors': self.errors,
            'bytes_sent': self.bytes_sent,
            'sequence_counter': self.sequence_counter,
            'running': self.running
        }

