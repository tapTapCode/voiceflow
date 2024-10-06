"""
SMS Service - Handles SMS sending, response processing, and sentiment analysis.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from sqlalchemy.orm import Session
from twilio.rest import Client

from backend.sms.models import (
    SMSMessage, SMSResponse, SMSCampaign, CallSMSCorrelation, 
    SMSAnalytics, SMSStatus, SMSType, ResponseSentiment
)
from backend.core.llm_service import LLMService

logger = logging.getLogger(__name__)


class SMSService:
    """Manages SMS operations: sending, receiving, and response analysis."""
    
    def __init__(self, twilio_account_sid: str, twilio_auth_token: str, from_number: str):
        """Initialize SMS service with Twilio credentials."""
        self.twilio_client = Client(twilio_account_sid, twilio_auth_token)
        self.from_number = from_number
        self.llm_service = LLMService()
        
    def send_sms(
        self,
        to_number: str,
        message_body: str,
        message_type: SMSType = SMSType.FOLLOWUP,
        related_call_id: Optional[int] = None,
        related_lead_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> Tuple[Optional[str], bool]:
        """
        Send an SMS message via Twilio.
        
        Args:
            to_number: Recipient phone number
            message_body: SMS content
            message_type: Type of SMS (followup, reminder, etc.)
            related_call_id: Link to call (if applicable)
            related_lead_id: Link to lead (if applicable)
            campaign_id: Link to campaign (if applicable)
            db: Database session for storing record
            
        Returns:
            Tuple of (SMS SID, success boolean)
        """
        try:
            # Send via Twilio
            message = self.twilio_client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            
            # Store in database if session provided
            if db:
                sms_record = SMSMessage(
                    sms_sid=message.sid,
                    message_type=message_type,
                    from_number=self.from_number,
                    to_number=to_number,
                    message_body=message_body,
                    status=SMSStatus.SENT,
                    related_call_id=related_call_id,
                    related_lead_id=related_lead_id,
                    campaign_id=campaign_id,
                    cost=message.price if hasattr(message, 'price') else None,
                    segments=message.num_segments if hasattr(message, 'num_segments') else 1,
                    sent_at=datetime.utcnow()
                )
                db.add(sms_record)
                db.commit()
                db.refresh(sms_record)
                logger.info(f"SMS sent to {to_number}, SID: {message.sid}")
                return message.sid, True
            else:
                logger.info(f"SMS sent to {to_number}, SID: {message.sid}")
                return message.sid, True
                
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_number}: {str(e)}")
            return None, False
    
    def handle_inbound_sms(
        self,
        message_sid: str,
        from_number: str,
        to_number: str,
        body: str,
        received_timestamp: str,
        db: Session
    ) -> Optional[int]:
        """
        Handle inbound SMS response via Twilio webhook.
        
        Args:
            message_sid: Twilio message SID
            from_number: Sender phone number
            to_number: Receiver phone number
            body: Message content
            received_timestamp: Timestamp (Unix)
            db: Database session
            
        Returns:
            SMSResponse record ID
        """
        try:
            # Find original message
            original_msg = db.query(SMSMessage).filter(
                SMSMessage.to_number == from_number
            ).order_by(SMSMessage.created_at.desc()).first()
            
            if not original_msg:
                logger.warning(f"No original SMS found for response from {from_number}")
                return None
            
            # Analyze sentiment and intent
            sentiment, confidence, intent, keywords = self._analyze_response(body)
            
            received_dt = datetime.fromtimestamp(int(received_timestamp) / 1000)
            
            # Store response
            response_record = SMSResponse(
                message_sid=message_sid,
                original_message_id=original_msg.id,
                from_number=from_number,
                to_number=to_number,
                response_body=body,
                sentiment=sentiment,
                confidence_score=confidence,
                intent=intent,
                keywords=keywords,
                received_at=received_dt
            )
            db.add(response_record)
            db.flush()
            
            # Update original message status
            original_msg.status = SMSStatus.DELIVERED
            
            # Update correlation if exists
            if original_msg.related_call_id and original_msg.related_lead_id:
                correlation = db.query(CallSMSCorrelation).filter(
                    CallSMSCorrelation.call_id == original_msg.related_call_id,
                    CallSMSCorrelation.lead_id == original_msg.related_lead_id
                ).first()
                
                if correlation:
                    correlation.sms_response_id = response_record.id
                    correlation.response_time_seconds = int(
                        (received_dt - original_msg.sent_at).total_seconds()
                    )
                    if sentiment in [ResponseSentiment.INTERESTED, ResponseSentiment.POSITIVE]:
                        correlation.conversion = True
            
            db.commit()
            db.refresh(response_record)
            logger.info(f"SMS response processed: {response_record.id}, sentiment: {sentiment}")
            return response_record.id
            
        except Exception as e:
            logger.error(f"Failed to handle inbound SMS: {str(e)}")
            db.rollback()
            return None
    
    def _analyze_response(self, message_body: str) -> Tuple[ResponseSentiment, float, Optional[str], Optional[str]]:
        """
        Analyze SMS response using LLM for sentiment and intent.
        
        Returns:
            Tuple of (sentiment, confidence, intent, keywords)
        """
        try:
            prompt = f"""Analyze this SMS response and extract:
1. Sentiment: positive, neutral, negative, interested, or not_interested
2. Intent: One of: interested, callback_request, unsubscribe, complaint, question, acknowledgment, or other
3. Keywords: Relevant words indicating intent (comma-separated)
4. Confidence: 0-1 score

