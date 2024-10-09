"""
Celery tasks for SMS operations - scheduled SMS sending, analytics, etc.
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task

from backend.database import SessionLocal
from backend.sms.models import (
    SMSMessage, SMSResponse, SMSCampaign, CallSMSCorrelation, SMSAnalytics,
    SMSStatus, SMSType, ResponseSentiment
)
from backend.sms.sms_service import SMSService
from backend.core.config import settings

logger = logging.getLogger(__name__)

# Initialize SMS service for tasks
sms_service = SMSService(
    twilio_account_sid=settings.TWILIO_ACCOUNT_SID,
    twilio_auth_token=settings.TWILIO_AUTH_TOKEN,
    from_number=settings.TWILIO_PHONE_NUMBER
)


@shared_task(bind=True, max_retries=3)
def send_scheduled_sms(
    self,
    call_id: int,
    lead_id: int,
    to_number: str,
    message_body: str,
    message_type: str = "followup",
    related_campaign_id: int = None
):
    """
    Send SMS message with retry logic.
    
    Args:
        call_id: Related call ID
        lead_id: Related lead ID
        to_number: Recipient phone number
        message_body: Message content
        message_type: Type of SMS
        related_campaign_id: Campaign ID (optional)
    """
    db = SessionLocal()
    try:
        sms_type = SMSType(message_type)
        
        sms_sid, success = sms_service.send_sms(
            to_number=to_number,
            message_body=message_body,
            message_type=sms_type,
            related_call_id=call_id,
            related_lead_id=lead_id,
            campaign_id=related_campaign_id,
            db=db
        )
        
        if success:
            # Create correlation
            sms_msg = db.query(SMSMessage).filter(
                SMSMessage.sms_sid == sms_sid
            ).first()
            
            if sms_msg:
                correlation = CallSMSCorrelation(
                    call_id=call_id,
                    sms_message_id=sms_msg.id,
                    lead_id=lead_id,
                    call_to_sms_delay_seconds=0
                )
                db.add(correlation)
                db.commit()
            
            logger.info(f"Scheduled SMS sent successfully: {sms_sid}")
            return {"success": True, "sms_sid": sms_sid}
        else:
            logger.error(f"Failed to send SMS to {to_number}")
            # Retry with exponential backoff
            raise self.retry(countdown=60 * (2 ** self.request.retries))
            
    except Exception as e:
        logger.error(f"Error in send_scheduled_sms: {str(e)}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def process_sms_response(
    self,
    message_sid: str,
    from_number: str,
    to_number: str,
    body: str
):
    """
    Process inbound SMS response asynchronously.
    
    Args:
        message_sid: Twilio message SID
        from_number: Sender phone
        to_number: Receiver phone
        body: Message content
    """
    db = SessionLocal()
    try:
        response_id = sms_service.handle_inbound_sms(
            message_sid=message_sid,
            from_number=from_number,
            to_number=to_number,
            body=body,
            received_timestamp=str(int(datetime.utcnow().timestamp() * 1000)),
            db=db
        )
        
        if response_id:
            logger.info(f"SMS response processed: {response_id}")
            return {"success": True, "response_id": response_id}
        else:
            logger.warning(f"Could not process SMS response from {from_number}")
            return {"success": False, "reason": "No original message found"}
            
    except Exception as e:
        logger.error(f"Error processing SMS response: {str(e)}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@shared_task
def update_daily_analytics():
    """
    Calculate and store daily SMS analytics.
    Runs daily at midnight.
    """
    db = SessionLocal()
    try:
        yesterday = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get yesterday's data
        start_time = yesterday - timedelta(days=1)
        end_time = yesterday
        
        sent_count = db.query(SMSMessage).filter(
            SMSMessage.created_at >= start_time,
            SMSMessage.created_at < end_time,
            SMSMessage.status.in_([SMSStatus.SENT, SMSStatus.DELIVERED])
        ).count()
        
        delivered_count = db.query(SMSMessage).filter(
            SMSMessage.created_at >= start_time,
            SMSMessage.created_at < end_time,
            SMSMessage.status == SMSStatus.DELIVERED
        ).count()
        
        failed_count = db.query(SMSMessage).filter(
            SMSMessage.created_at >= start_time,
            SMSMessage.created_at < end_time,
            SMSMessage.status.in_([SMSStatus.FAILED, SMSStatus.UNDELIVERED])
        ).count()
        
        response_count = db.query(SMSResponse).filter(
            SMSResponse.created_at >= start_time,
            SMSResponse.created_at < end_time
        ).count()
        
        response_rate = (response_count / sent_count * 100) if sent_count > 0 else 0
        
        positive_responses = db.query(SMSResponse).filter(
            SMSResponse.created_at >= start_time,
            SMSResponse.created_at < end_time,
            SMSResponse.sentiment.in_([ResponseSentiment.POSITIVE, ResponseSentiment.INTERESTED])
        ).count()
        
        negative_responses = db.query(SMSResponse).filter(
            SMSResponse.created_at >= start_time,
            SMSResponse.created_at < end_time,
            SMSResponse.sentiment.in_([ResponseSentiment.NEGATIVE, ResponseSentiment.NOT_INTERESTED])
        ).count()
        
        neutral_responses = response_count - positive_responses - negative_responses
        
        conversions = db.query(CallSMSCorrelation).filter(
            CallSMSCorrelation.created_at >= start_time,
            CallSMSCorrelation.created_at < end_time,
            CallSMSCorrelation.conversion == True
        ).count()
        
        conversion_rate = (conversions / sent_count * 100) if sent_count > 0 else 0
        
        # Calculate total cost
        total_cost = db.query(func.sum(SMSMessage.cost)).filter(
            SMSMessage.created_at >= start_time,
            SMSMessage.created_at < end_time
        ).scalar() or 0.0
        
        # Store analytics
        analytics = SMSAnalytics(
            date=yesterday,
            total_sent=sent_count,
            total_delivered=delivered_count,
            total_failed=failed_count,
            total_responses=response_count,
            response_rate=response_rate,
            positive_responses=positive_responses,
            negative_responses=negative_responses,
            neutral_responses=neutral_responses,
            conversions=conversions,
            conversion_rate=conversion_rate,
            total_cost=total_cost
        )
        db.add(analytics)
        db.commit()
        
        logger.info(f"Daily SMS analytics computed for {yesterday.date()}")
        return {
            "date": yesterday.isoformat(),
            "sent": sent_count,
            "delivered": delivered_count,
            "responses": response_count
        }
        
    except Exception as e:
        logger.error(f"Error computing daily analytics: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()


@shared_task
def cleanup_old_sms(days: int = 90):
    """
    Archive/delete old SMS records older than N days.
    Run periodically for database maintenance.
    
    Args:
        days: Number of days to retain (default 90)
    """
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Delete old SMS responses
        old_responses = db.query(SMSResponse).filter(
            SMSResponse.created_at < cutoff_date
        ).delete()
        
        # Delete old SMS messages without responses
        old_messages = db.query(SMSMessage).filter(
            SMSMessage.created_at < cutoff_date,
            ~db.query(SMSResponse).filter(
                SMSResponse.original_message_id == SMSMessage.id
            ).exists()
        ).delete()
        
        db.commit()
        
        logger.info(f"Cleanup complete: deleted {old_responses} responses and {old_messages} messages older than {cutoff_date}")
        return {
            "responses_deleted": old_responses,
            "messages_deleted": old_messages
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_sms: {str(e)}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@shared_task
def update_campaign_metrics():
    """
    Update SMS campaign performance metrics.
    Run periodically to keep metrics fresh.
    """
    db = SessionLocal()
    try:
        campaigns = db.query(SMSCampaign).filter(
            SMSCampaign.active == True
        ).all()
        
        for campaign in campaigns:
            # Count sent messages for this campaign
            sent = db.query(SMSMessage).filter(
                SMSMessage.campaign_id == campaign.id,
                SMSMessage.status.in_([SMSStatus.SENT, SMSStatus.DELIVERED])
            ).count()
            
            delivered = db.query(SMSMessage).filter(
                SMSMessage.campaign_id == campaign.id,
                SMSMessage.status == SMSStatus.DELIVERED
            ).count()
            
            # Count responses
            responses = db.query(SMSResponse).join(
                SMSMessage,
                SMSResponse.original_message_id == SMSMessage.id
            ).filter(
                SMSMessage.campaign_id == campaign.id
            ).count()
            
            response_rate = (responses / sent * 100) if sent > 0 else 0
            
            campaign.total_sent = sent
            campaign.total_delivered = delivered
            campaign.total_responses = responses
            campaign.response_rate = response_rate
        
        db.commit()
        logger.info(f"Updated metrics for {len(campaigns)} campaigns")
        return {"campaigns_updated": len(campaigns)}
        
    except Exception as e:
        logger.error(f"Error updating campaign metrics: {str(e)}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()
