"""
SMS API Routes - FastAPI endpoints for SMS operations.
"""

import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.sms import schemas
from backend.sms.models import (
    SMSMessage, SMSResponse, SMSCampaign, CallSMSCorrelation,
    SMSStatus, SMSType, ResponseSentiment
)
from backend.sms.sms_service import SMSService
from backend.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sms", tags=["SMS"])

# Initialize SMS service
sms_service = SMSService(
    twilio_account_sid=settings.TWILIO_ACCOUNT_SID,
    twilio_auth_token=settings.TWILIO_AUTH_TOKEN,
    from_number=settings.TWILIO_PHONE_NUMBER
)


# === SMS Sending ===

@router.post("/send", response_model=schemas.SMSMessageResponse)
def send_sms(
    request: schemas.SendSMSRequest,
    db: Session = Depends(get_db)
):
    """Send a single SMS message."""
    try:
        sms_sid, success = sms_service.send_sms(
            to_number=request.to_number,
            message_body=request.message_body,
            message_type=request.message_type,
            related_call_id=request.related_call_id,
            related_lead_id=request.related_lead_id,
            campaign_id=request.campaign_id,
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to send SMS"
            )
        
        # Retrieve and return the stored message
        sms_msg = db.query(SMSMessage).filter(
            SMSMessage.sms_sid == sms_sid
        ).first()
        
        return sms_msg
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/bulk-send", response_model=schemas.BulkSendSMSResponse)
def bulk_send_sms(
    request: schemas.BulkSendSMSRequest,
    db: Session = Depends(get_db)
):
    """Send SMS to multiple recipients."""
    try:
        total_sent = 0
        total_failed = 0
        failed_recipients = []
        
        for sms_request in request.recipients:
            sms_sid, success = sms_service.send_sms(
                to_number=sms_request.to_number,
                message_body=sms_request.message_body,
                message_type=sms_request.message_type,
                related_call_id=sms_request.related_call_id,
                related_lead_id=sms_request.related_lead_id,
                campaign_id=request.campaign_id,
                db=db
            )
            
            if success:
                total_sent += 1
            else:
                total_failed += 1
                failed_recipients.append(sms_request.to_number)
        
        return schemas.BulkSendSMSResponse(
            total_requested=len(request.recipients),
            total_sent=total_sent,
            total_failed=total_failed,
            failed_recipients=failed_recipients,
            campaign_id=request.campaign_id
        )
    except Exception as e:
        logger.error(f"Error bulk sending SMS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# === SMS Webhooks ===

@router.post("/webhook/inbound")
async def inbound_sms_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle inbound SMS from Twilio."""
    try:
        data = await request.form()
        
        # Verify Twilio signature (in production)
        # twilio_client.Twilio.rest.lookups.v1.phone_numbers(...).fetch()
        
        message_sid = data.get("MessageSid")
        from_number = data.get("From")
        to_number = data.get("To")
        body = data.get("Body")
        
        response_id = sms_service.handle_inbound_sms(
            message_sid=message_sid,
            from_number=from_number,
            to_number=to_number,
            body=body,
            received_timestamp=int(datetime.utcnow().timestamp() * 1000),
            db=db
        )
        
        if not response_id:
            logger.warning(f"Could not process inbound SMS from {from_number}")
        
        # Twilio expects empty response
        return {}
    except Exception as e:
        logger.error(f"Error handling inbound SMS: {str(e)}")
        return {}


@router.post("/webhook/status")
async def sms_status_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle SMS status callback from Twilio."""
    try:
        data = await request.form()
        
        message_sid = data.get("MessageSid")
        sms_status = data.get("SmsStatus")  # sent, delivered, failed, undelivered
        
        # Map Twilio status to our enum
        status_map = {
            "sent": SMSStatus.SENT,
            "delivered": SMSStatus.DELIVERED,
            "failed": SMSStatus.FAILED,
            "undelivered": SMSStatus.UNDELIVERED
        }
        
        status_enum = status_map.get(sms_status, SMSStatus.SENT)
        
        sms_service.update_sms_status(
            sms_sid=message_sid,
            status=status_enum,
            db=db
        )
        
        return {}
    except Exception as e:
        logger.error(f"Error handling SMS status callback: {str(e)}")
        return {}


# === SMS Messages ===

@router.get("/messages", response_model=List[schemas.SMSMessageResponse])
def get_sms_messages(
    skip: int = 0,
    limit: int = 100,
    to_number: str = None,
    status: SMSStatus = None,
    db: Session = Depends(get_db)
):
    """Get SMS messages with optional filtering."""
    try:
        query = db.query(SMSMessage)
        
        if to_number:
            query = query.filter(SMSMessage.to_number == to_number)
        if status:
            query = query.filter(SMSMessage.status == status)
        
        messages = query.order_by(SMSMessage.created_at.desc()).offset(skip).limit(limit).all()
        return messages
    except Exception as e:
        logger.error(f"Error fetching SMS messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/messages/{message_id}", response_model=schemas.SMSMessageResponse)
def get_sms_message(message_id: int, db: Session = Depends(get_db)):
    """Get a specific SMS message."""
    try:
        message = db.query(SMSMessage).filter(
            SMSMessage.id == message_id
        ).first()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SMS message not found"
            )
        
        return message
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching SMS message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# === SMS Responses ===

