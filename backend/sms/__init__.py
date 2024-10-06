"""
SMS Follow-up System - VoiceFlow
Auto-send SMS after calls, classify responses, and correlate with calls.
"""

from backend.sms.models import (
    SMSMessage,
    SMSResponse,
    SMSCampaign,
    CallSMSCorrelation,
    SMSAnalytics,
    SMSStatus,
    SMSType,
    ResponseSentiment,
)
from backend.sms.sms_service import SMSService
from backend.sms import schemas

__all__ = [
    "SMSMessage",
    "SMSResponse",
    "SMSCampaign",
    "CallSMSCorrelation",
    "SMSAnalytics",
    "SMSStatus",
    "SMSType",
    "ResponseSentiment",
    "SMSService",
    "schemas",
]
