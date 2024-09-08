"""
Inbound Support Agent - Handles customer support calls with AI.
"""

from typing import Optional, Dict, Any
from backend.core import LLMService, VoiceService, ConversationMemory
from backend.inbound.models import CallStatus, SentimentType
import json


class InboundSupportAgent:
    """
    AI-powered inbound support agent.
    Handles customer calls with sentiment detection and escalation routing.
    """

    SYSTEM_PROMPT = """You are a professional customer support agent for a company.
Your role is to:
1. Greet the customer warmly
2. Understand their issue
3. Provide helpful solutions
4. Be empathetic and professional
5. If you cannot resolve, prepare for escalation

Keep responses concise (1-2 sentences) and natural.
If the customer is frustrated or angry, acknowledge their feelings and offer solutions.
Always remain calm and helpful."""

    ESCALATION_INTENTS = [
        "speak to manager",
        "human agent",
        "escalate",
        "complaint",
        "urgent",
        "billing issue",
    ]

    def __init__(self):
        """Initialize inbound agent."""
        self.llm = LLMService()
        self.voice = VoiceService()
        self.memory = ConversationMemory()

    async def start_call(
        self,
        call_sid: str,
        from_number: str,
        customer_data: Optional[Dict] = None,
    ) -> str:
        """
        Start new inbound call.
        
        Args:
            call_sid: Twilio call SID
            from_number: Customer phone number
            customer_data: Pre-loaded customer info
            
        Returns:
            Initial greeting message
        """
        # Initialize conversation memory with customer context
        context = customer_data or {"phone": from_number}
        self.memory.start_conversation(call_sid, context)
        
        # Generate greeting
        greeting = "Hello! Thank you for calling. How can I help you today?"
        
        # Synthesize to speech
        audio = await self.voice.synthesize(
            greeting,
            voice_id="9BWtsMINqrJLrRacOk9x",  # Support agent voice
        )
        
        return greeting

    async def process_customer_message(
        self,
        call_sid: str,
        customer_message: str,
    ) -> Dict[str, Any]:
        """
        Process customer message and generate response.
        
        Args:
            call_sid: Call SID
            customer_message: Customer speech (transcribed)
            
        Returns:
            Response with agent message, sentiment, and escalation flag
        """
        # Add customer message to memory
        self.memory.add_message(call_sid, "user", customer_message)
        
        # Analyze sentiment
        sentiment_data = await self.llm.analyze_sentiment(customer_message)
        sentiment = SentimentType(sentiment_data["sentiment"])
        sentiment_score = sentiment_data["score"]
        
        # Check for escalation intent
        escalation_intent = await self.llm.extract_intent(
            customer_message,
            self.ESCALATION_INTENTS,
        )
        should_escalate = escalation_intent in self.ESCALATION_INTENTS
        
        # Get conversation history
        history = self.memory.get_conversation_history(call_sid)
        
        # Generate agent response
        agent_response = await self.llm.get_agent_response(
            history,
            self.SYSTEM_PROMPT,
        )
        
        # Add agent response to memory
        self.memory.add_message(
            call_sid,
            "assistant",
            agent_response,
            metadata={
                "sentiment": sentiment.value,
                "sentiment_score": sentiment_score,
                "escalation_intent": escalation_intent,
            },
        )
        
        # Synthesize response to speech
        audio = await self.voice.synthesize(agent_response)
        
        return {
            "agent_message": agent_response,
            "audio": audio,
            "sentiment": sentiment.value,
            "sentiment_score": sentiment_score,
            "should_escalate": should_escalate or sentiment == SentimentType.NEGATIVE,
            "escalation_reason": escalation_intent if should_escalate else None,
        }

    async def end_call(
        self,
        call_sid: str,
        duration_seconds: int,
        transcript: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        End call and generate summary.
        
        Args:
            call_sid: Call SID
            duration_seconds: Call duration
            transcript: Full call transcript
            
        Returns:
            Call summary with metrics
        """
        # Extract call information
        info = self.memory.extract_key_information(call_sid)
        
        # Generate summary if no transcript provided
        if not transcript:
            history = self.memory.get_conversation_history(call_sid)
            if history:
                transcript = await self.llm.generate_summary(history)
        
        # End conversation
        summary = self.memory.end_conversation(call_sid)
        summary.update({
            "duration_seconds": duration_seconds,
            "transcript": transcript,
            "sentiment_trend": info.get("sentiment_trend"),
            "topics": info.get("topics", []),
        })
        
        return summary

    async def generate_escalation_message(self, call_sid: str) -> str:
        """
        Generate message before transferring to human agent.
        
        Args:
            call_sid: Call SID
            
        Returns:
            Escalation message
        """
        message = (
            "I understand you need to speak with a specialist. "
            "Let me transfer you to an agent who can better assist you. "
            "Please hold while I connect you."
        )
        
        return message

    async def generate_closure_message(self, resolution_successful: bool) -> str:
        """
        Generate call closure message.
        
        Args:
            resolution_successful: Whether issue was resolved
            
        Returns:
            Closure message
        """
        if resolution_successful:
            return (
                "Thank you for calling! We're glad we could help. "
                "Have a great day!"
            )
        else:
            return (
                "Thank you for your patience. "
                "We've created a support ticket for your issue. "
                "Our team will follow up with you shortly. Goodbye!"
            )

    async def analyze_call_quality(self, call_sid: str) -> Dict[str, Any]:
        """
        Analyze call quality and performance.
        
        Args:
            call_sid: Call SID
            
        Returns:
            Quality metrics
        """
        info = self.memory.extract_key_information(call_sid)
        history = self.memory.get_conversation_history(call_sid)
        
        # Calculate metrics
        message_count = len(history)
        avg_message_length = (
            sum(len(msg.get("content", "").split()) for msg in history) / message_count
            if message_count > 0
            else 0
        )
        
        return {
            "message_count": message_count,
            "avg_message_length": avg_message_length,
            "sentiment_trend": info.get("sentiment_trend"),
            "topics_discussed": info.get("topics", []),
            "conversation_quality_score": self._calculate_quality_score(
                message_count,
                info.get("sentiment_trend"),
            ),
        }

    def _calculate_quality_score(self, message_count: int, sentiment: str) -> float:
        """
        Calculate overall call quality score (0-100).
        
        Args:
            message_count: Number of messages exchanged
            sentiment: Overall sentiment
            
        Returns:
            Quality score
        """
        base_score = min(message_count * 5, 80)
        
        sentiment_bonus = {
            "positive": 15,
            "neutral": 5,
            "negative": -10,
        }.get(sentiment, 0)
        
        return min(max(base_score + sentiment_bonus, 0), 100)
