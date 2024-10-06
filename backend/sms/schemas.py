"""
Pydantic schemas for SMS API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from backend.sms.models import SMSStatus, SMSType, ResponseSentiment


# === SMS Message Schemas ===

class SendSMSRequest(BaseModel):
    """Request to send an SMS message."""
    to_number: str = Field(..., description="Recipient phone number")
    message_body: str = Field(..., description="Message content")
    message_type: SMSType = Field(default=SMSType.FOLLOWUP, description="Type of SMS")
    related_call_id: Optional[int] = Field(None, description="Related call ID")
    related_lead_id: Optional[int] = Field(None, description="Related lead ID")
    campaign_id: Optional[int] = Field(None, description="Campaign ID")


class SMSMessageResponse(BaseModel):
    """SMS message response."""
    id: int
    sms_sid: str
    message_type: SMSType
    from_number: str
    to_number: str
    message_body: str
    status: SMSStatus
    related_call_id: Optional[int]
    related_lead_id: Optional[int]
    campaign_id: Optional[int]
    cost: Optional[float]
    segments: int
    sent_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


# === SMS Response Schemas ===

class SMSResponseData(BaseModel):
    """SMS response data."""
    id: int
    message_sid: str
    original_message_id: int
    from_number: str
    to_number: str
    response_body: str
    sentiment: Optional[ResponseSentiment]
    confidence_score: Optional[float]
    intent: Optional[str]
    keywords: Optional[str]
    received_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


class InboundSMSWebhook(BaseModel):
    """Twilio inbound SMS webhook payload."""
    MessageSid: str
    AccountSid: str
    From: str
    To: str
    Body: str
    NumMedia: int = 0
    MessageStatus: str = "received"


class SMSStatusWebhook(BaseModel):
    """Twilio SMS status callback payload."""
    MessageSid: str
    AccountSid: str
    From: str
    To: str
    SmsSid: str
    SmsStatus: str  # sent, delivered, failed, undelivered
    MessageStatus: str


# === SMS Campaign Schemas ===

class CreateSMSCampaignRequest(BaseModel):
    """Request to create SMS campaign."""
    name: str = Field(..., description="Campaign name")
    description: Optional[str] = Field(None, description="Campaign description")
    message_template: str = Field(..., description="Message template")
    trigger_event: str = Field(..., description="Event triggering SMS (call_completed, etc.)")
    delay_seconds: int = Field(default=300, description="Delay before sending SMS")


class SMSCampaignResponse(BaseModel):
    """SMS campaign response."""
    id: int
    name: str
    description: Optional[str]
    message_template: str
    trigger_event: str
    delay_seconds: int
    total_sent: int
    total_delivered: int
    total_responses: int
    response_rate: float
    active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UpdateSMSCampaignRequest(BaseModel):
    """Request to update SMS campaign."""
    name: Optional[str] = None
    description: Optional[str] = None
    message_template: Optional[str] = None
    trigger_event: Optional[str] = None
    delay_seconds: Optional[int] = None
    active: Optional[bool] = None


# === Correlation Schemas ===

class CallSMSCorrelationResponse(BaseModel):
    """Call-SMS correlation data."""
    id: int
    call_id: int
    sms_message_id: int
    sms_response_id: Optional[int]
    lead_id: int
    call_to_sms_delay_seconds: int
    response_time_seconds: Optional[int]
    conversion: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# === Analytics Schemas ===

class SMSAnalyticsResponse(BaseModel):
    """SMS analytics response."""
    period_days: int
    total_sent: int
    total_delivered: int
    total_failed: int
    total_responses: int
    response_rate_percent: float
    positive_responses: int
    negative_responses: int
    neutral_responses: int


class DailySMSAnalyticsResponse(BaseModel):
    """Daily SMS analytics."""
    id: int
    date: datetime
    total_sent: int
    total_delivered: int
    total_failed: int
    total_responses: int
    response_rate: float
    positive_responses: int
    negative_responses: int
    neutral_responses: int
    conversions: int
    conversion_rate: float
    total_cost: float
    created_at: datetime
    
    class Config:
        from_attributes = True


# === Schedule Follow-up Schemas ===

class ScheduleFollowupRequest(BaseModel):
    """Request to schedule SMS follow-up after call."""
    call_id: int = Field(..., description="Call ID")
    lead_id: int = Field(..., description="Lead ID")
    to_number: str = Field(..., description="Recipient phone number")
    message_template: str = Field(..., description="Message template")
    delay_seconds: int = Field(default=300, description="Delay before sending")


class ScheduleFollowupResponse(BaseModel):
    """Response to schedule follow-up."""
    success: bool
    message: str
    correlation_id: Optional[int] = None


# === Batch Operations ===

class BulkSendSMSRequest(BaseModel):
    """Request to send SMS to multiple recipients."""
    recipients: List[SendSMSRequest]
    campaign_id: Optional[int] = None


class BulkSendSMSResponse(BaseModel):
    """Response from bulk SMS sending."""
    total_requested: int
    total_sent: int
    total_failed: int
    failed_recipients: List[str] = []
    campaign_id: Optional[int]


# === Reporting ===

class SMSConversationResponse(BaseModel):
    """Full SMS conversation thread."""
    call_id: int
    lead_id: int
    lead_phone: str
    messages: List[SMSMessageResponse]
    responses: List[SMSResponseData]
    overall_sentiment: Optional[ResponseSentiment]
    conversion: bool
    created_at: datetime


class SMSReportResponse(BaseModel):
    """SMS report with aggregations."""
    report_date: datetime
    total_messages_sent: int
    total_responses: int
    response_rate: float
    average_response_time_seconds: Optional[int]
    conversion_rate: float
    sentiment_breakdown: dict
    top_intents: List[tuple]
    campaign_performance: List[dict]
