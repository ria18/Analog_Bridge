#!/usr/bin/env python3
"""
BOS-Radio-Bridge Main Orchestrator
Bidirectional Python alternative to Analog_Bridge for BOS Gateway applications.

Architecture:
TX Channel (Telefon -> Funk):
- USRP Server: Receives UDP streams on port 40001 (32-byte header)
- Audio Processor: Resampling to 8000 Hz, 16-Bit Mono PCM
- VOX Controller: Intelligent PTT/VOX control
- DMR Gateway: Sends to MMDVM_Bridge on port 33100

RX Channel (Funk -> Telefon):
- MMDVM Receiver: Receives TLV frames on port 33101
- Jitter Buffer: 20ms frame timing
- Audio Processor: process_rx_audio() for Phase 7
- USRP Client: Sends to pjsua on port 40001
"""

import json
import logging
import signal
import sys
import threading
import time
from queue import Queue
from pathlib import Path
from typing import Optional
import numpy as np

from usrp_server import USRPServer
from audio_processor import AudioProcessor
from vox_controller import VOXController
from dmr_gateway import DMRGateway
from mmdvm_receiver import MMDVMReceiver
from jitter_buffer import JitterBuffer
from usrp_client import USRPClient
from status_logger import StatusLogger
from echo_interlock import EchoInterlock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class BOSRadioBridge:
    """Main orchestrator for bidirectional BOS-Radio-Bridge."""
    
    def __init__(self, config_path: str = 'config.json'):
        """
        Initialize BOS-Radio-Bridge.
        
        Args:
            config_path: Path to configuration JSON file
        """
        self.config_path = config_path
        self.config: Optional[dict] = None
        self.running = False
        
        # Queues for TX channel (Telefon -> Funk)
        self.usrp_to_processor_queue = Queue(maxsize=100)
        self.processor_to_vox_queue = Queue(maxsize=100)
        self.vox_to_gateway_queue = Queue(maxsize=100)
        
        # Queues for RX channel (Funk -> Telefon)
        self.mmdvm_to_jitter_queue = Queue(maxsize=100)
        self.jitter_to_processor_rx_queue = Queue(maxsize=100)
        self.processor_rx_to_usrp_client_queue = Queue(maxsize=100)
        
        # TX Modules
        self.usrp_server: Optional[USRPServer] = None
        self.audio_processor_tx: Optional[AudioProcessor] = None
        self.vox_controller: Optional[VOXController] = None
        self.dmr_gateway: Optional[DMRGateway] = None
        
        # RX Modules
        self.mmdvm_receiver: Optional[MMDVMReceiver] = None
        self.jitter_buffer: Optional[JitterBuffer] = None
        self.audio_processor_rx: Optional[AudioProcessor] = None
        self.usrp_client: Optional[USRPClient] = None
        
        # Status Logger
        self.status_logger: Optional[StatusLogger] = None
        
        # Echo Interlock
        self.echo_interlock: Optional[EchoInterlock] = None
        
        # Threads
        self.tx_processing_thread: Optional[threading.Thread] = None
        self.rx_processing_thread: Optional[threading.Thread] = None
        self.jitter_buffer_thread: Optional[threading.Thread] = None
        self.stats_thread: Optional[threading.Thread] = None
        
        # Load configuration
        self.load_config()
        
        # Setup logging
        self.setup_logging()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def load_config(self):
        """Load configuration from JSON file."""
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                logger.error(f"Configuration file not found: {self.config_path}")
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
            with open(config_file, 'r') as f:
                self.config = json.load(f)
            
            logger.info(f"Configuration loaded from {self.config_path}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration: {e}", exc_info=True)
            raise
    
    def setup_logging(self):
        """Setup logging from configuration."""
        if not self.config:
            return
        
        log_config = self.config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        
        # Set log level
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(numeric_level)
        
        # File logging (if configured)
        log_file = log_config.get('file')
        if log_file:
            from logging.handlers import RotatingFileHandler
            handler = RotatingFileHandler(
                log_file,
                maxBytes=log_config.get('max_bytes', 10485760),
                backupCount=log_config.get('backup_count', 5)
            )
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            logging.getLogger().addHandler(handler)
            logger.info(f"Logging to file: {log_file}")
    
    def _calculate_audio_level(self, pcm_data: bytes) -> float:
        """Calculate audio level (RMS) from PCM data."""
        try:
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            return float(rms)
        except:
            return 0.0
    
    def _ptt_callback(self, ptt_on: bool):
        """PTT callback function for VOX controller."""
        if self.dmr_gateway:
            self.dmr_gateway.send_ptt_command(ptt_on)
        if self.status_logger:
            self.status_logger.update_tx_status(ptt_on)
    
    def initialize_modules(self):
        """Initialize all modules (TX and RX)."""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        
        logger.info("Initializing modules...")
        
        # Initialize TX modules (Telefon -> Funk)
        self.usrp_server = USRPServer(self.config, self.usrp_to_processor_queue)
        self.audio_processor_tx = AudioProcessor(
            self.config,
            self.usrp_to_processor_queue,
            self.processor_to_vox_queue
        )
        self.dmr_gateway = DMRGateway(self.config, self.vox_to_gateway_queue)
        self.vox_controller = VOXController(
            self.config,
            self.processor_to_vox_queue,
            self._ptt_callback
        )
        
        # Initialize RX modules (Funk -> Telefon)
        self.mmdvm_receiver = MMDVMReceiver(self.config, self.mmdvm_to_jitter_queue)
        self.jitter_buffer = JitterBuffer(
            self.config,
            self.mmdvm_to_jitter_queue,
            self.jitter_to_processor_rx_queue
        )
        self.audio_processor_rx = AudioProcessor(
            self.config,
            self.jitter_to_processor_rx_queue,
            self.processor_rx_to_usrp_client_queue
        )
        self.usrp_client = USRPClient(self.config, self.processor_rx_to_usrp_client_queue)
        
        # Initialize Status Logger
        status_config = self.config.get('status_logger', {})
        if status_config.get('enable', True):
            update_interval = status_config.get('update_interval', 1.0)
            self.status_logger = StatusLogger(self.config, update_interval)
        
        # Initialize Echo Interlock
        self.echo_interlock = EchoInterlock(self.config)
        
        logger.info("All modules initialized")
    
    def _tx_processing_loop(self):
        """TX processing loop (Telefon -> Funk)."""
        logger.info("TX processing loop started")
        
        while self.running:
            try:
                # Get packet from processor queue (after resampling)
                audio_packet = self.processor_to_vox_queue.get(timeout=1.0)
                
                # Echo Interlock: Check if RX is active (mute TX if RX active)
                if self.echo_interlock and self.echo_interlock.is_tx_muted():
                    # TX muted due to RX activity - drop packet or apply mute gain
                    pcm_data = audio_packet.get('pcm_data', b'')
                    if pcm_data:
                        # Apply mute gain (echo suppression)
                        mute_gain = self.echo_interlock.get_tx_gain(1.0)
                        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
                        audio_array = (audio_array * mute_gain).astype(np.int16)
                        audio_packet['pcm_data'] = audio_array.tobytes()
                        audio_packet['echo_muted'] = True
                
                # Update status logger
                if self.status_logger:
                    pcm_data = audio_packet.get('pcm_data', b'')
                    audio_level = self._calculate_audio_level(pcm_data)
                    sequence = audio_packet.get('sequence', 0)
                    self.status_logger.update_tx_status(True, audio_level, sequence)
                
                # Process through VOX controller (PTT control)
                audio_packet = self.vox_controller.process_audio_frame(audio_packet)
                
                # Put into gateway queue (only if PTT is active and not muted)
                if audio_packet.get('ptt_active', False) and not audio_packet.get('echo_muted', False):
                    try:
                        self.vox_to_gateway_queue.put(audio_packet, timeout=1.0)
                    except:
                        logger.warning("Gateway queue full, dropping packet")
                
            except:
                # Timeout is expected, continue
                continue
        
        logger.info("TX processing loop stopped")
    
    def _rx_processing_loop(self):
        """RX processing loop (Funk -> Telefon)."""
        logger.info("RX processing loop started")
        
        while self.running:
            try:
                # Get packet from jitter buffer queue
                audio_packet = self.jitter_to_processor_rx_queue.get(timeout=1.0)
                
                # Update echo interlock (RX active)
                if self.echo_interlock:
                    self.echo_interlock.set_rx_active(True)
                
                # Update status logger
                if self.status_logger:
                    pcm_data = audio_packet.get('pcm_data', b'')
                    audio_level = self._calculate_audio_level(pcm_data)
                    sequence = audio_packet.get('sequence', 0)
                    self.status_logger.update_rx_status(True, audio_level, sequence)
                
                # Process through audio processor (Phase 7: process_rx_audio)
                processed_packet = self.audio_processor_rx.process_rx_audio(audio_packet)
                
                if processed_packet:
                    # Put into USRP client queue
                    try:
                        self.processor_rx_to_usrp_client_queue.put(processed_packet, timeout=1.0)
                    except:
                        logger.warning("USRP client queue full, dropping packet")
                
            except:
                # Timeout is expected, continue
                continue
        
        logger.info("RX processing loop stopped")
    
    def _jitter_buffer_loop(self):
        """Jitter buffer processing loop."""
        logger.info("Jitter buffer loop started")
        
        while self.running:
            try:
                # Process jitter buffer
                self.jitter_buffer.process()
                
                # Small delay to prevent CPU spinning
                time.sleep(0.001)  # 1ms
                
            except Exception as e:
                if self.running:
                    logger.error(f"Error in jitter buffer loop: {e}", exc_info=True)
                break
        
        logger.info("Jitter buffer loop stopped")
    
    def _stats_loop(self):
        """Print statistics periodically."""
        logger.info("Statistics loop started")
        
        while self.running:
            try:
                time.sleep(30)  # Print stats every 30 seconds
                
                if not self.running:
                    break
                
                stats = self.get_stats()
                logger.info(f"Statistics: {json.dumps(stats, indent=2)}")
                
            except:
                break
        
        logger.info("Statistics loop stopped")
    
    def start(self):
        """Start the BOS-Radio-Bridge (bidirectional)."""
        if self.running:
            logger.warning("BOS-Radio-Bridge already running")
            return
        
        logger.info("Starting BOS-Radio-Bridge (bidirectional)...")
        
        try:
            # Initialize modules
            self.initialize_modules()
            
            # Start TX modules
            self.usrp_server.start()
            self.dmr_gateway.start()
            
            # Start RX modules
            self.mmdvm_receiver.start()
            self.usrp_client.start()
            
            # Start Status Logger
            if self.status_logger:
                self.status_logger.start()
            
            # Start processing threads (bidirectional)
            self.running = True
            
            # TX processing thread
            self.tx_processing_thread = threading.Thread(target=self._tx_processing_loop, daemon=True)
            self.tx_processing_thread.start()
            
            # RX processing thread
            self.rx_processing_thread = threading.Thread(target=self._rx_processing_loop, daemon=True)
            self.rx_processing_thread.start()
            
            # Jitter buffer thread
            self.jitter_buffer_thread = threading.Thread(target=self._jitter_buffer_loop, daemon=True)
            self.jitter_buffer_thread.start()
            
            # Statistics thread
            if self.config.get('system', {}).get('enable_metrics', True):
                self.stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
                self.stats_thread.start()
            
            logger.info("BOS-Radio-Bridge started successfully (bidirectional)")
            logger.info("Press Ctrl+C to stop")
            
        except Exception as e:
            logger.error(f"Failed to start BOS-Radio-Bridge: {e}", exc_info=True)
            self.stop()
            raise
    
    def stop(self):
        """Stop the BOS-Radio-Bridge with thread-safe shutdown."""
        with self._shutdown_lock:
            if not self.running:
                return
            
            logger.info("Stopping BOS-Radio-Bridge...")
            self.running = False
            
            # Send final PTT OFF command (critical for safety)
            try:
                if self.dmr_gateway:
                    logger.info("Sending final PTT OFF command...")
                    self.dmr_gateway.send_ptt_command(False)
                    time.sleep(0.1)  # Small delay to ensure command is sent
            except Exception as e:
                logger.error(f"Error sending final PTT OFF: {e}", exc_info=True)
            
            # Force PTT OFF in VOX controller
            try:
                if self.vox_controller:
                    self.vox_controller.force_ptt_off()
            except Exception as e:
                logger.error(f"Error forcing PTT OFF: {e}", exc_info=True)
            
            # Stop modules (UDP sockets must be closed)
            try:
                if self.usrp_server:
                    self.usrp_server.stop()
            except Exception as e:
                logger.error(f"Error stopping USRP server: {e}", exc_info=True)
            
            try:
                if self.dmr_gateway:
                    self.dmr_gateway.stop()
            except Exception as e:
                logger.error(f"Error stopping DMR gateway: {e}", exc_info=True)
            
            try:
                if self.mmdvm_receiver:
                    self.mmdvm_receiver.stop()
            except Exception as e:
                logger.error(f"Error stopping MMDVM receiver: {e}", exc_info=True)
            
            try:
                if self.usrp_client:
                    self.usrp_client.stop()
            except Exception as e:
                logger.error(f"Error stopping USRP client: {e}", exc_info=True)
            
            try:
                if self.status_logger:
                    self.status_logger.stop()
            except Exception as e:
                logger.error(f"Error stopping status logger: {e}", exc_info=True)
            
            # Wait for threads (prevent zombie processes)
            threads = [
                ('tx_processing', self.tx_processing_thread),
                ('rx_processing', self.rx_processing_thread),
                ('jitter_buffer', self.jitter_buffer_thread),
                ('stats', self.stats_thread)
            ]
            
            for name, thread in threads:
                if thread and thread.is_alive():
                    logger.debug(f"Waiting for {name} thread to finish...")
                    thread.join(timeout=2.0)
                    if thread.is_alive():
                        logger.warning(f"{name} thread did not finish in time")
            
            logger.info("BOS-Radio-Bridge stopped")
            
            # Print final statistics
            try:
                stats = self.get_stats()
                logger.info(f"Final statistics: {json.dumps(stats, indent=2)}")
            except Exception as e:
                logger.error(f"Error getting final statistics: {e}", exc_info=True)
            
            # Signal shutdown complete
            self._shutdown_complete.set()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals with thread-safe cleanup."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        try:
            self.stop()
            # Wait for shutdown to complete
            if not self._shutdown_complete.wait(timeout=5.0):
                logger.warning("Shutdown did not complete in time")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
        finally:
            sys.exit(0)
    
    def get_stats(self) -> dict:
        """Get statistics from all modules."""
        stats = {
            'running': self.running
        }
        
        if self.usrp_server:
            stats['usrp_server'] = self.usrp_server.get_stats()
        
        if self.audio_processor_tx:
            stats['audio_processor_tx'] = self.audio_processor_tx.get_stats()
        
        if self.vox_controller:
            stats['vox_controller'] = self.vox_controller.get_stats()
        
        if self.dmr_gateway:
            stats['dmr_gateway'] = self.dmr_gateway.get_stats()
        
        if self.mmdvm_receiver:
            stats['mmdvm_receiver'] = self.mmdvm_receiver.get_stats()
        
        if self.jitter_buffer:
            stats['jitter_buffer'] = self.jitter_buffer.get_stats()
        
        if self.audio_processor_rx:
            stats['audio_processor_rx'] = self.audio_processor_rx.get_stats()
        
        if self.usrp_client:
            stats['usrp_client'] = self.usrp_client.get_stats()
        
        if self.status_logger:
            stats['status_logger'] = self.status_logger.get_stats()
        
        return stats
    
    def run(self):
        """Run the BOS-Radio-Bridge (blocking)."""
        try:
            self.start()
            
            # Keep running until stopped
            while self.running:
                time.sleep(1)
            
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
        finally:
            self.stop()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='BOS-Radio-Bridge - Bidirectional Python alternative to Analog_Bridge')
    parser.add_argument('-c', '--config', default='config.json', help='Configuration file path')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run bridge
    bridge = BOSRadioBridge(config_path=args.config)
    bridge.run()


if __name__ == '__main__':
    main()
