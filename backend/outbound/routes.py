"""
Outbound Agent API Routes - Campaign and lead management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
import csv
import io

from backend.database import get_db
from backend.outbound.models import (
    Campaign,
    Lead,
    OutboundCall,
    LeadQualification,
    CampaignMetrics,
    CampaignStatus,
    LeadStatus,
    QualificationStatus,
)
from backend.outbound.agent import OutboundLeadAgent

router = APIRouter(prefix="/api/outbound", tags=["outbound"])
agent = OutboundLeadAgent()


class CampaignCreate(BaseModel):
    """Request to create campaign."""
    name: str
    description: Optional[str] = None
    script_template: str
    qualification_questions: Optional[List[str]] = None
    target_lead_count: int = 0
    calls_per_day_limit: int = 50
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class LeadCreate(BaseModel):
    """Request to create lead."""
    first_name: str
    last_name: str
    phone_number: str
    email: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    custom_data: Optional[dict] = None


class CampaignResponse(BaseModel):
    """Campaign response model."""
    id: int
    name: str
    status: str
    leads_contacted: int
    leads_qualified: int
    conversion_rate: float


@router.post("/campaigns")
async def create_campaign(
    request: CampaignCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Create new lead generation campaign."""
    campaign = Campaign(
        name=request.name,
        description=request.description,
        script_template=request.script_template,
        qualification_questions=request.qualification_questions,
        target_lead_count=request.target_lead_count,
        calls_per_day_limit=request.calls_per_day_limit,
        start_date=request.start_date,
        end_date=request.end_date,
        status=CampaignStatus.DRAFT,
    )
    
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    
    return {
        "id": campaign.id,
        "name": campaign.name,
        "status": campaign.status.value,
        "message": "Campaign created successfully",
    }


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get campaign details."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description,
        "status": campaign.status.value,
        "total_leads": campaign.total_leads,
        "leads_contacted": campaign.leads_contacted,
        "leads_qualified": campaign.leads_qualified,
        "conversion_rate": campaign.conversion_rate,
        "avg_call_duration": campaign.avg_call_duration,
        "created_at": campaign.created_at.isoformat(),
    }


