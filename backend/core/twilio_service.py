"""
Twilio Service - Manages Twilio API integration for call handling.
"""

import os
from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse


class TwilioService:
    """
    Service for managing Twilio voice calls.
    Handles inbound/outbound calls, call routing, and transcription.
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        phone_number: Optional[str] = None,
    ):
        """
        Initialize Twilio service.
        
        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            phone_number: Twilio phone number for outbound calls
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = phone_number or os.getenv("TWILIO_PHONE_NUMBER")
        
        self.client = Client(self.account_sid, self.auth_token)

    def create_inbound_response(
        self,
        message: str = None,
        gather_input: bool = False,
        num_digits: int = 1,
    ) -> str:
        """
        Create TwiML response for inbound call.
        
        Args:
            message: Message to say to caller
            gather_input: Whether to gather DTMF input
            num_digits: Number of digits to gather
            
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        if message:
            response.say(message, voice="Alice")
        
        if gather_input:
            response.gather(
                num_digits=num_digits,
                action="/webhook/handle-input",
                method="POST",
            )
        
        return str(response)

    def make_outbound_call(
        self,
        to_number: str,
        webhook_url: str,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Initiate outbound call.
        
        Args:
            to_number: Recipient phone number
            webhook_url: URL to call when call is answered
            custom_data: Custom data to pass to webhook
            
        Returns:
            Call SID
        """
        # Add custom data to URL if provided
        if custom_data:
            params = "&".join(f"{k}={v}" for k, v in custom_data.items())
            webhook_url = f"{webhook_url}?{params}"
        
        call = self.client.calls.create(
            to=to_number,
            from_=self.phone_number,
            url=webhook_url,
            record=True,
            recording_status_callback="/webhook/recording-complete",
        )
        
        return call.sid

    def get_call(self, call_sid: str) -> Dict[str, Any]:
        """
        Get call details.
        
        Args:
            call_sid: Call SID
            
        Returns:
            Call information
        """
        call = self.client.calls(call_sid).fetch()
        
        return {
            "sid": call.sid,
            "from": call.from_,
            "to": call.to,
            "status": call.status,
            "duration": call.duration,
            "price": call.price,
            "date_created": call.date_created,
            "date_updated": call.date_updated,
        }

    def get_call_recording(self, call_sid: str) -> Optional[str]:
        """
        Get recording URL for a call.
        
        Args:
            call_sid: Call SID
            
        Returns:
            Recording URL or None if not found
        """
        recordings = self.client.calls(call_sid).recordings.list()
        
        if recordings:
            return recordings[0].uri
        
        return None

    def get_call_transcription(self, recording_sid: str) -> Optional[str]:
        """
        Get transcription of a call recording.
        
        Args:
            recording_sid: Recording SID
            
        Returns:
            Transcription text or None
        """
        try:
            transcriptions = self.client.recordings(recording_sid).transcriptions.list()
            
            if transcriptions:
                return transcriptions[0].text
        except Exception:
            pass
        
        return None

    def hang_up_call(self, call_sid: str) -> bool:
        """
        Hang up a call.
        
        Args:
            call_sid: Call SID
            
        Returns:
            True if successful
        """
        try:
            call = self.client.calls(call_sid).update(status="completed")
            return call.status == "completed"
        except Exception:
            return False

    def transfer_call(self, call_sid: str, transfer_to: str) -> str:
        """
        Transfer an active call to another number.
        
        Args:
            call_sid: Call SID
            transfer_to: Number to transfer to
            
        Returns:
            TwiML response
        """
        response = VoiceResponse()
        response.dial(transfer_to)
        
        return str(response)

    def validate_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Validate phone number format and carrier.
        
        Args:
            phone_number: Phone number to validate
            
        Returns:
            Validation results
        """
        try:
            lookup = self.client.lookups.v1.phone_numbers(phone_number).fetch(
                type="carrier"
            )
            
            return {
                "valid": True,
                "carrier": lookup.carrier.get("name"),
                "type": lookup.carrier.get("type"),
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}
