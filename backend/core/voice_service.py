"""
Voice Service - Manages ElevenLabs text-to-speech integration.
"""

import os
from typing import Optional
import httpx
from enum import Enum


class VoicePreset(str, Enum):
    """Available voice presets."""
    PROFESSIONAL_MALE = "EXAVITQu4vr4xnSDxMaL"      # Mature male
    PROFESSIONAL_FEMALE = "EXAVITQu4vr4xnSDxMaL"   # Professional female
    FRIENDLY_MALE = "pNInz6obpgDQGcFmaJgB"         # Young male
    FRIENDLY_FEMALE = "EXAVITQu4vr4xnSDxMaL"       # Young female
    SUPPORT_AGENT = "9BWtsMINqrJLrRacOk9x"         # Customer support tone


class VoiceService:
    """
    Service for text-to-speech using ElevenLabs API.
    Generates natural-sounding voice responses for agents.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize voice service.
        
        Args:
            api_key: ElevenLabs API key (defaults to env variable)
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1"
        self.client = httpx.AsyncClient()

    async def synthesize(
        self,
        text: str,
        voice_id: str = VoicePreset.PROFESSIONAL_MALE,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
    ) -> bytes:
        """
        Convert text to speech audio.
        
        Args:
            text: Text to synthesize
            voice_id: Voice ID to use
            stability: Voice stability (0-1)
            similarity_boost: Similarity to voice (0-1)
            
        Returns:
            Audio bytes (MP3)
        """
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
            },
        }
        
        response = await self.client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        return response.content

    async def synthesize_streaming(
        self,
        text: str,
        voice_id: str = VoicePreset.PROFESSIONAL_MALE,
    ):
        """
        Stream text-to-speech audio for real-time playback.
        
        Args:
            text: Text to synthesize
            voice_id: Voice ID to use
            
        Yields:
            Audio chunks
        """
        url = f"{self.base_url}/text-to-speech/{voice_id}/stream"
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }
        
        async with self.client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk

    async def get_voices(self) -> list:
        """
        Get available voices.
        
        Returns:
            List of available voice objects
        """
        url = f"{self.base_url}/voices"
        headers = {"xi-api-key": self.api_key}
        
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        return data.get("voices", [])

    async def get_voice_settings(self, voice_id: str) -> dict:
        """
        Get settings for a specific voice.
        
        Args:
            voice_id: Voice ID
            
        Returns:
            Voice settings
        """
        url = f"{self.base_url}/voices/{voice_id}/settings"
        headers = {"xi-api-key": self.api_key}
        
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
