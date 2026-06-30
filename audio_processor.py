"""
Advanced Audio Processing for Low Voice Detection
Handles noise reduction, audio enhancement, and microphone sensitivity optimization.
"""

import os
import sys
import time
import logging
import io
from typing import Optional, Tuple
import numpy as np
import wave
import audioop

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("audio_processor")

try:
    import speech_recognition as sr
except ImportError:
    logger.error("Missing: pip install SpeechRecognition pydub")
    sys.exit(1)

try:
    from pydub import AudioSegment
    from pydub.effects import normalize
except ImportError:
    logger.warning("pydub not available, audio normalization disabled. Install: pip install pydub")
    AudioSegment = None

try:
    import noisereduce as nr
except ImportError:
    logger.warning("noisereduce not available. Install for better low-voice detection: pip install noisereduce")
    nr = None

try:
    import pocketsphinx  # type: ignore
    HAS_POCKETSPHINX = True
    logger.info("PocketSphinx is available for offline recognition")
except ImportError:
    HAS_POCKETSPHINX = False
    logger.info("PocketSphinx is not available; offline recognition will be disabled")

# Import voice configuration
try:
    from voice_config import VoiceConfig
except ImportError:
    logger.warning("voice_config not found, using hardcoded defaults")
    class VoiceConfig:
        INITIAL_ENERGY_THRESHOLD = 150
        CALIBRATION_DURATION = 3
        LISTEN_TIMEOUT = 8
        PHRASE_TIME_LIMIT = 15
        PAUSE_THRESHOLD = 0.8
        PHRASE_THRESHOLD = 0.1
        NON_SPEAKING_DURATION = 0.3


