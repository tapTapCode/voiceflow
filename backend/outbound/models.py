"""
Outbound Agent Database Models - Campaigns, leads, call logs, qualification results.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum, Text, Boolean, JSON
from sqlalchemy.sql import func
from datetime import datetime
import enum
from backend.database import Base


class CampaignStatus(str, enum.Enum):
    """Campaign status types."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class LeadStatus(str, enum.Enum):
    """Lead status in campaign."""
    PENDING = "pending"
    CALLING = "calling"
    CONTACTED = "contacted"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    CALLBACK = "callback"
    DUPLICATE = "duplicate"


class QualificationStatus(str, enum.Enum):
    """Lead qualification result."""
    HOT = "hot"           # Immediate buyer
    WARM = "warm"         # Interested, needs nurturing
    COLD = "cold"         # Not interested
    PENDING = "pending"   # Needs follow-up
    DISQUALIFIED = "disqualified"


class Campaign(Base):
    """Lead generation campaign."""
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT, index=True)
    
    # Campaign parameters
    script_template = Column(Text, nullable=False)  # Opening script
    qualification_questions = Column(JSON, nullable=True)  # Questions to ask
    target_lead_count = Column(Integer, default=0)
    calls_per_day_limit = Column(Integer, default=50)
    
    # Scheduling
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    call_start_hour = Column(Integer, default=9)   # 9 AM
    call_end_hour = Column(Integer, default=17)    # 5 PM
    
    # Results
    total_leads = Column(Integer, default=0)
    leads_contacted = Column(Integer, default=0)
    leads_qualified = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    avg_call_duration = Column(Integer, default=0)
    
    # Metadata
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Campaign(name={self.name}, status={self.status}, leads={self.total_leads})>"


class Lead(Base):
    """Lead for outbound campaign."""
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    
    # Lead info
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    job_title = Column(String(100), nullable=True)
    
    # Lead data
    custom_data = Column(JSON, nullable=True)  # Additional custom fields
    notes = Column(Text, nullable=True)
    
    # Status tracking
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.PENDING, index=True)
    qualification_status = Column(SQLEnum(QualificationStatus), nullable=True)
    qualification_score = Column(Float, default=0.0)  # 0-100
    
    # Call history
    call_count = Column(Integer, default=0)
    last_call_at = Column(DateTime, nullable=True)
    last_call_duration = Column(Integer, nullable=True)
    
    # Engagement
    interested = Column(Boolean, default=False)
    has_budget = Column(Boolean, nullable=True)
    timeline = Column(String(50), nullable=True)  # ASAP, 1-3 months, 3-6 months, 6+ months
    decision_maker = Column(Boolean, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Lead(name={self.first_name} {self.last_name}, status={self.status})>"


class OutboundCall(Base):
    """Outbound call log."""
    __tablename__ = "outbound_calls"

    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(100), unique=True, index=True, nullable=False)
    campaign_id = Column(Integer, nullable=False, index=True)
    lead_id = Column(Integer, nullable=False, index=True)
    
    # Call details
    from_number = Column(String(20), nullable=False)
    to_number = Column(String(20), nullable=False)
    status = Column(String(50), nullable=False)  # completed, failed, no_answer, voicemail
    duration_seconds = Column(Integer, default=0)
    
    # Transcription & recording
    transcript = Column(Text, nullable=True)
    recording_url = Column(String(500), nullable=True)
    
    # Results
    qualified = Column(Boolean, nullable=True)
    qualification_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Disposition
    disposition = Column(String(50), nullable=True)  # callback, interested, declined, etc.
    follow_up_date = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    ended_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<OutboundCall(sid={self.call_sid}, lead_id={self.lead_id}, status={self.status})>"


class LeadQualification(Base):
    """Detailed lead qualification data."""
    __tablename__ = "lead_qualifications"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, nullable=False, index=True)
    lead_id = Column(Integer, nullable=False, index=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    
    # Qualification data
    question_responses = Column(JSON, nullable=True)  # {question: answer}
    
    # Scoring components
    interest_score = Column(Float, default=0.0)      # 0-100
    budget_score = Column(Float, default=0.0)         # 0-100
    timeline_score = Column(Float, default=0.0)       # 0-100
    authority_score = Column(Float, default=0.0)      # 0-100 (decision maker)
    overall_score = Column(Float, default=0.0)        # 0-100
    
    # Final verdict
    qualified = Column(Boolean, default=False)
    qualification_reason = Column(Text, nullable=True)
    recommended_action = Column(String(50), nullable=True)  # follow_up, email, call_later
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<LeadQualification(lead_id={self.lead_id}, score={self.overall_score})>"


class CampaignMetrics(Base):
    """Aggregated campaign metrics."""
    __tablename__ = "campaign_metrics"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    
    # Daily metrics
    date = Column(DateTime, index=True, nullable=False)
    
    # Call metrics
    calls_attempted = Column(Integer, default=0)
    calls_connected = Column(Integer, default=0)
    calls_duration_total = Column(Integer, default=0)
    avg_call_duration = Column(Float, default=0.0)
    
    # Lead metrics
    leads_qualified = Column(Integer, default=0)
    leads_interested = Column(Integer, default=0)
    leads_declined = Column(Integer, default=0)
    leads_callback = Column(Integer, default=0)
    
    # Scoring
    avg_qualification_score = Column(Float, default=0.0)
    
    # Rates
    connection_rate = Column(Float, default=0.0)    # connected / attempted
    qualification_rate = Column(Float, default=0.0)  # qualified / connected
    conversion_rate = Column(Float, default=0.0)     # interested / qualified
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<CampaignMetrics(campaign_id={self.campaign_id}, date={self.date})>"
