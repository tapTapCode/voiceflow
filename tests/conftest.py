"""
Pytest configuration and shared fixtures.
"""

import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, MagicMock, patch

from backend.database import Base
from backend.inbound.agent import InboundSupportAgent
from backend.core import LLMService, VoiceService


@pytest.fixture(scope="session")
def test_db_url():
    """Test database URL."""
    return "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine(test_db_url):
    """Create test database engine."""
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine):
    """Create test database session."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    service = AsyncMock(spec=LLMService)
    
    # Mock responses
    service.analyze_sentiment.return_value = {
        "sentiment": "positive",
        "score": 0.8,
        "reason": "Customer sounds satisfied",
    }
    
    service.extract_intent.return_value = "resolve"
    
    service.get_agent_response.return_value = "How can I help you today?"
    
    service.generate_summary.return_value = "Customer called about account issues and was satisfied with the resolution."
    
    service.lead_score.return_value = {
        "score": 75,
        "qualified": True,
        "reasons": ["Budget confirmed", "Timeline immediate"],
    }
    
    return service


@pytest.fixture
def mock_voice_service():
    """Mock voice service for testing."""
    service = AsyncMock(spec=VoiceService)
    service.synthesize.return_value = b"mock_audio_data"
    service.synthesize_streaming = AsyncMock()
    service.get_voices.return_value = []
    return service


@pytest.fixture
def mock_twilio_service():
    """Mock Twilio service for testing."""
    from backend.core import TwilioService
    
    service = MagicMock(spec=TwilioService)
    service.create_inbound_response.return_value = "<Response><Say>Hello</Say></Response>"
    service.make_outbound_call.return_value = "CA123456789abcdef"
    service.get_call.return_value = {
        "sid": "CA123456789abcdef",
        "from": "+1234567890",
        "to": "+0987654321",
        "status": "in-progress",
        "duration": 120,
    }
    return service


@pytest.fixture
def inbound_agent():
    """Create inbound agent for testing."""
    agent = InboundSupportAgent()
    return agent


@pytest.fixture
def sample_call_data():
    """Sample call data for testing."""
    return {
        "call_sid": "CA123456789abcdef",
        "from_number": "+1234567890",
        "to_number": "+0987654321",
        "customer_id": 1,
    }


@pytest.fixture
def sample_customer_data():
    """Sample customer data for testing."""
    return {
        "phone_number": "+1234567890",
        "name": "John Doe",
        "email": "john@example.com",
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set mock environment variables."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test-key")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123456789abcdef")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-auth-token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+0987654321")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
