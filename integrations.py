import os
import httpx
from openai import AsyncOpenAI
from typing import Optional
import json

# Environment Variables
TTS_API_URL = os.getenv("TTS_API_URL", "http://192.168.1.31:6060/v1/")
HOME_ASSISTANT_URL = os.getenv("HOME_ASSISTANT_URL", "http://homeassistant.local:8123")
HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v17.0/")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")

class TTSClient:
    def __init__(self):
        # Adjust URL for OpenAI client if needed
        base_url = TTS_API_URL
        if "/v1" not in base_url and not base_url.endswith("/"):
             base_url += "/v1"
        self.client = AsyncOpenAI(api_key="EMPTY", base_url=base_url)

    async def generate_audio(self, text: str, output_path: str, voice: str = "en-US-AvaMultilingualNeural", speed=0.85) -> Optional[str]:
        """
        Generates audio from text using OpenAI-compatible TTS endpoint.
        Saves to output_path.
        """
        try:
            print(f"Generating TTS for: {text}")
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                speed=speed,
            )
            
            response.stream_to_file(output_path)
            return output_path
        except Exception as e:
            print(f"TTS Error: {e}")
            return None

class HomeAssistantClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
            "Content-Type": "application/json",
        }
        self.base_url = HOME_ASSISTANT_URL.rstrip('/')

    async def announce(self, message: str, media_url: Optional[str] = None):
        """
        Sends a notification or plays a media file on Home Assistant.
        For now, we'll assume a generic 'notify' service or 'media_player'.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Example: Send a text notification
                payload = {"message": message}
                url = f"{self.base_url}/api/services/notify/persistent_notification" # Adjust service as needed
                
                print(f"Sending HA notification: {message}")
                resp = await client.post(url, headers=self.headers, json=payload)
                resp.raise_for_status()
                
                # If functionality for playing audio is needed
                # url = f"{self.base_url}/api/services/media_player/play_media"
                # payload = {
                #     "entity_id": "all",
                #     "media_content_id": media_url,
                #     "media_content_type": "music"
                # }
                # await client.post(url, headers=self.headers, json=payload)
                
        except Exception as e:
            print(f"Home Assistant Error: {e}")

    async def play_audio(self, audio_url: str, entity_id: str = "media_player.living_room_speaker"):
        """
        Plays audio from a URL on a specific media player.
        """
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/api/services/media_player/play_media"
                payload = {
                    "entity_id": entity_id,
                    "media_content_id": audio_url,
                    "media_content_type": "music"
                }
                print(f"Playing audio on HA: {audio_url}")
                resp = await client.post(url, headers=self.headers, json=payload)
                resp.raise_for_status()
        except Exception as e:
            print(f"Home Assistant Audio Error: {e}")


class WhatsAppClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        }
        self.url = WHATSAPP_API_URL 

    async def send_message(self, to_number: str, message: str):
        """
        Sends a WhatsApp message.
        """
        if not WHATSAPP_TOKEN or "replace_me" in WHATSAPP_TOKEN:
            print("WhatsApp token not configured, skipping.")
            return

        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to_number,
                    "type": "text",
                    "text": {"body": message}
                }
                # Ensure URL is correct for sending messages (usually includes phone number ID)
                # Assuming WHATSAPP_API_URL includes the phone ID: e.g. https://graph.facebook.com/v17.0/PHONE_NUMBER_ID/messages
                # If not, we might need to adjust.
                
                print(f"Sending WhatsApp to {to_number}: {message}")
                resp = await client.post(self.url, headers=self.headers, json=payload)
                resp.raise_for_status()
        except Exception as e:
            print(f"WhatsApp Error: {e}")
