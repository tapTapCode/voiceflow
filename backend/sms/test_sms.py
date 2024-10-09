"""
SMS module integration tests.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from backend.sms.models import (
    SMSMessage, SMSResponse, SMSCampaign, CallSMSCorrelation,
    SMSStatus, SMSType, ResponseSentiment
)
from backend.sms.sms_service import SMSService
from backend.sms import schemas


class TestSMSService:
    """Test SMS service functionality."""
    
    @pytest.fixture
    def sms_service(self):
        """Create SMS service instance."""
        return SMSService(
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
            from_number="+1234567890"
        )
    
    @pytest.fixture
    def db_session(self, database):
        """Get database session."""
        return database.SessionLocal()
    
    # === Send SMS Tests ===
    
    def test_send_sms_success(self, sms_service, db_session):
        """Test successful SMS sending."""
        with patch.object(sms_service.twilio_client.messages, 'create') as mock_create:
            mock_message = Mock()
            mock_message.sid = "test_sid_123"
            mock_message.price = "-0.0075"
            mock_message.num_segments = 1
            mock_create.return_value = mock_message
            
            sms_sid, success = sms_service.send_sms(
                to_number="+1987654321",
                message_body="Test message",
                message_type=SMSType.FOLLOWUP,
                related_call_id=1,
                related_lead_id=2,
                db=db_session
            )
            
            assert success is True
            assert sms_sid == "test_sid_123"
            
            # Verify message stored
            stored_msg = db_session.query(SMSMessage).filter(
                SMSMessage.sms_sid == "test_sid_123"
            ).first()
            assert stored_msg is not None
            assert stored_msg.to_number == "+1987654321"
            assert stored_msg.status == SMSStatus.SENT
            assert stored_msg.related_call_id == 1
            assert stored_msg.related_lead_id == 2
    
    def test_send_sms_failure(self, sms_service):
        """Test SMS sending failure."""
        with patch.object(sms_service.twilio_client.messages, 'create') as mock_create:
            mock_create.side_effect = Exception("Twilio error")
            
            sms_sid, success = sms_service.send_sms(
                to_number="+1987654321",
                message_body="Test message"
            )
            
            assert success is False
            assert sms_sid is None
    
    def test_send_sms_without_db(self, sms_service):
        """Test SMS sending without database session."""
        with patch.object(sms_service.twilio_client.messages, 'create') as mock_create:
            mock_message = Mock()
            mock_message.sid = "test_sid_456"
            mock_create.return_value = mock_message
            
            sms_sid, success = sms_service.send_sms(
                to_number="+1987654321",
                message_body="Test message"
            )
            
            assert success is True
            assert sms_sid == "test_sid_456"
    
    # === Inbound SMS Tests ===
    
    def test_handle_inbound_sms(self, sms_service, db_session):
        """Test handling inbound SMS response."""
        # Create original message
        original_msg = SMSMessage(
            sms_sid="orig_sid",
            message_type=SMSType.FOLLOWUP,
            from_number="+1234567890",
            to_number="+1987654321",
            message_body="Follow-up message",
            status=SMSStatus.SENT,
            related_call_id=1,
            related_lead_id=2,
            sent_at=datetime.utcnow()
        )
        db_session.add(original_msg)
        db_session.commit()
        
        with patch.object(sms_service, '_analyze_response') as mock_analyze:
            mock_analyze.return_value = (
                ResponseSentiment.INTERESTED,
                0.95,
                "interested",
                "yes,interested"
            )
            
            response_id = sms_service.handle_inbound_sms(
                message_sid="resp_sid_123",
                from_number="+1987654321",
                to_number="+1234567890",
                body="Yes, I'm interested!",
                received_timestamp=str(int(datetime.utcnow().timestamp() * 1000)),
                db=db_session
            )
            
            assert response_id is not None
            
            # Verify response stored
            response = db_session.query(SMSResponse).filter(
                SMSResponse.id == response_id
            ).first()
            assert response is not None
            assert response.sentiment == ResponseSentiment.INTERESTED
            assert response.confidence_score == 0.95
            assert response.intent == "interested"
            
            # Verify original message marked delivered
            original_msg = db_session.query(SMSMessage).filter(
                SMSMessage.sms_sid == "orig_sid"
            ).first()
            assert original_msg.status == SMSStatus.DELIVERED
    
    def test_handle_inbound_sms_no_original(self, sms_service, db_session):
        """Test handling inbound SMS with no original message."""
        response_id = sms_service.handle_inbound_sms(
            message_sid="resp_sid_456",
            from_number="+1987654321",
            to_number="+1234567890",
            body="Response",
            received_timestamp=str(int(datetime.utcnow().timestamp() * 1000)),
            db=db_session
        )
        
        assert response_id is None
    
    # === Sentiment Analysis Tests ===
    
    def test_basic_sentiment_positive(self, sms_service):
        """Test basic sentiment analysis for positive response."""
        sentiment, confidence, intent, keywords = sms_service._basic_sentiment_analysis(
            "Yes, I'm definitely interested in your offer!"
        )
        
        assert sentiment == ResponseSentiment.INTERESTED
        assert confidence == 0.7
        assert intent == "interested"
    
    def test_basic_sentiment_negative(self, sms_service):
        """Test basic sentiment analysis for negative response."""
        sentiment, confidence, intent, keywords = sms_service._basic_sentiment_analysis(
            "No, I'm not interested. Please stop."
        )
        
        assert sentiment == ResponseSentiment.NOT_INTERESTED
        assert confidence == 0.7
        assert intent == "not_interested"
    
    def test_basic_sentiment_neutral(self, sms_service):
        """Test basic sentiment analysis for neutral response."""
        sentiment, confidence, intent, keywords = sms_service._basic_sentiment_analysis(
            "Got it"
        )
        
        assert sentiment == ResponseSentiment.NEUTRAL
        assert confidence == 0.5
        assert intent == "acknowledgment"
    
    # === Analytics Tests ===
    
    def test_get_sms_analytics(self, sms_service, db_session):
        """Test SMS analytics calculation."""
        # Create test messages
        for i in range(5):
            msg = SMSMessage(
                sms_sid=f"sid_{i}",
                message_type=SMSType.FOLLOWUP,
                from_number="+1234567890",
                to_number=f"+198765432{i}",
                message_body="Test",
                status=SMSStatus.DELIVERED if i < 4 else SMSStatus.FAILED,
                created_at=datetime.utcnow() - timedelta(days=1)
            )
            db_session.add(msg)
        db_session.commit()
        
        # Create responses
        for i in range(3):
            msg = db_session.query(SMSMessage).filter(
                SMSMessage.sms_sid == f"sid_{i}"
            ).first()
            
            response = SMSResponse(
                message_sid=f"resp_sid_{i}",
                original_message_id=msg.id,
                from_number=msg.to_number,
                to_number=msg.from_number,
                response_body="Response",
                sentiment=ResponseSentiment.INTERESTED if i < 2 else ResponseSentiment.NEUTRAL,
                confidence_score=0.8,
                received_at=datetime.utcnow()
            )
            db_session.add(response)
        db_session.commit()
        
        analytics = sms_service.get_sms_analytics(db=db_session, days=7)
        
        assert analytics["total_sent"] == 4
        assert analytics["total_delivered"] == 4
        assert analytics["total_failed"] == 1
        assert analytics["total_responses"] == 3
        assert analytics["positive_responses"] == 2
        assert analytics["neutral_responses"] == 1
    
    # === Status Update Tests ===
    
    def test_update_sms_status(self, sms_service, db_session):
        """Test updating SMS status."""
        msg = SMSMessage(
            sms_sid="test_sid",
            message_type=SMSType.FOLLOWUP,
            from_number="+1234567890",
            to_number="+1987654321",
            message_body="Test",
            status=SMSStatus.SENT
        )
        db_session.add(msg)
        db_session.commit()
        
        success = sms_service.update_sms_status(
            sms_sid="test_sid",
            status=SMSStatus.DELIVERED,
            db=db_session
        )
        
        assert success is True
        
        msg = db_session.query(SMSMessage).filter(
            SMSMessage.sms_sid == "test_sid"
        ).first()
        assert msg.status == SMSStatus.DELIVERED


class TestSMSSchemas:
    """Test Pydantic schemas."""
    
    def test_send_sms_request_valid(self):
        """Test SendSMSRequest schema."""
        request = schemas.SendSMSRequest(
            to_number="+1234567890",
            message_body="Test message"
        )
        
        assert request.to_number == "+1234567890"
        assert request.message_body == "Test message"
        assert request.message_type == SMSType.FOLLOWUP
    
    def test_sms_message_response(self):
        """Test SMSMessageResponse schema."""
        now = datetime.utcnow()
        response = schemas.SMSMessageResponse(
            id=1,
            sms_sid="test_sid",
            message_type=SMSType.FOLLOWUP,
            from_number="+1234567890",
            to_number="+1987654321",
            message_body="Test",
            status=SMSStatus.SENT,
            related_call_id=1,
            related_lead_id=2,
            campaign_id=None,
            cost=-0.0075,
            segments=1,
            sent_at=now,
            created_at=now
        )
        
        assert response.sms_sid == "test_sid"
        assert response.status == SMSStatus.SENT
    
    def test_sms_response_data(self):
        """Test SMSResponseData schema."""
        now = datetime.utcnow()
        response = schemas.SMSResponseData(
            id=1,
            message_sid="resp_sid",
            original_message_id=1,
            from_number="+1987654321",
            to_number="+1234567890",
            response_body="Yes, interested",
            sentiment=ResponseSentiment.INTERESTED,
            confidence_score=0.95,
            intent="interested",
            keywords="yes,interested",
            received_at=now,
            created_at=now
        )
        
        assert response.sentiment == ResponseSentiment.INTERESTED
        assert response.confidence_score == 0.95
    
    def test_bulk_send_sms_request(self):
        """Test BulkSendSMSRequest schema."""
        request = schemas.BulkSendSMSRequest(
            recipients=[
                schemas.SendSMSRequest(to_number="+1111111111", message_body="Msg1"),
                schemas.SendSMSRequest(to_number="+2222222222", message_body="Msg2")
            ],
            campaign_id=1
        )
        
        assert len(request.recipients) == 2
        assert request.campaign_id == 1
    
    def test_schedule_followup_request(self):
        """Test ScheduleFollowupRequest schema."""
        request = schemas.ScheduleFollowupRequest(
            call_id=1,
            lead_id=2,
            to_number="+1234567890",
            message_template="Thanks for your time!",
            delay_seconds=300
        )
        
        assert request.call_id == 1
        assert request.lead_id == 2
        assert request.delay_seconds == 300


class TestSMSModels:
    """Test SMS database models."""
    
    def test_sms_message_creation(self, db_session):
        """Test SMSMessage model."""
        msg = SMSMessage(
            sms_sid="test_sid",
            message_type=SMSType.FOLLOWUP,
            from_number="+1234567890",
            to_number="+1987654321",
            message_body="Test message",
            status=SMSStatus.SENT
        )
        db_session.add(msg)
        db_session.commit()
        
        stored = db_session.query(SMSMessage).filter(
            SMSMessage.sms_sid == "test_sid"
        ).first()
        
        assert stored is not None
        assert stored.to_number == "+1987654321"
        assert stored.status == SMSStatus.SENT
    
    def test_sms_response_creation(self, db_session):
        """Test SMSResponse model."""
        # Create original message first
        msg = SMSMessage(
            sms_sid="orig_sid",
            message_type=SMSType.FOLLOWUP,
            from_number="+1234567890",
            to_number="+1987654321",
            message_body="Test",
            status=SMSStatus.SENT
        )
        db_session.add(msg)
        db_session.commit()
        
        response = SMSResponse(
            message_sid="resp_sid",
            original_message_id=msg.id,
            from_number="+1987654321",
            to_number="+1234567890",
            response_body="Response",
            sentiment=ResponseSentiment.INTERESTED,
            confidence_score=0.9,
            received_at=datetime.utcnow()
        )
        db_session.add(response)
        db_session.commit()
        
        stored = db_session.query(SMSResponse).filter(
            SMSResponse.message_sid == "resp_sid"
        ).first()
        
        assert stored is not None
        assert stored.sentiment == ResponseSentiment.INTERESTED
    
    def test_call_sms_correlation_creation(self, db_session):
        """Test CallSMSCorrelation model."""
        correlation = CallSMSCorrelation(
            call_id=1,
            sms_message_id=1,
            lead_id=2,
            call_to_sms_delay_seconds=300
        )
        db_session.add(correlation)
        db_session.commit()
        
        stored = db_session.query(CallSMSCorrelation).filter(
            CallSMSCorrelation.call_id == 1
        ).first()
        
        assert stored is not None
        assert stored.lead_id == 2
        assert stored.call_to_sms_delay_seconds == 300
    
    def test_sms_campaign_creation(self, db_session):
        """Test SMSCampaign model."""
        campaign = SMSCampaign(
            name="Test Campaign",
            description="Test campaign description",
            message_template="Thanks for your time!",
            trigger_event="call_completed",
            delay_seconds=300
        )
        db_session.add(campaign)
        db_session.commit()
        
        stored = db_session.query(SMSCampaign).filter(
            SMSCampaign.name == "Test Campaign"
        ).first()
        
        assert stored is not None
        assert stored.trigger_event == "call_completed"
        assert stored.active is True
