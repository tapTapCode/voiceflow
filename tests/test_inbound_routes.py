"""
Integration tests for inbound API routes.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from backend.main import app
from backend.inbound.models import CallStatus, SentimentType, Customer, InboundCall


client = TestClient(app)


@pytest.fixture
def mock_dependencies(mocker, db_session):
    """Mock dependencies for API tests."""
    mocker.patch("backend.database.get_db", return_value=db_session)
    mocker.patch("backend.inbound.routes.agent.llm", new_callable=AsyncMock)
    mocker.patch("backend.inbound.routes.agent.voice", new_callable=AsyncMock)
    

def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "agents" in data


def test_start_call_success(mock_dependencies, db_session):
    """Test starting a call successfully."""
    with patch("backend.inbound.routes.agent.start_call", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = "Hello, how can I help?"
        
        response = client.post(
            "/api/inbound/calls/start",
            json={
                "call_sid": "CA123456789abcdef",
                "from_number": "+1234567890",
                "to_number": "+0987654321",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "call_id" in data
        assert "greeting" in data


def test_start_call_duplicate_customer(mock_dependencies, db_session):
    """Test starting call with existing customer."""
    # Create customer first
    customer = Customer(phone_number="+1234567890")
    db_session.add(customer)
    db_session.commit()
    
    with patch("backend.inbound.routes.agent.start_call", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = "Welcome back!"
        
        response = client.post(
            "/api/inbound/calls/start",
            json={
                "call_sid": "CA123456789abcdef",
                "from_number": "+1234567890",
                "to_number": "+0987654321",
            },
        )
        
        assert response.status_code == 200


def test_process_message_success(mock_dependencies, db_session):
    """Test processing customer message."""
    # Create call first
    customer = Customer(phone_number="+1234567890")
    db_session.add(customer)
    db_session.commit()
    
    db_call = InboundCall(
        call_sid="CA123456789abcdef",
        customer_id=customer.id,
        from_number="+1234567890",
        to_number="+0987654321",
        status=CallStatus.IN_PROGRESS,
    )
    db_session.add(db_call)
    db_session.commit()
    
    with patch("backend.inbound.routes.agent.process_customer_message", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = {
            "agent_message": "How can I help?",
            "audio": b"audio_data",
            "sentiment": "positive",
            "sentiment_score": 0.8,
            "should_escalate": False,
            "escalation_reason": None,
        }
        
        response = client.post(
            "/api/inbound/calls/message",
            json={
                "call_sid": "CA123456789abcdef",
                "message": "I need help with my account",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["sentiment"] == "positive"
        assert data["should_escalate"] is False


def test_process_message_not_found(mock_dependencies):
    """Test processing message for non-existent call."""
    response = client.post(
        "/api/inbound/calls/message",
        json={
            "call_sid": "CA_NONEXISTENT",
            "message": "Hello",
        },
    )
    
    assert response.status_code == 404


def test_end_call_success(mock_dependencies, db_session):
    """Test ending a call."""
    customer = Customer(phone_number="+1234567890")
    db_session.add(customer)
    db_session.commit()
    
    db_call = InboundCall(
        call_sid="CA123456789abcdef",
        customer_id=customer.id,
        from_number="+1234567890",
        to_number="+0987654321",
        status=CallStatus.IN_PROGRESS,
    )
    db_session.add(db_call)
    db_session.commit()
    
    with patch("backend.inbound.routes.agent.end_call", new_callable=AsyncMock) as mock_end:
        mock_end.return_value = {
            "id": "CA123456789abcdef",
            "duration_seconds": 300,
            "transcript": "Sample transcript",
        }
        
        response = client.post(
            "/api/inbound/calls/end",
            json={
                "call_sid": "CA123456789abcdef",
                "duration_seconds": 300,
                "transcript": "Sample transcript",
                "resolved": True,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["duration"] == 300
        assert data["resolved"] is True


def test_get_call_success(mock_dependencies, db_session):
    """Test getting call details."""
    customer = Customer(phone_number="+1234567890")
    db_session.add(customer)
    db_session.commit()
    
    db_call = InboundCall(
        call_sid="CA123456789abcdef",
        customer_id=customer.id,
        from_number="+1234567890",
        to_number="+0987654321",
        status=CallStatus.COMPLETED,
        sentiment=SentimentType.POSITIVE,
        sentiment_score=0.85,
        duration_seconds=300,
    )
    db_session.add(db_call)
    db_session.commit()
    
    response = client.get("/api/inbound/calls/CA123456789abcdef")
    
    assert response.status_code == 200
    data = response.json()
    assert data["call_sid"] == "CA123456789abcdef"
    assert data["sentiment"] == "positive"
    assert data["duration"] == 300


def test_get_call_not_found(mock_dependencies):
    """Test getting non-existent call."""
    response = client.get("/api/inbound/calls/CA_NONEXISTENT")
    
    assert response.status_code == 404


def test_list_calls(mock_dependencies, db_session):
    """Test listing calls."""
    customer = Customer(phone_number="+1234567890")
    db_session.add(customer)
    db_session.commit()
    
    # Create multiple calls
    for i in range(3):
        db_call = InboundCall(
            call_sid=f"CA{i}",
            customer_id=customer.id,
            from_number="+1234567890",
            to_number="+0987654321",
            status=CallStatus.COMPLETED,
        )
        db_session.add(db_call)
    
    db_session.commit()
    
    response = client.get("/api/inbound/calls?limit=10&offset=0")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["calls"]) == 3


def test_list_calls_with_status_filter(mock_dependencies, db_session):
    """Test listing calls with status filter."""
    customer = Customer(phone_number="+1234567890")
    db_session.add(customer)
    db_session.commit()
    
    # Create calls with different statuses
    db_call1 = InboundCall(
        call_sid="CA1",
        customer_id=customer.id,
        from_number="+1234567890",
        to_number="+0987654321",
        status=CallStatus.COMPLETED,
    )
    db_call2 = InboundCall(
        call_sid="CA2",
        customer_id=customer.id,
        from_number="+1111111111",
        to_number="+0987654321",
        status=CallStatus.ESCALATED,
    )
    
    db_session.add_all([db_call1, db_call2])
    db_session.commit()
    
    response = client.get("/api/inbound/calls?status=completed")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


def test_submit_feedback_success(mock_dependencies, db_session):
    """Test submitting call feedback."""
    from backend.inbound.models import SupportTicket, ResolutionStatus
    
    customer = Customer(phone_number="+1234567890")
    db_session.add(customer)
    db_session.commit()
    
    db_call = InboundCall(
        call_sid="CA1",
        customer_id=customer.id,
        from_number="+1234567890",
        to_number="+0987654321",
    )
    db_session.add(db_call)
    db_session.commit()
    
    ticket = SupportTicket(
        call_id=db_call.id,
        customer_id=customer.id,
        resolution_status=ResolutionStatus.RESOLVED,
    )
    db_session.add(ticket)
    db_session.commit()
    
    response = client.post(
        f"/api/inbound/calls/{db_call.id}/feedback",
        json={
            "csat_score": 5,
            "feedback": "Great service!",
        },
    )
    
    assert response.status_code == 200


def test_submit_feedback_invalid_score(mock_dependencies):
    """Test submitting feedback with invalid CSAT score."""
    response = client.post(
        "/api/inbound/calls/1/feedback",
        json={
            "csat_score": 10,  # Invalid, should be 1-5
            "feedback": "Good",
        },
    )
    
    assert response.status_code == 400


def test_analytics_summary(mock_dependencies, db_session):
    """Test getting analytics summary."""
    customer = Customer(phone_number="+1234567890")
    db_session.add(customer)
    db_session.commit()
    
    # Create test calls
    db_call1 = InboundCall(
        call_sid="CA1",
        customer_id=customer.id,
        from_number="+1234567890",
        to_number="+0987654321",
        status=CallStatus.COMPLETED,
        sentiment=SentimentType.POSITIVE,
        duration_seconds=300,
    )
    db_call2 = InboundCall(
        call_sid="CA2",
        customer_id=customer.id,
        from_number="+1111111111",
        to_number="+0987654321",
        status=CallStatus.ESCALATED,
        sentiment=SentimentType.NEGATIVE,
        escalated=True,
        duration_seconds=150,
    )
    
    db_session.add_all([db_call1, db_call2])
    db_session.commit()
    
    response = client.get("/api/inbound/analytics/summary")
    
    assert response.status_code == 200
    data = response.json()
    assert "total_calls" in data
    assert "completed_calls" in data
    assert "escalated_calls" in data
    assert "sentiment_distribution" in data
