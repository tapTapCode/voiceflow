"""
Inbound Agent Database Models - Call records, customer data, support tickets.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum, Text, Boolean
from sqlalchemy.sql import func
from datetime import datetime
import enum
from backend.database import Base


class CallStatus(str, enum.Enum):
    """Call status types."""
    INCOMING = "incoming"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class SentimentType(str, enum.Enum):
    """Sentiment classification."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ResolutionStatus(str, enum.Enum):
    """Support ticket resolution status."""
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    PENDING_FOLLOWUP = "pending_followup"


class Customer(Base):
    """Customer information."""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    customer_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Customer(phone={self.phone_number}, name={self.name})>"


class InboundCall(Base):
    """Inbound call record."""
    __tablename__ = "inbound_calls"

    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(100), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, nullable=True, index=True)
    from_number = Column(String(20), nullable=False)
    to_number = Column(String(20), nullable=False)
    status = Column(SQLEnum(CallStatus), default=CallStatus.INCOMING, index=True)
    duration_seconds = Column(Integer, default=0)
    
    # Sentiment and analysis
    sentiment = Column(SQLEnum(SentimentType), default=SentimentType.NEUTRAL)
    sentiment_score = Column(Float, default=0.5)  # 0-1
    
    # Recording and transcript
    recording_url = Column(String(500), nullable=True)
    transcript = Column(Text, nullable=True)
    
    # Escalation
    escalated = Column(Boolean, default=False)
    escalation_reason = Column(String(500), nullable=True)
    escalated_to_agent = Column(String(255), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<InboundCall(sid={self.call_sid}, status={self.status}, sentiment={self.sentiment})>"


class SupportTicket(Base):
    """Support ticket from call."""
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, nullable=False, index=True)
    customer_id = Column(Integer, nullable=False, index=True)
    issue_type = Column(String(100), nullable=True)
    issue_description = Column(Text, nullable=True)
    resolution_status = Column(SQLEnum(ResolutionStatus), default=ResolutionStatus.UNRESOLVED)
    
    # Resolution details
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(String(255), nullable=True)
    resolution_time_seconds = Column(Integer, nullable=True)
    
    # Satisfaction
    csat_score = Column(Integer, nullable=True)  # 1-5
    feedback = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<SupportTicket(call_id={self.call_id}, status={self.resolution_status})>"


class CallTranscript(Base):
    """Detailed call transcript with timestamps."""
    __tablename__ = "call_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, nullable=False, index=True)
    speaker = Column(String(20), nullable=False)  # "customer" or "agent"
    text = Column(Text, nullable=False)
    timestamp = Column(Integer, nullable=False)  # Seconds from call start
    sentiment = Column(SQLEnum(SentimentType), nullable=True)
    confidence = Column(Float, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<CallTranscript(call_id={self.call_id}, speaker={self.speaker})>"


class CallMetric(Base):
    """Aggregated call metrics for analytics."""
    __tablename__ = "call_metrics"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, index=True, nullable=False)
    
    # Count metrics
    total_calls = Column(Integer, default=0)
    completed_calls = Column(Integer, default=0)
    escalated_calls = Column(Integer, default=0)
    failed_calls = Column(Integer, default=0)
    
    # Duration metrics
    avg_duration_seconds = Column(Float, default=0)
    min_duration_seconds = Column(Integer, default=0)
    max_duration_seconds = Column(Integer, default=0)
    
    # Sentiment metrics
    positive_sentiment_count = Column(Integer, default=0)
    neutral_sentiment_count = Column(Integer, default=0)
    negative_sentiment_count = Column(Integer, default=0)
    
    # Resolution metrics
    resolution_rate = Column(Float, default=0)  # 0-1
    avg_csat_score = Column(Float, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<CallMetric(date={self.date}, total_calls={self.total_calls})>"