Response: "{message_body}"

Respond in JSON format:
{{"sentiment": "...", "confidence": 0.0, "intent": "...", "keywords": "..."}}"""
            
            response = self.llm_service.query(prompt)
            import json
            
            data = json.loads(response)
            sentiment = ResponseSentiment(data.get("sentiment", "neutral"))
            confidence = float(data.get("confidence", 0.5))
            intent = data.get("intent", "other")
            keywords = data.get("keywords", "")
            
            return sentiment, confidence, intent, keywords
            
        except Exception as e:
            logger.warning(f"LLM analysis failed, using basic sentiment: {str(e)}")
            return self._basic_sentiment_analysis(message_body)
    
    def _basic_sentiment_analysis(self, message_body: str) -> Tuple[ResponseSentiment, float, Optional[str], Optional[str]]:
        """Fallback basic sentiment analysis using keywords."""
        body_lower = message_body.lower()
        
        positive_keywords = ["yes", "interested", "great", "love", "want", "ready", "sounds good"]
        negative_keywords = ["no", "not interested", "unsubscribe", "stop", "remove", "delete"]
        
        positive_count = sum(1 for kw in positive_keywords if kw in body_lower)
        negative_count = sum(1 for kw in negative_keywords if kw in body_lower)
        
        if positive_count > negative_count:
            sentiment = ResponseSentiment.INTERESTED
            confidence = 0.7
            intent = "interested"
        elif negative_count > positive_count:
            sentiment = ResponseSentiment.NOT_INTERESTED
            confidence = 0.7
            intent = "not_interested"
        else:
            sentiment = ResponseSentiment.NEUTRAL
            confidence = 0.5
            intent = "acknowledgment"
        
        return sentiment, confidence, intent, ""
    
    def schedule_followup_sms(
        self,
        call_id: int,
        lead_id: int,
        to_number: str,
        message_template: str,
        delay_seconds: int = 300,
        db: Optional[Session] = None
    ) -> bool:
        """
        Schedule SMS follow-up after a call.
        
        Args:
            call_id: Related call ID
            lead_id: Related lead ID
            to_number: Recipient number
            message_template: Message template (can include {variables})
            delay_seconds: Delay before sending (default 5 min)
            db: Database session
            
        Returns:
            Success boolean
        """
        try:
            # In production, use a task queue (Celery, RQ) for scheduling
            # For now, send immediately after delay
            import asyncio
            
            async def delayed_send():
                await asyncio.sleep(delay_seconds)
                self.send_sms(
                    to_number=to_number,
                    message_body=message_template,
                    message_type=SMSType.FOLLOWUP,
                    related_call_id=call_id,
                    related_lead_id=lead_id,
                    db=db
                )
            
            # Queue for background processing (implement with Celery in production)
            logger.info(f"Scheduled SMS follow-up for call {call_id}, lead {lead_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule SMS follow-up: {str(e)}")
            return False
    
    def get_sms_analytics(
        self,
        db: Session,
        days: int = 7
    ) -> Dict:
        """Get SMS analytics for the past N days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Aggregate SMS metrics
            sent_count = db.query(SMSMessage).filter(
                SMSMessage.created_at >= cutoff_date,
                SMSMessage.status.in_([SMSStatus.SENT, SMSStatus.DELIVERED])
            ).count()
            
            delivered_count = db.query(SMSMessage).filter(
                SMSMessage.created_at >= cutoff_date,
                SMSMessage.status == SMSStatus.DELIVERED
            ).count()
            
            failed_count = db.query(SMSMessage).filter(
                SMSMessage.created_at >= cutoff_date,
                SMSMessage.status.in_([SMSStatus.FAILED, SMSStatus.UNDELIVERED])
            ).count()
            
            response_count = db.query(SMSResponse).filter(
                SMSResponse.created_at >= cutoff_date
            ).count()
            
            response_rate = (response_count / sent_count * 100) if sent_count > 0 else 0
            
            # Sentiment breakdown
            positive_responses = db.query(SMSResponse).filter(
                SMSResponse.created_at >= cutoff_date,
                SMSResponse.sentiment.in_([ResponseSentiment.POSITIVE, ResponseSentiment.INTERESTED])
            ).count()
            
            negative_responses = db.query(SMSResponse).filter(
                SMSResponse.created_at >= cutoff_date,
                SMSResponse.sentiment.in_([ResponseSentiment.NEGATIVE, ResponseSentiment.NOT_INTERESTED])
            ).count()
            
            return {
                "period_days": days,
                "total_sent": sent_count,
                "total_delivered": delivered_count,
                "total_failed": failed_count,
                "total_responses": response_count,
                "response_rate_percent": round(response_rate, 2),
                "positive_responses": positive_responses,
                "negative_responses": negative_responses,
                "neutral_responses": response_count - positive_responses - negative_responses,
            }
        except Exception as e:
            logger.error(f"Failed to get SMS analytics: {str(e)}")
            return {}
    
    def update_sms_status(
        self,
        sms_sid: str,
        status: SMSStatus,
        db: Session
    ) -> bool:
        """Update SMS message status from Twilio status callback."""
        try:
            sms_record = db.query(SMSMessage).filter(
                SMSMessage.sms_sid == sms_sid
            ).first()
            
            if sms_record:
                sms_record.status = status
                db.commit()
                logger.info(f"Updated SMS {sms_sid} status to {status}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update SMS status: {str(e)}")
            return False