@router.get("/responses", response_model=List[schemas.SMSResponseData])
def get_sms_responses(
    skip: int = 0,
    limit: int = 100,
    sentiment: ResponseSentiment = None,
    intent: str = None,
    db: Session = Depends(get_db)
):
    """Get SMS responses with optional filtering."""
    try:
        query = db.query(SMSResponse)
        
        if sentiment:
            query = query.filter(SMSResponse.sentiment == sentiment)
        if intent:
            query = query.filter(SMSResponse.intent == intent)
        
        responses = query.order_by(SMSResponse.created_at.desc()).offset(skip).limit(limit).all()
        return responses
    except Exception as e:
        logger.error(f"Error fetching SMS responses: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/responses/{response_id}", response_model=schemas.SMSResponseData)
def get_sms_response(response_id: int, db: Session = Depends(get_db)):
    """Get a specific SMS response."""
    try:
        response = db.query(SMSResponse).filter(
            SMSResponse.id == response_id
        ).first()
        
        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SMS response not found"
            )
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching SMS response: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# === SMS Campaigns ===

@router.post("/campaigns", response_model=schemas.SMSCampaignResponse)
def create_sms_campaign(
    request: schemas.CreateSMSCampaignRequest,
    db: Session = Depends(get_db)
):
    """Create a new SMS campaign."""
    try:
        campaign = SMSCampaign(
            name=request.name,
            description=request.description,
            message_template=request.message_template,
            trigger_event=request.trigger_event,
            delay_seconds=request.delay_seconds
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign
    except Exception as e:
        logger.error(f"Error creating SMS campaign: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/campaigns", response_model=List[schemas.SMSCampaignResponse])
def get_sms_campaigns(
    skip: int = 0,
    limit: int = 100,
    active: bool = None,
    db: Session = Depends(get_db)
):
    """Get SMS campaigns."""
    try:
        query = db.query(SMSCampaign)
        
        if active is not None:
            query = query.filter(SMSCampaign.active == active)
        
        campaigns = query.order_by(SMSCampaign.created_at.desc()).offset(skip).limit(limit).all()
        return campaigns
    except Exception as e:
        logger.error(f"Error fetching SMS campaigns: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/campaigns/{campaign_id}", response_model=schemas.SMSCampaignResponse)
def get_sms_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Get a specific SMS campaign."""
    try:
        campaign = db.query(SMSCampaign).filter(
            SMSCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        return campaign
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching campaign: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/campaigns/{campaign_id}", response_model=schemas.SMSCampaignResponse)
def update_sms_campaign(
    campaign_id: int,
    request: schemas.UpdateSMSCampaignRequest,
    db: Session = Depends(get_db)
):
    """Update an SMS campaign."""
    try:
        campaign = db.query(SMSCampaign).filter(
            SMSCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        if request.name is not None:
            campaign.name = request.name
        if request.description is not None:
            campaign.description = request.description
        if request.message_template is not None:
            campaign.message_template = request.message_template
        if request.trigger_event is not None:
            campaign.trigger_event = request.trigger_event
        if request.delay_seconds is not None:
            campaign.delay_seconds = request.delay_seconds
        if request.active is not None:
            campaign.active = request.active
        
        db.commit()
        db.refresh(campaign)
        return campaign
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating campaign: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# === Schedule Follow-up ===

@router.post("/followup/schedule", response_model=schemas.ScheduleFollowupResponse)
def schedule_followup(
    request: schemas.ScheduleFollowupRequest,
    db: Session = Depends(get_db)
):
    """Schedule SMS follow-up after a call."""
    try:
        # Create correlation record
        correlation = CallSMSCorrelation(
            call_id=request.call_id,
            lead_id=request.lead_id,
            sms_message_id=None,  # Will be filled when SMS is sent
            call_to_sms_delay_seconds=request.delay_seconds
        )
        db.add(correlation)
        db.flush()
        
        # Schedule SMS (integrate with Celery in production)
        success = sms_service.schedule_followup_sms(
            call_id=request.call_id,
            lead_id=request.lead_id,
            to_number=request.to_number,
            message_template=request.message_template,
            delay_seconds=request.delay_seconds,
            db=db
        )
        
        db.commit()
        
        return schemas.ScheduleFollowupResponse(
            success=success,
            message="SMS follow-up scheduled" if success else "Failed to schedule SMS",
            correlation_id=correlation.id if success else None
        )
    except Exception as e:
        logger.error(f"Error scheduling follow-up: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# === Analytics ===

@router.get("/analytics", response_model=schemas.SMSAnalyticsResponse)
def get_sms_analytics(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Get SMS analytics for the past N days."""
    try:
        analytics = sms_service.get_sms_analytics(db=db, days=days)
        return schemas.SMSAnalyticsResponse(**analytics)
    except Exception as e:
        logger.error(f"Error fetching analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# === Call-SMS Correlation ===

@router.get("/correlations", response_model=List[schemas.CallSMSCorrelationResponse])
def get_correlations(
    call_id: int = None,
    lead_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get call-SMS correlations."""
    try:
        query = db.query(CallSMSCorrelation)
        
        if call_id:
            query = query.filter(CallSMSCorrelation.call_id == call_id)
        if lead_id:
            query = query.filter(CallSMSCorrelation.lead_id == lead_id)
        
        correlations = query.offset(skip).limit(limit).all()
        return correlations
    except Exception as e:
        logger.error(f"Error fetching correlations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/correlations/{correlation_id}", response_model=schemas.CallSMSCorrelationResponse)
def get_correlation(correlation_id: int, db: Session = Depends(get_db)):
    """Get a specific call-SMS correlation."""
    try:
        correlation = db.query(CallSMSCorrelation).filter(
            CallSMSCorrelation.id == correlation_id
        ).first()
        
        if not correlation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Correlation not found"
            )
        
        return correlation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching correlation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
