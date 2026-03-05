"""
Audio Service for DIA (Digital Intelligent Assistant)
Handles speech-to-text and text-to-speech functionality
"""
import io
import os
import time
import wave
import pyaudio
import audioop
import requests
import pyttsx3
from typing import Optional

from config import (
    SILENCE_THRESHOLD, SILENCE_DURATION, API_URL, 
    SPEECH_RATE, get_openai_api_key
)


class AudioService:
    """Service for handling audio input/output operations"""
    
    def __init__(self, mic_index: int = 1):
        self.mic_index = mic_index
        self.engine = self._setup_tts_engine()
        
    def _setup_tts_engine(self):
        """Initialize and configure the TTS engine"""
        engine = pyttsx3.init()
        engine.setProperty('rate', SPEECH_RATE)
        
        # Try to set Italian voice if available
        voices = engine.getProperty('voices')
        italian_voice = None
        
        for voice in voices:
            if "italian" in voice.name.lower() or "ita" in voice.id.lower():
                italian_voice = voice.id
                break
        
        if italian_voice:
            engine.setProperty('voice', italian_voice)
        
        return engine
    
    def list_microphones(self) -> None:
        """List all available microphones"""
        p = pyaudio.PyAudio()
        print("Available microphones:")
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            if device_info["maxInputChannels"] > 0:
                print(f"Index {i}: {device_info['name']}")
        p.terminate()
    
    def select_microphone(self) -> int:
        """Ask user to select a microphone by index"""
        self.list_microphones()
        mic_index = int(input("Enter the index of the microphone you want to use: "))
        return mic_index
    
    def text_to_audio(self, text: str, rate: int = SPEECH_RATE) -> float:
        """
        Convert text to speech and play it
        
        Args:
            text (str): The text to convert to speech
            rate (int): Speech rate - higher values = faster speech
        
        Returns:
            float: Start time of the response for metrics tracking
        """
        start_time = time.time()
        
        # Set the speech rate
        self.engine.setProperty('rate', rate)
        
        # Convert and play
        self.engine.say(text)
        self.engine.runAndWait()
        
        return start_time
    
    def record_audio(self) -> bytes:
        """
        Record audio from the selected microphone and return it as raw audio bytes.
        Stops recording on silence.
        
        Returns:
            bytes: Raw audio data
        """
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            input_device_index=self.mic_index,
            frames_per_buffer=1024
        )
        
        device_name = p.get_device_info_by_index(self.mic_index)['name']
        print(f"Recording from {device_name}...")
        
        frames = []
        silence_count = 0
        
        while True:
            data = stream.read(1024)
            frames.append(data)
            rms = audioop.rms(data, 2)
            
            if rms < SILENCE_THRESHOLD:
                silence_count += 1
            else:
                silence_count = 0
            
            if silence_count > (SILENCE_DURATION * 16000 / 1024):
                print("Silence detected. Stopping recording.")
                break
        
        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Return the raw audio data
        audio_data = b"".join(frames)
        return audio_data
    
    def convert_to_wav(self, audio_data: bytes) -> io.BytesIO:
        """
        Convert raw audio data to a valid WAV file-like object.
        
        Args:
            audio_data (bytes): Raw audio data
            
        Returns:
            io.BytesIO: WAV buffer
        """
        wav_buffer = io.BytesIO()
        
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 2 bytes for 16-bit audio
            wf.setframerate(16000)
            wf.writeframes(audio_data)
        
        wav_buffer.seek(0)
        return wav_buffer
    
    def transcribe_audio_with_whisper(self, audio_data: bytes) -> str:
        """
        Send raw audio data to Whisper API for transcription
        
        Args:
            audio_data (bytes): Raw audio data
            
        Returns:
            str: Transcribed text
        """
        headers = {
            "Authorization": f"Bearer {get_openai_api_key()}",
        }
        
        # Convert the raw audio data to WAV format in memory
        wav_audio = self.convert_to_wav(audio_data)
        
        # Send the audio file to Whisper for transcription
        response = requests.post(
            API_URL,
            headers=headers,
            files={"file": ("audio.wav", wav_audio, "audio/wav")},
            data={"model": "whisper-1", "language": "it"}
        )
        
        if response.status_code == 200:
            return response.json()["text"]
        else:
            raise Exception(f"Error: {response.status_code}, {response.text}")
    
    def audio_transcription(self) -> str:
        """
        Complete audio transcription workflow
        
        Returns:
            str: Transcribed text
        """
        # Record audio
        audio_data = self.record_audio()
        
        # Transcribe audio using Whisper API
        print("Transcribing audio using Whisper...")
        transcription = self.transcribe_audio_with_whisper(audio_data)
        
        if transcription:
            print("You said:", transcription)
            return transcription
        
        return ""
    
    def wait_for_speech(self) -> tuple[float, str]:
        """
        Wait for user speech input
        
        Returns:
            tuple: (start_time, transcribed_text)
        """
        input("Premi INVIO per parlare...")
        start_time = time.time()
        transcription = self.audio_transcription()
        return start_time, transcription.strip().lower()


# Utility function for backward compatibility
def get_audio_service(mic_index: int = 1) -> AudioService:
    """Get an AudioService instance"""
    return AudioService(mic_index)