class AudioProcessor:
    """Enhanced audio processing for speech recognition."""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Optional device selection via environment variable
        self.mic_index = None
        try:
            mic_idx = os.environ.get("AUDIO_DEVICE_INDEX")
            if mic_idx is not None:
                self.mic_index = int(mic_idx)
                logger.info(f"Using microphone device index from env: {self.mic_index}")
        except Exception:
            self.mic_index = None

        # FORCE default device to 10 when no env var is provided to improve detection
        # This targets common Realtek headset setups where index 10 is known working.
        if self.mic_index is None:
            try:
                forced_default = 10
                logger.info(f"Forcing default microphone device index to {forced_default}")
                self.mic_index = forced_default
            except Exception:
                self.mic_index = None

        # If no explicit device configured, try to auto-select a good microphone
        if self.mic_index is None:
            self.mic_index = self._pick_preferred_mic()
            if self.mic_index is not None:
                try:
                    names = sr.Microphone.list_microphone_names()
                    logger.info(f"Auto-selected microphone index {self.mic_index}: {names[self.mic_index]}")
                except Exception:
                    logger.info(f"Auto-selected microphone index {self.mic_index}")

        # Validate the selected microphone or probe for a working one
        self._validate_or_probe_microphone()

        self.voice_profile_name = os.environ.get("AUDIO_VOICE_PROFILE", "").strip()
        self.voice_profile = None
        if self.voice_profile_name:
            self.voice_profile = getattr(VoiceConfig, "VOICE_PROFILES", {}).get(
                self.voice_profile_name
            )
            if self.voice_profile:
                logger.info(f"Using voice profile: {self.voice_profile_name}")
            else:
                logger.warning(
                    f"Unknown voice profile '{self.voice_profile_name}'. Using default low-voice settings."
                )

        self._configure_recognizer_for_low_voice()

        # Log final chosen device and a short diagnostic (RMS) to help confirm selection
        try:
            diag = self.run_diagnostic(duration=1)
            logger.info(f"Final microphone selection: index={self.mic_index} diagnostic={diag}")
        except Exception as e:
            logger.debug(f"Could not run final diagnostic: {e}")

    def _pick_preferred_mic(self) -> Optional[int]:
        """Heuristic selection of a preferred microphone index.

        Scans available microphone names and selects the most likely candidate
        based on common substrings and a prioritized device order.
        """
        try:
            names = sr.Microphone.list_microphone_names()
        except Exception:
            return None

        if not names:
            return None

        try:
            for i, n in enumerate(names):
                logger.debug(f"Mic list: index={i} name={n}")
        except Exception:
            pass

        candidate_order = self._preferred_device_order(names)
        if candidate_order:
            selected = candidate_order[0]
            logger.info(f"Selected microphone index {selected}: {names[selected]}")
            return selected

        logger.warning("No clear microphone candidate found; falling back to first device (may be output-only)")
        if names:
            lower_first = names[0].lower()
            if any(ex in lower_first for ex in ("output", "speaker", "playback", "stereo mix", "virtual", "loopback", "hitpaw", "microsoft sound mapper")):
                logger.warning("Fallback device appears to be an output/virtual device; not selecting by default.")
                return None
            logger.info(f"Fallback device 0: {names[0]}")
            return 0
        return None

    def _validate_or_probe_microphone(self) -> None:
        """Validate the selected mic or probe for a working one."""
        try:
            names = sr.Microphone.list_microphone_names()
        except Exception:
            names = []

        if self.mic_index is not None:
            if self.mic_index >= len(names) or self._is_output_device(names[self.mic_index]):
                logger.warning(f"Selected device index {self.mic_index} appears invalid or output-only. Probing other microphones.")
                self.mic_index = None
            elif not self._probe_microphone(self.mic_index):
                logger.warning(f"Selected device index {self.mic_index} did not return sufficient audio. Probing other microphones.")
                self.mic_index = None

        if self.mic_index is None:
            names = names or []
            candidate_indexes = self._preferred_device_order(names)
            if self._probe_best_microphone(candidate_indexes):
                return

            try:
                working = self.find_working_microphone()
                if working is not None:
                    self.mic_index = working
                    logger.info(f"Detected working microphone index: {self.mic_index}")
                else:
                    logger.warning("No working microphone auto-detected; please verify your microphone device or set AUDIO_DEVICE_INDEX.")
            except Exception as e:
                logger.warning(f"Microphone auto-detection failed: {type(e).__name__}: {e}")

    def _probe_microphone(self, index: int, duration: float = 1.0, min_rms: float = None) -> bool:
        """Probe a single microphone index using SpeechRecognition and return True if it has audio."""
        if min_rms is None:
            min_rms = getattr(VoiceConfig, 'MINIMUM_AUDIO_RMS', 20.0)
        try:
            if index is None:
                return False
            with sr.Microphone(device_index=index) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.record(source, duration=duration)
            wav_bytes = audio.get_wav_data()
            with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
                frames = w.readframes(w.getnframes())
                sampwidth = w.getsampwidth()
                channels = w.getnchannels()

            if channels > 1:
                mono = audioop.tomono(frames, sampwidth, 1, 1)
            else:
                mono = frames
            rms = float(audioop.rms(mono, sampwidth))
            logger.info(f"Probe device {index} RMS={rms:.2f}")
            return rms >= min_rms
        except Exception as e:
            logger.debug(f"Probe microphone {index} failed: {type(e).__name__}: {e}")
            return False

    def _probe_best_microphone(self, candidate_indexes: list) -> bool:
        """Probe candidate devices and select the first strong microphone."""
        if not candidate_indexes:
            return False
        for idx in candidate_indexes:
            if self._probe_microphone(idx):
                self.mic_index = idx
                try:
                    names = sr.Microphone.list_microphone_names()
                    logger.info(f"Auto-selected working microphone index {idx}: {names[idx]}")
                except Exception:
                    logger.info(f"Auto-selected working microphone index {idx}")
                return True
        return False

    def _is_output_device(self, name: str) -> bool:
        lower = name.lower()
        return any(k in lower for k in ("output", "speaker", "playback", "stereo mix", "virtual", "hitpaw", "loopback", "microsoft sound mapper"))

    def _preferred_device_order(self, names: list) -> list:
        priorities = ["headset microphone", "headset", "microphone array", "microphone", "usb", "realtek", "intel"]
        candidates = []
        for idx, name in enumerate(names):
            if self._is_output_device(name):
                continue
            score = 999
            lower = name.lower()
            for priority_index, keyword in enumerate(priorities):
                if keyword in lower:
                    score = priority_index
                    break
            candidates.append((score, idx))
        candidates.sort(key=lambda item: (item[0], item[1]))
        return [idx for _, idx in candidates]

    def _configure_recognizer_for_low_voice(self):
        """
        Optimize recognizer for low-volume voices.
        Key settings:
        - LOW energy_threshold for maximum sensitivity (but not extreme)
        - Disabled dynamic_energy: prevents aggressive auto-adjustment that cuts words
        - OPTIMAL pause_threshold: fast detection without cutting mid-sentence
        """
        profile = self.voice_profile or {}

        # Use configured initial threshold (default 30) - proven optimal for low voices
        self.recognizer.energy_threshold = VoiceConfig.INITIAL_ENERGY_THRESHOLD

        # DISABLE dynamic energy adjustment - it interferes with word capture
        self.recognizer.dynamic_energy_threshold = False

        # Pause threshold: Detect end-of-phrase quickly without cutting words
        self.recognizer.pause_threshold = VoiceConfig.PAUSE_THRESHOLD

        # Phrase threshold: Minimum audio duration to consider as speech
        self.recognizer.phrase_threshold = VoiceConfig.PHRASE_THRESHOLD

        # Non-speaking duration: Allow natural pauses within continuous speech
        self.recognizer.non_speaking_duration = VoiceConfig.NON_SPEAKING_DURATION

        logger.info(f"✓ Recognizer configured for LOW-VOICE detection")
        logger.info(
            f"  - Energy threshold: {self.recognizer.energy_threshold} (low sensitivity)"
        )
        logger.info(
            f"  - Pause threshold: {self.recognizer.pause_threshold}s (end-of-phrase detection)"
        )
        logger.info(
            f"  - Phrase threshold: {self.recognizer.phrase_threshold}s (ultra-sensitive)"
        )
        logger.info(
            f"  - Non-speaking duration: {self.recognizer.non_speaking_duration}s (continuous speech)"
        )
        logger.info(f"  - Dynamic adjustment: DISABLED (prevents word cutting)")
    
    def calibrate_microphone(self, duration: int = None) -> int:
        """
        Calibrate microphone for ambient noise with low-voice focus.
        
        Args:
            duration: Calibration duration in seconds (default from config)
        
        Returns:
            Adjusted energy threshold
        """
        if duration is None:
            duration = VoiceConfig.CALIBRATION_DURATION
            
        try:
            mic_args = {}
            if self.mic_index is not None:
                mic_args["device_index"] = self.mic_index
            with sr.Microphone(**mic_args) as source:
                logger.info(f"🔧 Calibrating microphone for {duration}s... Please be silent.")
                
                # Keep dynamic disabled - we use fixed low threshold
                old_dynamic = self.recognizer.dynamic_energy_threshold
                self.recognizer.dynamic_energy_threshold = False
                
                self.recognizer.adjust_for_ambient_noise(source, duration=duration)
                calibrated_threshold = self.recognizer.energy_threshold
                logger.info(f"Post-calibration energy threshold: {calibrated_threshold}")
                
                # Cap to MAX_ENERGY_THRESHOLD to prevent too-high thresholds in noisy environments
                if calibrated_threshold > VoiceConfig.MAX_ENERGY_THRESHOLD:
                    self.recognizer.energy_threshold = VoiceConfig.MAX_ENERGY_THRESHOLD
                    logger.info(f"⚠️  Calibration result ({calibrated_threshold}) exceeded max. Capped to {VoiceConfig.MAX_ENERGY_THRESHOLD}")
                # Ensure minimum sensitivity
                elif calibrated_threshold < VoiceConfig.INITIAL_ENERGY_THRESHOLD:
                    self.recognizer.energy_threshold = VoiceConfig.INITIAL_ENERGY_THRESHOLD
                    logger.info(f"✓ Calibration result ({calibrated_threshold}) lower than initial. Using better sensitivity: {VoiceConfig.INITIAL_ENERGY_THRESHOLD}")
                
                logger.info(f"✓ Calibration complete. Energy threshold: {self.recognizer.energy_threshold}")
                return self.recognizer.energy_threshold
                
        except Exception as e:
            logger.error(f"Microphone calibration failed: {e}")
            # On calibration failure, use the configured default
            self.recognizer.energy_threshold = VoiceConfig.INITIAL_ENERGY_THRESHOLD
            logger.warning(f"Using default threshold: {self.recognizer.energy_threshold}")
            return self.recognizer.energy_threshold

    def run_diagnostic(self, duration: int = 3) -> dict:
        """
        Record a short diagnostic sample and report RMS/peak levels and sample rate.

        Returns:
            dict: {"sample_rate", "channels", "rms", "peak", "dBFS"}
        """
        try:
            mic_args = {}
            if self.mic_index is not None:
                mic_args["device_index"] = self.mic_index

            with sr.Microphone(**mic_args) as source:
                logger.info(f"Recording diagnostic sample for {duration}s...")
                audio = self.recognizer.record(source, duration=duration)

            wav_bytes = audio.get_wav_data()
            import wave
            import math

            with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
                frames = w.readframes(w.getnframes())
                sampwidth = w.getsampwidth()
                channels = w.getnchannels()
                framerate = w.getframerate()

            dtype = None
            if sampwidth == 2:
                dtype = np.int16
            elif sampwidth == 4:
                dtype = np.int32
            else:
                dtype = np.int8

            audio_array = np.frombuffer(frames, dtype=dtype)
            # If stereo, take mean across channels
            if channels > 1:
                audio_array = audio_array.reshape((-1, channels)).mean(axis=1)

            audio_f = audio_array.astype(np.float64)
            rms = float(np.sqrt(np.mean(audio_f ** 2)))
            peak = float(np.max(np.abs(audio_f)))
            dbfs = 20 * math.log10(rms) if rms > 0 else float('-inf')

            result = {
                "sample_rate": framerate,
                "channels": channels,
                "rms": rms,
                "peak": peak,
                "dBFS": dbfs,
            }
            logger.info(f"Diagnostic: sr={framerate} ch={channels} rms={rms:.2f} peak={peak:.2f} dBFS={dbfs:.2f}")
            return result

        except Exception as e:
            logger.warning(f"Diagnostic failed: {e}")
            return {}

    def find_working_microphone(self, try_duration: float = 1.5, min_rms: float = None) -> Optional[int]:
        """
        Probe available microphones and pick the device that returns the strongest measurable audio signal.

        Returns the device index or None if none found.
        """
        if min_rms is None:
            min_rms = getattr(VoiceConfig, 'MINIMUM_AUDIO_RMS', 20.0)

        try:
            names = sr.Microphone.list_microphone_names()
        except Exception as e:
            logger.warning(f"Could not list microphones: {e}")
            return None

        if not names:
            logger.warning("No microphone devices found")
            return None

        logger.info(f"Probing {len(names)} microphone(s) to find a working device...")
        candidate_indexes = self._preferred_device_order(names)
        if self.mic_index is not None and self.mic_index in candidate_indexes:
            candidate_indexes.insert(0, candidate_indexes.pop(candidate_indexes.index(self.mic_index)))

        best_candidate = None
        best_rms = 0.0

        for i in candidate_indexes:
            name = names[i]
            logger.info(f"Probing device {i}: {name}")
            try:
                with sr.Microphone(device_index=i) as source:
                    try:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    except Exception:
                        pass
                    audio = self.recognizer.record(source, duration=try_duration)

                wav_bytes = audio.get_wav_data()
                with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
                    frames = w.readframes(w.getnframes())
                    sampwidth = w.getsampwidth()
                    channels = w.getnchannels()

                if channels > 1:
                    try:
                        mono = audioop.tomono(frames, sampwidth, 1, 1)
                    except Exception:
                        mono = frames
                else:
                    mono = frames

                try:
                    rms = float(audioop.rms(mono, sampwidth))
                except Exception:
                    rms = 0.0

                logger.info(f"Device {i} RMS={rms:.2f}")
                if rms > best_rms:
                    best_rms = rms
                    best_candidate = i
                if rms >= min_rms:
                    logger.info(f"Selected working microphone index {i}: {name} (rms={rms:.2f})")
                    return i

            except Exception as e:
                logger.debug(f"Probe failed for device {i}: {e}")
                continue

        if best_candidate is not None and best_rms > 0:
            name = names[best_candidate]
            logger.warning(
                f"No device reached the desired RMS threshold ({min_rms}); "
                f"selecting best candidate {best_candidate}: {name} (rms={best_rms:.2f})"
            )
            return best_candidate

        logger.warning("No working microphone detected by probe")
        return None

    def _get_input_devices(self) -> list:
        """Get list of likely input device indices, filtering out output devices."""
        try:
            names = sr.Microphone.list_microphone_names()
        except Exception:
            return [None]  # Default device

        input_devices = []
        for i, name in enumerate(names):
            if self._is_output_device(name):
                continue
            input_devices.append(i)

        if not input_devices:
            return [None]

        sorted_inputs = [i for i in self._preferred_device_order(names) if i in input_devices]
        return sorted_inputs if sorted_inputs else input_devices
    
    def recognize_speech(self, 
                        timeout: int = None, 
                        phrase_time_limit: int = None,
                        max_retries: int = None) -> Optional[str]:
        """
        Recognize speech with AGGRESSIVE low-voice detection and retry logic.
        
        Args:
            timeout: Maximum time to wait for speech (seconds)
            phrase_time_limit: Maximum duration of recognized phrase (seconds)
            max_retries: Number of retries on failure
        
        Returns:
            Recognized text or None if failed
        """
        # Use config defaults if not specified
        if timeout is None:
            timeout = VoiceConfig.LISTEN_TIMEOUT
        if phrase_time_limit is None:
            phrase_time_limit = VoiceConfig.PHRASE_TIME_LIMIT
        if max_retries is None:
            max_retries = VoiceConfig.MAX_RETRIES
            
        retry_count = 0
        last_error = None
        initial_threshold = self.recognizer.energy_threshold
        
        # Build a list of devices to try in rotation
        devices_to_try = self._get_input_devices()
        if self.mic_index is not None and self.mic_index not in devices_to_try:
            devices_to_try.insert(0, self.mic_index)
        
        logger.info(f"Will try audio devices in order: {devices_to_try}")
        device_pos = 0
        
        while retry_count < max_retries:
            source = None
            audio = None
            raw_wav = None
            
            try:
                # Rotate through available devices on each retry
                current_device = devices_to_try[device_pos % len(devices_to_try)]
                device_pos += 1
                
                mic_args = {}
                if current_device is not None:
                    mic_args["device_index"] = current_device

                try:
                    source = sr.Microphone(**mic_args)
                except Exception as e:
                    logger.warning(f"Failed to create microphone source (device {current_device}): {e}")
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(0.3)
                    continue

                src = None
                try:
                    src = source.__enter__()
                    if src is None:
                        logger.warning(f"Microphone context manager __enter__ returned None")
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(0.3)
                        continue
                    
                    # Log source details for diagnostics
                    try:
                        sr_rate = getattr(src, 'SAMPLE_RATE', None) or getattr(src, 'sample_rate', None)
                        sr_width = getattr(src, 'SAMPLE_WIDTH', None) or getattr(src, 'sample_width', None)
                        logger.debug(f"Microphone source - sample_rate={sr_rate} sample_width={sr_width}")
                    except Exception:
                        pass


                    # Progressive threshold reduction: drop gradually per retry for sensitivity increase
                    if retry_count == 0:
                        logger.info(f"🎤 Listening (threshold: {self.recognizer.energy_threshold})...")
                    else:
                        # Drop by 2-5% per retry (gradual sensitivity increase)
                        pct_drop = min(3 + (retry_count * 1), 10)  # 3%, 4%, 5%...
                        new_threshold = max(
                            VoiceConfig.MIN_ENERGY_THRESHOLD,
                            int(initial_threshold * (1 - pct_drop / 100.0))
                        )
                        self.recognizer.energy_threshold = new_threshold
                        logger.info(f"🎤 Retry #{retry_count}/{max_retries} - Threshold: {new_threshold} (sensitivity +{pct_drop}%)")

                    # Keep dynamic adjustment DISABLED (prevents word cutting)
                    self.recognizer.dynamic_energy_threshold = False

                    # Listen with extended timeout
                    effective_timeout = timeout if retry_count == 0 else max(5, timeout - retry_count * 2)
                    logger.info(f"   Listening for {effective_timeout}s (phrase limit {phrase_time_limit}s)...")

                    audio = self.recognizer.listen(
                        src,
                        timeout=effective_timeout,
                        phrase_time_limit=phrase_time_limit
                    )

                    # Log captured audio size and characteristics
                    if audio is not None:
                        raw_wav = audio.get_wav_data()
                        logger.info(f"✅ Audio captured: {len(raw_wav)} bytes, sample_rate={audio.sample_rate}, width={audio.sample_width}")
                    else:
                        logger.warning("Audio capture returned None")
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(0.3)
                        continue
                    
                finally:
                    # Safely close the context manager
                    if src is not None and source is not None:
                        try:
                            source.__exit__(None, None, None)
                        except AttributeError:
                            pass
                        except Exception as e:
                            logger.debug(f"Error closing microphone: {e}")

                
                # Try Google Speech Recognition (online)
                if self._is_online():
                    try:
                        # Enhance audio before recognition for better quality
                        enhanced = self.enhance_audio_signal(raw_wav)
                        if enhanced:
                            audio_enhanced = sr.AudioData(enhanced, audio.sample_rate, audio.sample_width)
                            audio = audio_enhanced
                            logger.info(f"   Audio enhanced ({len(enhanced)} bytes after enhancement)")
                        
                        logger.info(f"   Sending to Google STT...")
                        text = self.recognizer.recognize_google(audio, language="en-US").lower().strip()
                        if text:
                            logger.info(f"✅ Recognized (google): '{text}'")
                            return text
                        else:
                            logger.warning("❌ Google returned empty text")
                            last_error = "google_empty"
                            retry_count += 1
                            if retry_count < max_retries:
                                time.sleep(0.3)
                    except sr.UnknownValueError:
                        logger.warning("❌ Could not understand audio (google)")
                        last_error = "google_unknown"
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(0.3)
                    except sr.RequestError as e:
                        logger.error(f"❌ Google STT error: {e}")
                        last_error = f"google_request: {e}"
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(0.3)
                else:
                    logger.info("🌐 Network offline - trying PocketSphinx")
                    if not HAS_POCKETSPHINX:
                        logger.error("PocketSphinx not available. Install: pip install pocketsphinx")
                        last_error = "sphinx_not_installed"
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(0.3)
                        continue

                    try:
                        text = self.recognizer.recognize_sphinx(audio).lower().strip()
                        logger.info(f"✅ Recognized (sphinx): '{text}'")
                        return text
                    except sr.UnknownValueError:
                        logger.warning("❌ Could not understand (sphinx)")
                        last_error = "sphinx_unknown"
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(0.3)
                    except Exception as e:
                        logger.error(f"Sphinx error: {e}")
                        last_error = f"sphinx: {e}"
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(0.3)
                        
            except sr.WaitTimeoutError:
                logger.warning(f"⏱️  Timeout: no speech detected within {effective_timeout if 'effective_timeout' in locals() else timeout}s")
                last_error = "timeout"
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"   Recalibrating and retrying ({retry_count}/{max_retries})...")
                    # Recalibrate on timeout to adapt to environment
                    try:
                        mic_args = {}
                        if self.mic_index is not None:
                            mic_args["device_index"] = self.mic_index
                        with sr.Microphone(**mic_args) as src:
                            self.recognizer.adjust_for_ambient_noise(src, duration=0.5)
                            logger.info(f"   Recalibrated; threshold now: {self.recognizer.energy_threshold}")
                    except Exception as e:
                        logger.warning(f"   Recalibration failed: {e}")
                    time.sleep(0.2)
                continue
            
            except Exception as e:
                logger.error(f"❌ Microphone/Recognition error: {type(e).__name__}: {e}")
                last_error = f"error: {e}"
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"   Retrying ({retry_count}/{max_retries})...")
                    time.sleep(0.3)
                continue
        
        logger.error(f"❌ Failed to recognize speech after {max_retries} attempts. Last error: {last_error}")
        return None

    def _is_online(self, host: str = "8.8.8.8", port: int = 53, timeout: float = 1.0) -> bool:
        """Quick check for network connectivity by trying to open a socket to a public DNS."""
        import socket

        try:
            socket.setdefaulttimeout(timeout)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            sock.close()
            return True
        except Exception:
            return False
    
    def enhance_audio_signal(self, audio_data: bytes) -> Optional[bytes]:
        """
        Enhance audio signal for better recognition (normalize + optional noise reduction).
        
        Args:
            audio_data: Raw audio bytes
        
        Returns:
            Enhanced audio bytes or original if enhancement fails
        """
        try:
            if AudioSegment is None:
                return audio_data
            
            # Load audio
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format="wav")
            
            # Normalize audio (increase soft parts)
            audio = normalize(audio)
            
            # Optional: Noise reduction if noisereduce is available
            if nr is not None:
                try:
                    audio_array = np.array(audio.get_array_of_samples())
                    audio_array = nr.reduce_noise(y=audio_array, sr=audio.frame_rate)
                    audio = audio._spawn(audio_array.astype(np.int16).tobytes())
                    logger.info("Audio enhancement applied (noise reduction)")
                except Exception as e:
                    logger.warning(f"Noise reduction skipped: {e}")
            
            logger.info("Audio enhancement applied (normalization)")
            # Return raw PCM frame data for SpeechRecognition AudioData
            return audio.raw_data
            
        except Exception as e:
            logger.warning(f"Audio enhancement failed: {e}. Using original audio.")
            return audio_data


def create_processor() -> AudioProcessor:
    """Factory function to create and configure audio processor."""
    return AudioProcessor()
