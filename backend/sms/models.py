"""
SMS Follow-up Database Models - SMS messages, responses, correlations.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Enum as SQLEnum, Float
from sqlalchemy.sql import func
from datetime import datetime
import enum
from backend.database import Base


class SMSStatus(str, enum.Enum):
    """SMS message status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


class SMSType(str, enum.Enum):
    """SMS type classification."""
    FOLLOWUP = "followup"
    REMINDER = "reminder"
    CONFIRMATION = "confirmation"
    FEEDBACK = "feedback"


class ResponseSentiment(str, enum.Enum):
    """SMS response sentiment."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"


class SMSMessage(Base):
    """Outbound SMS message."""
    __tablename__ = "sms_messages"

    id = Column(Integer, primary_key=True, index=True)
    
    # Identification
    sms_sid = Column(String(100), unique=True, index=True, nullable=False)  # Twilio SID
    message_type = Column(SQLEnum(SMSType), nullable=False)
    
    # Recipients
    from_number = Column(String(20), nullable=False)
    to_number = Column(String(20), nullable=False, index=True)
    
    # Content
    message_body = Column(Text, nullable=False)
    
    # Status
    status = Column(SQLEnum(SMSStatus), default=SMSStatus.PENDING, index=True)
    
    # Correlation
    related_call_id = Column(Integer, nullable=True, index=True)  # Link to call
    related_lead_id = Column(Integer, nullable=True, index=True)  # Link to lead
    campaign_id = Column(Integer, nullable=True, index=True)  # Link to campaign
    
    # Metadata
    cost = Column(Float, nullable=True)
    segments = Column(Integer, default=1)
    
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SMSMessage(sid={self.sms_sid}, to={self.to_number}, status={self.status})>"


class SMSResponse(Base):
    """Inbound SMS response."""
    __tablename__ = "sms_responses"

    id = Column(Integer, primary_key=True, index=True)
    
    # Identification
    message_sid = Column(String(100), unique=True, index=True, nullable=False)  # Twilio SID
    
    # Link to original message
    original_message_id = Column(Integer, nullable=False, index=True)
    
    # Response details
    from_number = Column(String(20), nullable=False)
    to_number = Column(String(20), nullable=False)
    response_body = Column(Text, nullable=False)
    
    # Analysis
    sentiment = Column(SQLEnum(ResponseSentiment), nullable=True)
    confidence_score = Column(Float, nullable=True)  # 0-1
    
    # Intent extraction
    intent = Column(String(100), nullable=True)  # "interested", "callback", "unsubscribe", etc.
    keywords = Column(Text, nullable=True)  # Comma-separated
    
    received_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<SMSResponse(sid={self.message_sid}, sentiment={self.sentiment})>"


class SMSCampaign(Base):
    """SMS follow-up campaign."""
    __tablename__ = "sms_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    
    # Campaign info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Template
    message_template = Column(Text, nullable=False)
    
    # Configuration
    trigger_event = Column(String(50), nullable=False)  # "call_completed", "call_duration", etc.
    delay_seconds = Column(Integer, default=300)  # Send SMS after call ends
    
    # Tracking
    total_sent = Column(Integer, default=0)
    total_delivered = Column(Integer, default=0)
    total_responses = Column(Integer, default=0)
    response_rate = Column(Float, default=0.0)
    
    active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SMSCampaign(name={self.name}, sent={self.total_sent})>"


class CallSMSCorrelation(Base):
    """Correlation between calls and SMS messages."""
    __tablename__ = "call_sms_correlation"

    id = Column(Integer, primary_key=True, index=True)
    
    # Correlation
    call_id = Column(Integer, nullable=False, index=True)
    sms_message_id = Column(Integer, nullable=False, index=True)
    sms_response_id = Column(Integer, nullable=True, index=True)
    
    # Lead tracking
    lead_id = Column(Integer, nullable=False, index=True)
    
    # Metrics
    call_to_sms_delay_seconds = Column(Integer)  # Time between call end and SMS send
    response_time_seconds = Column(Integer, nullable=True)  # Time to respond to SMS
    conversion = Column(Boolean, default=False)  # Did SMS lead to conversion?
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<CallSMSCorrelation(call_id={self.call_id}, lead_id={self.lead_id})>"


class SMSAnalytics(Base):
    """Daily SMS analytics."""
    __tablename__ = "sms_analytics"

    id = Column(Integer, primary_key=True, index=True)
    
    date = Column(DateTime, index=True, nullable=False)
    
    # Volume
    total_sent = Column(Integer, default=0)
    total_delivered = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    
    # Responses
    total_responses = Column(Integer, default=0)
    response_rate = Column(Float, default=0.0)
    
    # Sentiment
    positive_responses = Column(Integer, default=0)
    negative_responses = Column(Integer, default=0)
    neutral_responses = Column(Integer, default=0)
    
    # Conversion
    conversions = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    
    # Cost
    total_cost = Column(Float, default=0.0)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<SMSAnalytics(date={self.date}, sent={self.total_sent})>"