@router.post("/campaigns/{campaign_id}/leads/bulk-upload")
async def bulk_upload_leads(
    campaign_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Bulk upload leads via CSV."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Read CSV
    contents = await file.read()
    stream = io.StringIO(contents.decode())
    reader = csv.DictReader(stream)
    
    leads_created = 0
    
    for row in reader:
        lead = Lead(
            campaign_id=campaign_id,
            first_name=row.get("first_name", ""),
            last_name=row.get("last_name", ""),
            phone_number=row.get("phone_number", ""),
            email=row.get("email"),
            company=row.get("company"),
            job_title=row.get("job_title"),
            status=LeadStatus.PENDING,
        )
        db.add(lead)
        leads_created += 1
    
    # Update campaign
    campaign.total_leads += leads_created
    
    db.commit()
    
    return {
        "campaign_id": campaign_id,
        "leads_created": leads_created,
        "total_leads": campaign.total_leads,
        "message": f"Successfully uploaded {leads_created} leads",
    }


@router.get("/campaigns/{campaign_id}/leads")
async def list_leads(
    campaign_id: int,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    """List leads in campaign."""
    query = db.query(Lead).filter(Lead.campaign_id == campaign_id)
    
    if status:
        query = query.filter(Lead.status == status)
    
    total = query.count()
    leads = query.order_by(Lead.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "campaign_id": campaign_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "leads": [
            {
                "id": lead.id,
                "name": f"{lead.first_name} {lead.last_name}",
                "phone": lead.phone_number,
                "company": lead.company,
                "status": lead.status.value,
                "qualification_score": lead.qualification_score,
                "call_count": lead.call_count,
            }
            for lead in leads
        ],
    }


@router.post("/campaigns/{campaign_id}/calls/initiate")
async def initiate_lead_call(
    campaign_id: int,
    lead_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Initiate outbound call to lead."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.campaign_id == campaign_id).first()
    
    if not campaign or not lead:
        raise HTTPException(status_code=404, detail="Campaign or lead not found")
    
    # Start call
    call_sid = f"CA{campaign_id}{lead_id}{int(datetime.now().timestamp())}"
    
    opening = await agent.start_lead_call(
        call_sid=call_sid,
        lead_name=lead.first_name,
        lead_phone=lead.phone_number,
        company="Your Company",
        industry=lead.custom_data.get("industry", "General") if lead.custom_data else "General",
        value_prop="improve your operations",
    )
    
    # Create call record
    db_call = OutboundCall(
        call_sid=call_sid,
        campaign_id=campaign_id,
        lead_id=lead_id,
        from_number="+0987654321",
        to_number=lead.phone_number,
        status="initiated",
    )
    
    # Update lead status
    lead.status = LeadStatus.CALLING
    lead.call_count += 1
    lead.last_call_at = datetime.now()
    
    db.add(db_call)
    db.commit()
    
    return {
        "call_sid": call_sid,
        "lead_id": lead_id,
        "opening_message": opening,
        "status": "ready",
    }


@router.post("/calls/{call_sid}/response")
async def process_lead_response(
    call_sid: str,
    lead_response: str,
    question_index: int,
    db: Session = Depends(get_db),
) -> dict:
    """Process lead's response to qualification question."""
    call = db.query(OutboundCall).filter(OutboundCall.call_sid == call_sid).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Process response
    result = await agent.process_lead_response(
        call_sid=call_sid,
        lead_response=lead_response,
        question_index=question_index,
    )
    
    # Get next question if continuing
    next_question = None
    if result["next_question"] is not None:
        next_question = await agent.ask_qualification_question(
            call_sid=call_sid,
            question_index=result["next_question"],
        )
    
    return {
        "intent": result["intent"],
        "score": result["score"],
        "next_action": result["next_action"],
        "next_question": next_question,
        "next_question_index": result["next_question"],
    }


@router.post("/calls/{call_sid}/end")
async def end_lead_call(
    call_sid: str,
    duration_seconds: int,
    transcript: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """End outbound call and process qualification."""
    call = db.query(OutboundCall).filter(OutboundCall.call_sid == call_sid).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # End call in agent
    summary = await agent.end_lead_call(
        call_sid=call_sid,
        duration_seconds=duration_seconds,
        transcript=transcript,
    )
    
    # Update call record
    call.status = "completed"
    call.duration_seconds = duration_seconds
    call.transcript = transcript
    call.ended_at = datetime.now()
    
    # Get qualification data
    qualification = summary.get("qualification", {})
    call.qualification_score = qualification.get("score", 0)
    call.qualified = qualification.get("status") in ["hot", "warm"]
    call.disposition = qualification.get("recommended_action")
    
    # Update lead
    lead = db.query(Lead).filter(Lead.id == call.lead_id).first()
    lead.status = LeadStatus.CONTACTED
    lead.qualification_score = qualification.get("score", 0)
    lead.qualification_status = QualificationStatus(qualification.get("status", "pending"))
    lead.last_call_duration = duration_seconds
    
    db.commit()
    
    # Create qualification record
    qual_record = LeadQualification(
        call_id=call.id,
        lead_id=call.lead_id,
        campaign_id=call.campaign_id,
        question_responses=summary.get("lead_data", {}),
        overall_score=qualification.get("score", 0),
        qualified=qualification.get("qualified", False),
        qualification_reason=str(qualification.get("reasons", [])),
        recommended_action=qualification.get("recommended_action"),
    )
    
    db.add(qual_record)
    db.commit()
    
    return {
        "call_sid": call_sid,
        "lead_id": call.lead_id,
        "status": "completed",
        "duration": duration_seconds,
        "qualification": qualification,
    }


@router.get("/campaigns/{campaign_id}/analytics")
async def get_campaign_analytics(
    campaign_id: int,
    days: int = 7,
    db: Session = Depends(get_db),
) -> dict:
    """Get campaign analytics and metrics."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get recent calls
    calls = db.query(OutboundCall).filter(
        OutboundCall.campaign_id == campaign_id,
        OutboundCall.created_at >= datetime.now() - timedelta(days=days),
    ).all()
    
    # Calculate metrics
    total_calls = len(calls)
    completed_calls = sum(1 for c in calls if c.status == "completed")
    qualified_leads = sum(1 for c in calls if c.qualified)
    avg_duration = sum(c.duration_seconds for c in calls if c.duration_seconds) / completed_calls if completed_calls > 0 else 0
    
    # Lead status distribution
    leads = db.query(Lead).filter(Lead.campaign_id == campaign_id).all()
    qualification_dist = {
        "hot": sum(1 for l in leads if l.qualification_status == QualificationStatus.HOT),
        "warm": sum(1 for l in leads if l.qualification_status == QualificationStatus.WARM),
        "cold": sum(1 for l in leads if l.qualification_status == QualificationStatus.COLD),
        "pending": sum(1 for l in leads if l.qualification_status is None),
    }
    
    return {
        "campaign_id": campaign_id,
        "period_days": days,
        "total_leads": campaign.total_leads,
        "leads_contacted": completed_calls,
        "leads_qualified": qualified_leads,
        "conversion_rate": qualified_leads / completed_calls if completed_calls > 0 else 0,
        "avg_call_duration": avg_duration,
        "qualification_distribution": qualification_dist,
        "contact_rate": completed_calls / campaign.total_leads if campaign.total_leads > 0 else 0,
    }


@router.post("/campaigns/{campaign_id}/status")
async def update_campaign_status(
    campaign_id: int,
    status: str,
    db: Session = Depends(get_db),
) -> dict:
    """Update campaign status."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    try:
        campaign.status = CampaignStatus(status)
        db.commit()
        
        return {
            "campaign_id": campaign_id,
            "status": campaign.status.value,
            "message": f"Campaign status updated to {status}",
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
