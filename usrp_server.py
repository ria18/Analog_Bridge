#!/usr/bin/env python3
"""
USRP Server Module
Handles incoming USRP protocol UDP streams on port 40001.

USRP Protocol Format (32-Byte Header):
- Magic String: "USRP" (4 bytes)
- Packet Type: uint32 (4 bytes) - 0=Audio Frame, 1=Control/Metadata
- Sequence Number: uint32 (4 bytes, little-endian)
- Timestamp: uint64 (8 bytes, little-endian)
- Sample Rate: uint32 (4 bytes, little-endian)
- Channels: uint16 (2 bytes, little-endian)
- Sample Width: uint16 (2 bytes, little-endian)
- Reserved: uint16 (2 bytes)
- Payload Length: uint32 (4 bytes, little-endian)
- PCM Audio Data: variable length (16-bit PCM samples)
"""

import socket
import struct
import logging
import threading
from queue import Queue
from typing import Optional, Tuple
import time

logger = logging.getLogger(__name__)


class USRPServer:
    """Handles incoming USRP protocol UDP streams with 32-byte header."""
    
    USRP_MAGIC = b'USRP'
    HEADER_SIZE = 32
    PACKET_TYPE_AUDIO = 0
    PACKET_TYPE_CONTROL = 1
    
    def __init__(self, config: dict, audio_queue: Queue):
        """
        Initialize USRP Server.
        
        Args:
            config: Configuration dictionary with 'usrp' section
            audio_queue: Queue to put processed audio data
        """
        self.config = config['usrp']
        self.audio_queue = audio_queue
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.sequence_counter = 0
        self.packet_count = 0
        self.error_count = 0
        self.control_packet_count = 0
        
        # Extract configuration
        self.listen_address = self.config.get('listen_address', '0.0.0.0')
        self.listen_port = self.config.get('listen_port', 40001)
        self.buffer_size = self.config.get('buffer_size', 4096)
        
        logger.info(f"USRP Server initialized: {self.listen_address}:{self.listen_port}")
    
    def _parse_usrp_packet(self, data: bytes) -> Optional[Tuple[dict, bytes]]:
        """
        Parse USRP protocol packet with 32-byte header.
        
        Format:
        - Magic: "USRP" (4 bytes)
        - Packet Type: uint32 (4 bytes, little-endian) - 0=Audio, 1=Control
        - Sequence: uint32 (4 bytes, little-endian)
        - Timestamp: uint64 (8 bytes, little-endian)
        - Sample Rate: uint32 (4 bytes, little-endian)
        - Channels: uint16 (2 bytes, little-endian)
        - Sample Width: uint16 (2 bytes, little-endian)
        - Reserved: uint16 (2 bytes)
        - Payload Length: uint32 (4 bytes, little-endian)
        - Payload: variable length
        
        Returns:
            Tuple of (header_dict, payload) or None if invalid
        """
        try:
            if len(data) < self.HEADER_SIZE:
                logger.warning(f"Packet too short: {len(data)} bytes (minimum {self.HEADER_SIZE})")
                return None
            
            # Parse magic string
            magic = data[0:4]
            if magic != self.USRP_MAGIC:
                logger.debug(f"Invalid magic: {magic.hex()} (expected {self.USRP_MAGIC.hex()})")
                return None
            
            # Parse header fields
            offset = 4
            packet_type = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            sequence = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            timestamp = struct.unpack('<Q', data[offset:offset+8])[0]
            offset += 8
            
            sample_rate = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            channels = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            
            sample_width = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            
            reserved = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            
            payload_length = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            # Extract payload
            if len(data) < self.HEADER_SIZE + payload_length:
                logger.warning(f"Packet incomplete: expected {self.HEADER_SIZE + payload_length} bytes, got {len(data)}")
                return None
            
            payload = data[self.HEADER_SIZE:self.HEADER_SIZE + payload_length]
            
            # Create header dictionary
            header = {
                'packet_type': packet_type,
                'sequence': sequence,
                'timestamp': timestamp,
                'sample_rate': sample_rate,
                'channels': channels,
                'sample_width': sample_width,
                'reserved': reserved,
                'payload_length': payload_length
            }
            
            return (header, payload)
            
        except struct.error as e:
            logger.error(f"Struct unpack error: {e}")
            self.error_count += 1
            return None
        except Exception as e:
            logger.error(f"Error parsing USRP packet: {e}", exc_info=True)
            self.error_count += 1
            return None
    
    def _handle_packet(self, data: bytes, address: Tuple[str, int]):
        """Handle incoming UDP packet."""
        try:
            parsed = self._parse_usrp_packet(data)
            if parsed is None:
                return
            
            header, payload = parsed
            
            # Handle different packet types
            packet_type = header['packet_type']
            
            if packet_type == self.PACKET_TYPE_CONTROL:
                # Control/Metadata packet - log but don't process audio
                self.control_packet_count += 1
                logger.debug(f"Control packet received: sequence={header['sequence']}")
                return
            
            elif packet_type == self.PACKET_TYPE_AUDIO:
                # Audio frame - process
                sequence = header['sequence']
                
                # Validate sequence (optional: check for out-of-order packets)
                self.sequence_counter = max(self.sequence_counter, sequence)
                
                # Create audio packet structure (only pure PCM data)
                audio_packet = {
                    'sequence': sequence,
                    'timestamp': header['timestamp'],
                    'sample_rate': header['sample_rate'],
                    'channels': header['channels'],
                    'sample_width': header['sample_width'],
                    'pcm_data': payload,  # Pure PCM data only
                    'source': 'usrp',
                    'address': address,
                    'packet_type': 'audio'
                }
                
                # Put into queue for processing
                try:
                    self.audio_queue.put(audio_packet, timeout=1.0)
                    self.packet_count += 1
                except:
                    logger.warning("Audio queue full, dropping packet")
            else:
                logger.warning(f"Unknown packet type: {packet_type}")
                return
                
        except Exception as e:
            logger.error(f"Error handling packet from {address}: {e}", exc_info=True)
            self.error_count += 1
    
    def _receive_loop(self):
        """Main receive loop in separate thread."""
        logger.info(f"USRP Server started, listening on {self.listen_address}:{self.listen_port}")
        
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
        
        logger.info("USRP Server receive loop stopped")
    
    def start(self):
        """Start the USRP server."""
        if self.running:
            logger.warning("USRP Server already running")
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
            
            logger.info(f"USRP Server started successfully on {self.listen_address}:{self.listen_port}")
            
        except Exception as e:
            logger.error(f"Failed to start USRP Server: {e}", exc_info=True)
            self.running = False
            if self.socket:
                self.socket.close()
                self.socket = None
            raise
    
    def stop(self):
        """Stop the USRP server."""
        if not self.running:
            return
        
        logger.info("Stopping USRP Server...")
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        logger.info("USRP Server stopped")
        logger.info(f"Statistics: Packets={self.packet_count}, Control={self.control_packet_count}, Errors={self.error_count}")
    
    def get_stats(self) -> dict:
        """Get server statistics."""
        return {
            'packet_count': self.packet_count,
            'control_packet_count': self.control_packet_count,
            'error_count': self.error_count,
            'sequence_counter': self.sequence_counter,
            'running': self.running
        }
