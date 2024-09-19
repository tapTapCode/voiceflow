"""
Inbound Agent API Routes - Twilio webhooks and call management.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from backend.database import get_db
from backend.inbound.models import (
    InboundCall,
    Customer,
    SupportTicket,
    CallStatus,
    SentimentType,
    ResolutionStatus,
)
from backend.inbound.agent import InboundSupportAgent

router = APIRouter(prefix="/api/inbound", tags=["inbound"])
agent = InboundSupportAgent()


class CallStartRequest(BaseModel):
    """Request to start a new call."""
    from_number: str
    to_number: str
    call_sid: str
    customer_id: Optional[int] = None


class CallMessageRequest(BaseModel):
    """Customer message during call."""
    call_sid: str
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "call_sid": "CA123456789abcdef",
                "message": "I need help with my account",
            }
        }


class CallEndRequest(BaseModel):
    """Request to end a call."""
    call_sid: str
    duration_seconds: int
    transcript: Optional[str] = None
    resolved: bool = False


class CallResponse(BaseModel):
    """Call response data."""
    call_sid: str
    status: str
    sentiment: str
    sentiment_score: float
    agent_message: str
    should_escalate: bool


@router.post("/calls/start")
async def start_call(
    request: CallStartRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Start new inbound call.
    
    Twilio sends: CallSid, From, To, CallStatus
    """
    # Get or create customer
    customer = db.query(Customer).filter(
        Customer.phone_number == request.from_number
    ).first()
    
    if not customer:
        customer = Customer(phone_number=request.from_number)
        db.add(customer)
        db.commit()
        db.refresh(customer)
    
    # Create call record
    db_call = InboundCall(
        call_sid=request.call_sid,
        customer_id=customer.id,
        from_number=request.from_number,
        to_number=request.to_number,
        status=CallStatus.INCOMING,
        started_at=datetime.now(),
    )
    db.add(db_call)
    db.commit()
    db.refresh(db_call)
    
    # Generate greeting
    greeting = await agent.start_call(
        request.call_sid,
        request.from_number,
        customer_data={"id": customer.id, "phone": request.from_number},
    )
    
    return {
        "call_id": db_call.id,
        "call_sid": db_call.call_sid,
        "greeting": greeting,
        "status": "ready",
    }


@router.post("/calls/message")
async def process_message(
    request: CallMessageRequest,
    db: Session = Depends(get_db),
) -> CallResponse:
    """
    Process customer message and generate agent response.
    """
    # Get call
    db_call = db.query(InboundCall).filter(
        InboundCall.call_sid == request.call_sid
    ).first()
    
    if not db_call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Process message
    result = await agent.process_customer_message(
        request.call_sid,
        request.message,
    )
    
    # Update call with sentiment
    db_call.sentiment = SentimentType(result["sentiment"])
    db_call.sentiment_score = result["sentiment_score"]
    db_call.status = CallStatus.IN_PROGRESS
    
    # Check for escalation
    if result["should_escalate"]:
        db_call.escalated = True
        db_call.escalation_reason = result.get("escalation_reason")
        db_call.status = CallStatus.ESCALATED
    
    db.commit()
    db.refresh(db_call)
    
    return CallResponse(
        call_sid=db_call.call_sid,
        status=db_call.status.value,
        sentiment=result["sentiment"],
        sentiment_score=result["sentiment_score"],
        agent_message=result["agent_message"],
        should_escalate=result["should_escalate"],
    )


