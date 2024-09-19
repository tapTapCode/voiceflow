"""
Unit tests for inbound support agent.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.inbound.agent import InboundSupportAgent
from backend.inbound.models import CallStatus, SentimentType


@pytest.mark.asyncio
async def test_start_call(mock_llm_service, mock_voice_service):
    """Test starting a new call."""
    agent = InboundSupportAgent()
    agent.llm = mock_llm_service
    agent.voice = mock_voice_service
    
    greeting = await agent.start_call(
        call_sid="CA123456789abcdef",
        from_number="+1234567890",
    )
    
    assert greeting is not None
    assert "Help" in greeting or "help" in greeting.lower()
    assert mock_voice_service.synthesize.called


@pytest.mark.asyncio
async def test_process_customer_message(mock_llm_service, mock_voice_service):
    """Test processing a customer message."""
    agent = InboundSupportAgent()
    agent.llm = mock_llm_service
    agent.voice = mock_voice_service
    
    # Start call first
    await agent.start_call("CA123", "+1234567890")
    
    # Process message
    result = await agent.process_customer_message(
        call_sid="CA123",
        customer_message="I need help with my account",
    )
    
    assert "agent_message" in result
    assert "sentiment" in result
    assert "sentiment_score" in result
    assert "should_escalate" in result
    assert result["sentiment"] in ["positive", "neutral", "negative"]
    assert 0 <= result["sentiment_score"] <= 1


@pytest.mark.asyncio
async def test_sentiment_analysis_positive():
    """Test positive sentiment detection."""
    agent = InboundSupportAgent()
    
    agent.llm = AsyncMock()
    agent.llm.analyze_sentiment.return_value = {
        "sentiment": "positive",
        "score": 0.9,
        "reason": "Very satisfied",
    }
    agent.llm.extract_intent.return_value = "resolve"
    agent.llm.get_agent_response.return_value = "Great!"
    
    agent.voice = AsyncMock()
    agent.voice.synthesize.return_value = b"audio"
    
    await agent.start_call("CA1", "+1234567890")
    result = await agent.process_customer_message("CA1", "This is amazing!")
    
    assert result["sentiment"] == "positive"
    assert result["sentiment_score"] == 0.9


@pytest.mark.asyncio
async def test_escalation_detection():
    """Test escalation trigger."""
    agent = InboundSupportAgent()
    
    agent.llm = AsyncMock()
    agent.llm.analyze_sentiment.return_value = {
        "sentiment": "negative",
        "score": 0.2,
        "reason": "Very unhappy",
    }
    agent.llm.extract_intent.return_value = "speak to manager"
    agent.llm.get_agent_response.return_value = "I'll transfer you..."
    
    agent.voice = AsyncMock()
    agent.voice.synthesize.return_value = b"audio"
    
    await agent.start_call("CA1", "+1234567890")
    result = await agent.process_customer_message("CA1", "This is terrible!")
    
    # Should escalate due to negative sentiment
    assert result["should_escalate"] is True


@pytest.mark.asyncio
async def test_escalation_intent():
    """Test escalation by intent detection."""
    agent = InboundSupportAgent()
    
    agent.llm = AsyncMock()
    agent.llm.analyze_sentiment.return_value = {
        "sentiment": "neutral",
        "score": 0.5,
        "reason": "Neutral",
    }
    agent.llm.extract_intent.return_value = "escalate"
    agent.llm.get_agent_response.return_value = "Let me transfer you..."
    
    agent.voice = AsyncMock()
    agent.voice.synthesize.return_value = b"audio"
    
    await agent.start_call("CA1", "+1234567890")
    result = await agent.process_customer_message("CA1", "I need to speak to a manager")
    
    assert result["should_escalate"] is True
    assert result["escalation_reason"] == "escalate"


@pytest.mark.asyncio
async def test_end_call():
    """Test ending a call."""
    agent = InboundSupportAgent()
    
    agent.llm = AsyncMock()
    agent.llm.generate_summary.return_value = "Customer resolved issue successfully"
    
    agent.voice = AsyncMock()
    
    await agent.start_call("CA1", "+1234567890")
    summary = await agent.end_call(
        call_sid="CA1",
        duration_seconds=300,
        transcript="Customer and agent conversation",
    )
    
    assert summary["id"] == "CA1"
    assert summary["duration_seconds"] == 300
    assert "created_at" in summary
    assert "ended_at" in summary


@pytest.mark.asyncio
async def test_call_quality_score():
    """Test call quality scoring."""
    agent = InboundSupportAgent()
    agent.memory.start_conversation("CA1", {})
    
    # Add messages
    agent.memory.add_message("CA1", "user", "Hi")
    agent.memory.add_message("CA1", "assistant", "Hello", {"sentiment": "positive"})
    agent.memory.add_message("CA1", "user", "Need help")
    agent.memory.add_message("CA1", "assistant", "Sure!", {"sentiment": "positive"})
    
    quality = agent._calculate_quality_score(message_count=4, sentiment="positive")
    
    assert 0 <= quality <= 100
    assert quality > 50  # Positive sentiment should boost score


@pytest.mark.asyncio
async def test_call_quality_negative_sentiment():
    """Test quality score with negative sentiment."""
    agent = InboundSupportAgent()
    
    quality = agent._calculate_quality_score(message_count=4, sentiment="negative")
    
    assert 0 <= quality <= 100
    # Negative sentiment should lower score


@pytest.mark.asyncio
async def test_multiple_messages_conversation():
    """Test conversation with multiple exchanges."""
    agent = InboundSupportAgent()
    
    agent.llm = AsyncMock()
    agent.voice = AsyncMock()
    agent.voice.synthesize.return_value = b"audio"
    
    # Mock different responses for each call
    agent.llm.analyze_sentiment.side_effect = [
        {"sentiment": "neutral", "score": 0.5, "reason": "Initial"},
        {"sentiment": "positive", "score": 0.7, "reason": "Better"},
        {"sentiment": "positive", "score": 0.9, "reason": "Resolved"},
    ]
    
    agent.llm.extract_intent.return_value = "resolve"
    agent.llm.get_agent_response.side_effect = [
        "Hello, how can I help?",
        "Let me check that for you",
        "Here's the solution",
    ]
    
    # Start call
    await agent.start_call("CA1", "+1234567890")
    
    # Message 1
    result1 = await agent.process_customer_message("CA1", "I have an issue")
    assert result1["sentiment"] == "neutral"
    
    # Message 2
    result2 = await agent.process_customer_message("CA1", "I'm feeling better")
    assert result2["sentiment"] == "positive"
    
    # Message 3
    result3 = await agent.process_customer_message("CA1", "Thank you so much")
    assert result3["sentiment"] == "positive"
    assert result3["sentiment_score"] == 0.9


@pytest.mark.asyncio
async def test_escalation_message_generation():
    """Test escalation message generation."""
    agent = InboundSupportAgent()
    
    message = await agent.generate_escalation_message("CA1")
    
    assert "specialist" in message.lower() or "transfer" in message.lower()


@pytest.mark.asyncio
async def test_closure_message_success():
    """Test closure message for successful resolution."""
    agent = InboundSupportAgent()
    
    message = await agent.generate_closure_message(resolution_successful=True)
    
    assert "thank" in message.lower()
    assert "help" in message.lower()


@pytest.mark.asyncio
async def test_closure_message_unresolved():
    """Test closure message for unresolved issue."""
    agent = InboundSupportAgent()
    
    message = await agent.generate_closure_message(resolution_successful=False)
    
    assert "ticket" in message.lower() or "follow" in message.lower()
