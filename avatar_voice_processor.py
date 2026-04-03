#!/usr/bin/env python3
"""
Real-time voice interaction with Jimmy avatar using Voice Activity Detection (VAD)
Automatically transcribes audio when speech ends, gets Jimmy's response, and generates TTS
"""

import io
import wave
import base64
import asyncio
from typing import Tuple, Optional
import numpy as np
from language_utils import DEFAULT_JIMMY_LANGUAGE, detect_supported_language, normalize_supported_language

# Try to import WebRTC VAD for voice activity detection
try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    print("[WARNING] webrtcvad not installed - using simple energy-based voice detection")


class VoiceActivityDetector:
    """
    Detects voice activity in audio using WebRTC VAD or simple energy threshold.
    When silence is detected, signals that transcription should happen.
    """
    
    def __init__(self, sample_rate: int = 16000, vad_mode: int = 1):
        """
        Args:
            sample_rate: Audio sample rate (16000 Hz expected)
            vad_mode: WebRTC VAD mode (0-3, higher = less sensitive)
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = 20  # WebRTC VAD requires 10, 20, or 30ms frames
        self.frame_size = int(sample_rate * self.frame_duration_ms / 1000)
        
        if VAD_AVAILABLE:
            self.vad = webrtcvad.Vad(vad_mode)
        else:
            self.vad = None
        
        # Energy-based fallback parameters
        self.silence_threshold = 500  # Energy threshold for silence
        self.silence_duration_ms = 800  # 800ms of silence = end of speech
        self.silence_frames_needed = int(self.silence_duration_ms / self.frame_duration_ms)
        self.consecutive_silence_frames = 0
    
    def is_speech(self, audio_chunk: bytes) -> bool:
        """
        Detect if audio chunk contains speech.
        
        Args:
            audio_chunk: Audio data (bytes)
        
        Returns:
            True if speech detected, False if silence
        """
        if VAD_AVAILABLE:
            try:
                return self.vad.is_speech(audio_chunk, self.sample_rate)
            except Exception:
                return False
        else:
            # Fallback: energy-based detection
            audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
            energy = np.sum(audio_data ** 2) / len(audio_data) if len(audio_data) > 0 else 0
            return energy > self.silence_threshold
    
    def update_silence(self, is_speech: bool) -> bool:
        """
        Update silence counter and return True when speech has ended (silence detected).
        
        Args:
            is_speech: Whether current frame contains speech
        
        Returns:
            True if speech has clearly ended (silence detected), False otherwise
        """
        if is_speech:
            self.consecutive_silence_frames = 0
            return False
        else:
            self.consecutive_silence_frames += 1
            # Return True when enough silence accumulated
            return self.consecutive_silence_frames >= self.silence_frames_needed
    
    def reset(self):
        """Reset silence counter for next speaker."""
        self.consecutive_silence_frames = 0


class AudioBuffer:
    """Buffers audio chunks and provides WAV encoding."""
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_chunks = []
    
    def add_chunk(self, chunk: bytes):
        """Add audio chunk to buffer."""
        self.audio_chunks.append(chunk)
    
    def get_wav(self) -> bytes:
        """Get buffered audio as WAV file."""
        if not self.audio_chunks:
            return b''
        
        # Combine chunks
        audio_data = b''.join(self.audio_chunks)
        
        # Create WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data)
        
        return wav_buffer.getvalue()
    
    def reset(self):
        """Clear buffer for next audio stream."""
        self.audio_chunks = []
    
    def get_audio_bytes(self) -> bytes:
        """Get raw audio bytes."""
        return b''.join(self.audio_chunks)


def process_avatar_audio_stream(
    audio_base64: str,
    patient_id: int,
    language: str = "English",
    history: list = None
) -> Tuple[str, Optional[str], str, str]:
    """
    Process audio stream for avatar interaction:
    1. Detect voice activity
    2. Transcribe when speech ends
    3. Get Jimmy response
    4. Generate TTS audio
    
    Args:
        audio_base64: Base64-encoded audio (16-bit, 16kHz PCM)
        patient_id: Patient ID for context
        language: Preferred language
        history: Conversation history
    
    Returns:
        (transcribed_text, jimmy_response, audio_b64_or_error, detected_language)
    """
    
    try:
        requested_language = normalize_supported_language(language)

        # Decode audio
        audio_bytes = base64.b64decode(audio_base64)
        
        # Initialize VAD and buffer
        vad = VoiceActivityDetector(sample_rate=16000, vad_mode=1)
        audio_buffer = AudioBuffer(sample_rate=16000, channels=1)
        
        # Process audio in chunks
        frame_size = vad.frame_size * 2  # 2 bytes per sample (16-bit)
        speech_detected = False
        speech_ended = False
        
        for i in range(0, len(audio_bytes), frame_size):
            chunk = audio_bytes[i:i + frame_size]
            if len(chunk) < frame_size:
                # Pad last chunk if needed
                chunk = chunk + b'\x00' * (frame_size - len(chunk))
            
            # Check for speech
            is_speech = vad.is_speech(chunk)
            
            if is_speech:
                speech_detected = True
                audio_buffer.add_chunk(chunk)
            else:
                if speech_detected:
                    # Speech was detected before, now we have silence
                    if vad.update_silence(False):
                        speech_ended = True
                        break
                audio_buffer.add_chunk(chunk)  # Still buffer silence in case they just pause
        
        if not speech_detected:
            return "", None, "No speech detected", requested_language
        
        # Transcribe
        from whisper_transcriber import transcribe
        wav_audio = audio_buffer.get_wav()
        transcribed_text = transcribe(wav_audio)
        
        if not transcribed_text or transcribed_text.strip() == "":
            return "", None, "Could not transcribe audio", requested_language

        detected_language = detect_supported_language(
            transcribed_text,
            hint=requested_language,
        )
        
        # Get Jimmy response
        from meralion_avatar import get_avatar
        avatar = get_avatar()
        
        if history is None:
            history = []
        
        jimmy_response = avatar.query_jimmy(
            patient_id=patient_id,
            user_message=transcribed_text,
            conversation_history=history,
            include_rag=True,
            include_performance=True,
            preferred_language=detected_language
        )
        
        # Generate TTS audio response (inline to avoid circular imports)
        import asyncio
        import hashlib
        import tempfile
        import os
        import base64
        
        try:
            import edge_tts
            
            # Generate voice audio using edge-tts
            sample_rate_hz = 16000
            h = hashlib.md5(f"edge|{detected_language}|{jimmy_response}".encode("utf-8")).hexdigest()
            cache_dir = os.path.join(tempfile.gettempdir(), "avatar_tts_cache")
            os.makedirs(cache_dir, exist_ok=True)
            mp3_path = os.path.join(cache_dir, f"{h}.mp3")
            
            if os.path.exists(mp3_path):
                with open(mp3_path, 'rb') as f:
                    audio_response_b64 = base64.b64encode(f.read()).decode()
            else:
                # Map language to voice
                voice_map = {
                    "English": "en-US-AriaNeural",
                    "Chinese": "zh-CN-XiaoxiaoNeural",
                    "Malay": "ms-MY-OsmanNeural",
                    "Tamil": "ta-IN-PallaviNeural",
                    "Singlish": "en-SG-LunaNeural"
                }
                voice = voice_map.get(detected_language, "en-US-AriaNeural")
                
                communicate = edge_tts.Communicate(text=jimmy_response, voice=voice)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(communicate.save(mp3_path))
                loop.close()
                
                with open(mp3_path, 'rb') as f:
                    audio_response_b64 = base64.b64encode(f.read()).decode()
        except Exception as tts_err:
            print(f"[AVATAR-VOICE] TTS failed: {tts_err}")
            audio_response_b64 = ""
        
        return transcribed_text, jimmy_response, audio_response_b64, detected_language
    
    except Exception as e:
        print(f"[AVATAR-VOICE] Error processing audio: {e}")
        import traceback
        traceback.print_exc()
        return "", None, f"Error: {str(e)}", DEFAULT_JIMMY_LANGUAGE


if __name__ == "__main__":
    # Test VAD availability
    print(f"[VAD] WebRTC VAD available: {VAD_AVAILABLE}")
    
    # Test simple audio processing
    import numpy as np
    
    # Create test audio with speech (high energy) followed by silence
    sample_rate = 16000
    duration = 2  # 2 seconds
    
    # First second: speech (440 Hz tone)
    t1 = np.linspace(0, 1, sample_rate)
    speech = (np.sin(2 * np.pi * 440 * t1) * 10000).astype(np.int16)
    
    # Second second: silence
    silence = np.zeros(sample_rate, dtype=np.int16)
    
    # Combine and encode
    audio_combined = np.concatenate([speech, silence]).tobytes()
    audio_b64 = base64.b64encode(audio_combined).decode()
    
    # Test processing (would fail without proper Flask context)
    print("[TEST] Audio processing function ready for Flask integration")