@router.post("/calls/end")
async def end_call(
    request: CallEndRequest,
    db: Session = Depends(get_db),
) -> dict:
    """End call and store transcript."""
    # Get call
    db_call = db.query(InboundCall).filter(
        InboundCall.call_sid == request.call_sid
    ).first()
    
    if not db_call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # End call
    summary = await agent.end_call(
        request.call_sid,
        request.duration_seconds,
        request.transcript,
    )
    
    # Update call record
    db_call.status = CallStatus.COMPLETED
    db_call.duration_seconds = request.duration_seconds
    db_call.transcript = request.transcript
    db_call.ended_at = datetime.now()
    
    db.commit()
    
    # Create support ticket if not resolved
    if not request.resolved and db_call.escalated:
        ticket = SupportTicket(
            call_id=db_call.id,
            customer_id=db_call.customer_id,
            issue_description=request.transcript,
            resolution_status=ResolutionStatus.UNRESOLVED,
        )
        db.add(ticket)
        db.commit()
    
    return {
        "call_id": db_call.id,
        "status": "completed",
        "duration": request.duration_seconds,
        "resolved": request.resolved,
        "sentiment": db_call.sentiment.value if db_call.sentiment else None,
    }


@router.get("/calls/{call_sid}")
async def get_call(
    call_sid: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get call details."""
    db_call = db.query(InboundCall).filter(
        InboundCall.call_sid == call_sid
    ).first()
    
    if not db_call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return {
        "id": db_call.id,
        "call_sid": db_call.call_sid,
        "from": db_call.from_number,
        "to": db_call.to_number,
        "status": db_call.status.value,
        "duration": db_call.duration_seconds,
        "sentiment": db_call.sentiment.value if db_call.sentiment else None,
        "sentiment_score": db_call.sentiment_score,
        "escalated": db_call.escalated,
        "created_at": db_call.created_at.isoformat(),
    }


@router.get("/calls")
async def list_calls(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """List inbound calls with filters."""
    query = db.query(InboundCall)
    
    if status:
        query = query.filter(InboundCall.status == status)
    
    total = query.count()
    calls = query.order_by(InboundCall.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "calls": [
            {
                "id": call.id,
                "call_sid": call.call_sid,
                "status": call.status.value,
                "sentiment": call.sentiment.value if call.sentiment else None,
                "duration": call.duration_seconds,
                "escalated": call.escalated,
                "created_at": call.created_at.isoformat(),
            }
            for call in calls
        ],
    }


@router.post("/calls/{call_id}/feedback")
async def submit_feedback(
    call_id: int,
    csat_score: int,
    feedback: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """Submit customer feedback for a call."""
    if not 1 <= csat_score <= 5:
        raise HTTPException(status_code=400, detail="CSAT score must be 1-5")
    
    # Find ticket for call
    ticket = db.query(SupportTicket).filter(
        SupportTicket.call_id == call_id
    ).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    
    ticket.csat_score = csat_score
    ticket.feedback = feedback
    db.commit()
    
    return {"status": "success", "csat_score": csat_score}


@router.get("/analytics/summary")
async def get_analytics_summary(
    days: int = 7,
    db: Session = Depends(get_db),
) -> dict:
    """Get analytics summary for recent period."""
    from sqlalchemy import func
    
    # Get calls from last N days
    calls = db.query(InboundCall).filter(
        InboundCall.created_at >= datetime.now().replace(day=1)
    ).all()
    
    total_calls = len(calls)
    completed = sum(1 for c in calls if c.status == CallStatus.COMPLETED)
    escalated = sum(1 for c in calls if c.escalated)
    avg_duration = (
        sum(c.duration_seconds for c in calls if c.duration_seconds) / completed
        if completed > 0
        else 0
    )
    
    # Sentiment distribution
    sentiment_dist = {
        "positive": sum(1 for c in calls if c.sentiment == SentimentType.POSITIVE),
        "neutral": sum(1 for c in calls if c.sentiment == SentimentType.NEUTRAL),
        "negative": sum(1 for c in calls if c.sentiment == SentimentType.NEGATIVE),
    }
    
    return {
        "total_calls": total_calls,
        "completed_calls": completed,
        "escalated_calls": escalated,
        "avg_duration_seconds": avg_duration,
        "sentiment_distribution": sentiment_dist,
        "resolution_rate": completed / total_calls if total_calls > 0 else 0,
    }
