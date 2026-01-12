#!/usr/bin/env python3
"""
MMDVM Receiver Module
Handles incoming TLV frames from MMDVM_Bridge on port 33101 (RX channel).

Features:
- UDP listener on port 33101
- TLV frame parsing
- PCM data extraction
- Queue-based output for processing
"""

import socket
import struct
import logging
import threading
from queue import Queue
from typing import Optional, Tuple
import time

logger = logging.getLogger(__name__)


class MMDVMReceiver:
    """Receives TLV frames from MMDVM_Bridge (RX channel: Funk -> Telefon)."""
    
    # TLV Frame types
    TLV_TYPE_PCM = 0x00
    TLV_TYPE_AMBE = 0x01
    
    def __init__(self, config: dict, audio_queue: Queue):
        """
        Initialize MMDVM Receiver.
        
        Args:
            config: Configuration dictionary with 'mmdvm_rx' section
            audio_queue: Queue to put received audio data
        """
        self.config = config.get('mmdvm_rx', config.get('mmdvm', {}))
        self.audio_queue = audio_queue
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Extract configuration
        self.listen_address = self.config.get('listen_address', '0.0.0.0')
        self.listen_port = self.config.get('rx_port', 33101)
        self.buffer_size = self.config.get('buffer_size', 4096)
        
        # Statistics
        self.packets_received = 0
        self.errors = 0
        self.bytes_received = 0
        self.sequence_counter = 0
        
        logger.info(f"MMDVM Receiver initialized: {self.listen_address}:{self.listen_port}")
    
    def _parse_tlv_frame(self, data: bytes) -> Optional[Tuple[int, bytes]]:
        """
        Parse TLV frame from MMDVM_Bridge.
        
        Format:
        - Type: 1 byte
        - Length: 2 bytes (little-endian)
        - Value: variable length (PCM data)
        
        Args:
            data: Raw UDP packet data
            
        Returns:
            Tuple of (frame_type, pcm_data) or None if invalid
        """
        try:
            if len(data) < 3:  # Minimum: Type (1) + Length (2)
                logger.warning(f"Packet too short: {len(data)} bytes")
                return None
            
            # Parse type
            frame_type = data[0]
            
            # Parse length
            length = struct.unpack('<H', data[1:3])[0]
            
            # Check if packet is complete
            if len(data) < 3 + length:
                logger.warning(f"Packet incomplete: expected {3 + length} bytes, got {len(data)}")
                return None
            
            # Extract value (PCM data)
            value = data[3:3 + length]
            
            return (frame_type, value)
            
        except struct.error as e:
            logger.error(f"Struct unpack error: {e}")
            self.errors += 1
            return None
        except Exception as e:
            logger.error(f"Error parsing TLV frame: {e}", exc_info=True)
            self.errors += 1
            return None
    
    def _handle_packet(self, data: bytes, address: Tuple[str, int]):
        """Handle incoming UDP packet."""
        try:
            parsed = self._parse_tlv_frame(data)
            if parsed is None:
                return
            
            frame_type, pcm_data = parsed
            
            # Only process PCM frames (Type 0x00)
            if frame_type != self.TLV_TYPE_PCM:
                logger.debug(f"Ignoring non-PCM frame type: 0x{frame_type:02x}")
                return
            
            if len(pcm_data) == 0:
                logger.warning("Empty PCM data in frame")
                return
            
            # Create audio packet structure
            audio_packet = {
                'frame_type': frame_type,
                'pcm_data': pcm_data,
                'source': 'mmdvm_rx',
                'address': address,
                'timestamp': time.time(),
                'sequence': self.sequence_counter
            }
            
            self.sequence_counter += 1
            
            # Put into queue for processing
            try:
                self.audio_queue.put(audio_packet, timeout=1.0)
                self.packets_received += 1
                self.bytes_received += len(data)
            except:
                logger.warning("Audio queue full, dropping packet")
                
        except Exception as e:
            logger.error(f"Error handling packet from {address}: {e}", exc_info=True)
            self.errors += 1
    
    def _receive_loop(self):
        """Main receive loop in separate thread."""
        logger.info(f"MMDVM Receiver started, listening on {self.listen_address}:{self.listen_port}")
        
        while self.running:
            try:
                # Receive UDP packet
                data, address = self.socket.recvfrom(self.buffer_size)
                
                # Handle packet
                self._handle_packet(data, address)
                
            except socket.timeout:
                # Timeout is expected, continue
                continue
            except socket.error as e:
                if self.running:
                    logger.error(f"Socket error: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error in receive loop: {e}", exc_info=True)
                if not self.running:
                    break
        
        logger.info("MMDVM Receiver receive loop stopped")
    
    def start(self):
        """Start the MMDVM Receiver."""
        if self.running:
            logger.warning("MMDVM Receiver already running")
            return
        
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.listen_address, self.listen_port))
            self.socket.settimeout(1.0)  # Non-blocking with timeout
            
            self.running = True
            
            # Start receive thread
            self.thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.thread.start()
            
            logger.info(f"MMDVM Receiver started successfully on {self.listen_address}:{self.listen_port}")
            
        except Exception as e:
            logger.error(f"Failed to start MMDVM Receiver: {e}", exc_info=True)
            self.running = False
            if self.socket:
                self.socket.close()
                self.socket = None
            raise
    
    def stop(self):
        """Stop the MMDVM Receiver."""
        if not self.running:
            return
        
        logger.info("Stopping MMDVM Receiver...")
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        logger.info("MMDVM Receiver stopped")
        logger.info(f"Statistics: Packets={self.packets_received}, Errors={self.errors}, Bytes={self.bytes_received}")
    
    def get_stats(self) -> dict:
        """Get receiver statistics."""
        return {
            'packets_received': self.packets_received,
            'errors': self.errors,
            'bytes_received': self.bytes_received,
            'sequence_counter': self.sequence_counter,
            'running': self.running
        }

