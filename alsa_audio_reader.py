#!/usr/bin/env python3
"""
ALSA Audio Reader Module
Reads audio stream from ALSA Loopback device (hw:2,1) for BOS Gateway.

Features:
- ALSA Loopback device input (hw:2,1)
- Mono, 16000 Hz, 16-bit PCM (BOS standard)
- Queue-based buffering for jitter prevention
- Low latency design
- Phase 7: AI noise reduction placeholder
- Thread-safe implementation
"""

import logging
import threading
import time
import numpy as np
from queue import Queue, Empty
from typing import Optional, Callable
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    try:
        import pyaudio
        PYAUDIO_AVAILABLE = True
        SOUNDDEVICE_AVAILABLE = False
    except ImportError:
        SOUNDDEVICE_AVAILABLE = False
        PYAUDIO_AVAILABLE = False
        logging.warning("Neither sounddevice nor pyaudio available. Install one: pip install sounddevice or pip install pyaudio")

logger = logging.getLogger(__name__)


class AlsaAudioReader:
    """ALSA Audio Reader for BOS Gateway with low latency and queue-based buffering."""
    
    def __init__(self, config: dict, audio_queue: Queue):
        """
        Initialize ALSA Audio Reader.
        
        Args:
            config: Configuration dictionary with 'alsa' section
            audio_queue: Queue to put audio data
        """
        self.config = config.get('alsa', {})
        self.audio_queue = audio_queue
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # ALSA configuration
        self.device = self.config.get('device', 'hw:2,1')
        self.sample_rate = self.config.get('sample_rate', 16000)  # BOS standard: 16 kHz
        self.channels = self.config.get('channels', 1)  # Mono
        self.dtype = self.config.get('dtype', 'int16')
        self.sample_width = 2  # 16-bit = 2 bytes
        
        # Buffer configuration
        self.blocksize = self.config.get('blocksize', 320)  # 20ms at 16kHz (16000 * 0.02)
        self.queue_size = self.config.get('queue_size', 10)  # Number of blocks in queue
        self.buffer_size = self.config.get('buffer_size', 4096)
        
        # Statistics
        self.frames_read = 0
        self.overflows = 0
        self.underflows = 0
        self.errors = 0
        self.bytes_read = 0
        
        # Phase 7: AI noise reduction callback (placeholder)
        self.ai_noise_reduction_callback: Optional[Callable[[np.ndarray], np.ndarray]] = None
        
        # Audio stream
        self.stream = None
        self.audio_device = None
        
        logger.info(f"ALSA Audio Reader initialized: device={self.device}, sample_rate={self.sample_rate}Hz, channels={self.channels}")
    
    def register_ai_noise_reduction(self, callback: Callable[[np.ndarray], np.ndarray]):
        """
        Register AI noise reduction callback (Phase 7).
        
        Args:
            callback: Callable that takes numpy array (audio data) and returns processed numpy array
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self.ai_noise_reduction_callback = callback
        logger.info("AI noise reduction callback registered (Phase 7)")
    
    def _apply_ai_noise_reduction(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Apply AI noise reduction (Phase 7 placeholder).
        
        Args:
            audio_data: Input audio as numpy array (int16)
            
        Returns:
            Processed audio as numpy array (int16)
        """
        if self.ai_noise_reduction_callback:
            try:
                return self.ai_noise_reduction_callback(audio_data)
            except Exception as e:
                logger.error(f"Error in AI noise reduction callback: {e}", exc_info=True)
                # Return original data on error
                return audio_data
        
        # No AI processing - return original
        return audio_data
    
    def _audio_callback_sounddevice(self, indata, frames, time_info, status):
        """Audio callback for sounddevice."""
        if status:
            logger.warning(f"Audio callback status: {status}")
            if status.input_overflow:
                self.overflows += 1
            if status.input_underflow:
                self.underflows += 1
        
        try:
            # Convert to int16 (sounddevice uses float32 by default)
            if indata.dtype == np.float32:
                # Convert from float32 [-1.0, 1.0] to int16 [-32768, 32767]
                audio_int16 = (indata * 32767).astype(np.int16)
            else:
                audio_int16 = indata.astype(np.int16)
            
            # Convert to mono if needed
            if self.channels == 1 and audio_int16.ndim > 1 and audio_int16.shape[1] > 1:
                audio_int16 = np.mean(audio_int16, axis=1, dtype=np.int16)
            
            # Phase 7: Apply AI noise reduction (placeholder)
            audio_int16 = self._apply_ai_noise_reduction(audio_int16)
            
            # Convert to bytes (little-endian)
            audio_bytes = audio_int16.tobytes()
            
            # Create audio packet
            audio_packet = {
                'pcm_data': audio_bytes,
                'sample_rate': self.sample_rate,
                'channels': self.channels,
                'sample_width': self.sample_width,
                'source': 'alsa',
                'device': self.device,
                'timestamp': time.time(),
                'sequence': self.frames_read
            }
            
            # Put into queue (non-blocking to prevent overflow)
            try:
                self.audio_queue.put_nowait(audio_packet)
                self.frames_read += 1
                self.bytes_read += len(audio_bytes)
            except:
                # Queue full - drop packet silently (prevent buffer overflow and log spam)
                self.overflows += 1
                # Only log warning every 100 overflows to reduce log spam
                if self.overflows % 100 == 0:
                    logger.debug(f"Audio queue full, dropped {self.overflows} packets")
                
        except Exception as e:
            logger.error(f"Error in audio callback: {e}", exc_info=True)
            self.errors += 1
    
    def _audio_loop_sounddevice(self):
        """Main audio loop using sounddevice."""
        logger.info(f"ALSA Audio Reader started (sounddevice): device={self.device}, {self.sample_rate}Hz")
        
        try:
            # Open audio stream
            with sd.InputStream(
                device=self.device,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype='int16',
                blocksize=self.blocksize,
                callback=self._audio_callback_sounddevice,
                latency='low'
            ):
                logger.info(f"Audio stream opened successfully: {self.device}")
                
                # Keep running until stopped
                while self.running:
                    time.sleep(0.1)  # Small sleep to prevent CPU spinning
                    
        except Exception as e:
            logger.error(f"Error in audio loop: {e}", exc_info=True)
            self.errors += 1
            self.running = False
        
        logger.info("ALSA Audio Reader loop stopped")
    
    def _audio_loop_pyaudio(self):
        """Main audio loop using pyaudio (fallback)."""
        logger.info(f"ALSA Audio Reader started (pyaudio): device={self.device}, {self.sample_rate}Hz")
        
        try:
            import pyaudio
            
            p = pyaudio.PyAudio()
            
            # Find device index from device name
            device_index = None
            device_name = self.device
            
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if device_name in info['name'] or device_name == str(i):
                    device_index = i
                    break
            
            if device_index is None:
                logger.error(f"Device not found: {self.device}")
                raise ValueError(f"Device not found: {self.device}")
            
            # Open audio stream
            stream = p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.blocksize
            )
            
            logger.info(f"Audio stream opened successfully: {self.device} (index {device_index})")
            
            # Read audio loop
            while self.running:
                try:
                    # Read audio data
                    audio_data = stream.read(self.blocksize, exception_on_overflow=False)
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    
                    # Phase 7: Apply AI noise reduction (placeholder)
                    audio_array = self._apply_ai_noise_reduction(audio_array)
                    
                    # Convert to bytes
                    audio_bytes = audio_array.tobytes()
                    
                    # Create audio packet
                    audio_packet = {
                        'pcm_data': audio_bytes,
                        'sample_rate': self.sample_rate,
                        'channels': self.channels,
                        'sample_width': self.sample_width,
                        'source': 'alsa',
                        'device': self.device,
                        'timestamp': time.time(),
                        'sequence': self.frames_read
                    }
                    
                    # Put into queue (non-blocking)
                    try:
                        self.audio_queue.put_nowait(audio_packet)
                        self.frames_read += 1
                        self.bytes_read += len(audio_bytes)
                    except:
                        # Queue full - drop packet
                        self.overflows += 1
                        logger.warning("Audio queue full, dropping packet")
                        
                except Exception as e:
                    logger.error(f"Error reading audio: {e}", exc_info=True)
                    self.errors += 1
                    break
            
            # Cleanup
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            logger.error(f"Error in audio loop (pyaudio): {e}", exc_info=True)
            self.errors += 1
            self.running = False
        
        logger.info("ALSA Audio Reader loop stopped")
    
    def start(self):
        """Start the ALSA Audio Reader."""
        if self.running:
            logger.warning("ALSA Audio Reader already running")
            return
        
        # Check for available audio library
        if not SOUNDDEVICE_AVAILABLE and not PYAUDIO_AVAILABLE:
            logger.error("No audio library available. Install sounddevice or pyaudio.")
            raise RuntimeError("No audio library available. Install sounddevice or pyaudio.")
        
        try:
            self.running = True
            
            # Start audio thread (prefer sounddevice)
            if SOUNDDEVICE_AVAILABLE:
                self.thread = threading.Thread(target=self._audio_loop_sounddevice, daemon=True)
            elif PYAUDIO_AVAILABLE:
                self.thread = threading.Thread(target=self._audio_loop_pyaudio, daemon=True)
            else:
                raise RuntimeError("No audio library available")
            
            self.thread.start()
            
            logger.info(f"ALSA Audio Reader started successfully: {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to start ALSA Audio Reader: {e}", exc_info=True)
            self.running = False
            raise
    
    def stop(self):
        """Stop the ALSA Audio Reader."""
        if not self.running:
            return
        
        logger.info("Stopping ALSA Audio Reader...")
        self.running = False
        
        # Wait for thread
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        logger.info("ALSA Audio Reader stopped")
        logger.info(f"Statistics: Frames={self.frames_read}, Overflows={self.overflows}, Underflows={self.underflows}, Errors={self.errors}, Bytes={self.bytes_read}")
    
    def get_stats(self) -> dict:
        """Get reader statistics."""
        return {
            'frames_read': self.frames_read,
            'overflows': self.overflows,
            'underflows': self.underflows,
            'errors': self.errors,
            'bytes_read': self.bytes_read,
            'running': self.running,
            'device': self.device,
            'sample_rate': self.sample_rate,
            'ai_callback_registered': self.ai_noise_reduction_callback is not None
        }

