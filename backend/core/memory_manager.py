"""
Memory Manager - Manages conversation context and history.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json


class ConversationMemory:
    """
    Manages conversation history and context for agents.
    Handles context window management and information extraction.
    """

    def __init__(self, max_messages: int = 20, ttl_hours: int = 24):
        """
        Initialize conversation memory.
        
        Args:
            max_messages: Maximum messages to keep in memory
            ttl_hours: Time-to-live for conversations in hours
        """
        self.max_messages = max_messages
        self.ttl = timedelta(hours=ttl_hours)
        self.conversations: Dict[str, dict] = {}

    def start_conversation(self, conversation_id: str, context: Optional[Dict] = None) -> None:
        """
        Start new conversation.
        
        Args:
            conversation_id: Unique conversation ID (e.g., call_sid)
            context: Initial context data (customer info, etc.)
        """
        self.conversations[conversation_id] = {
            "created_at": datetime.now(),
            "messages": [],
            "context": context or {},
            "metadata": {},
        }

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Add message to conversation history.
        
        Args:
            conversation_id: Conversation ID
            role: Message role (user/assistant)
            content: Message content
            metadata: Optional metadata (sentiment, intent, etc.)
        """
        if conversation_id not in self.conversations:
            self.start_conversation(conversation_id)
        
        conv = self.conversations[conversation_id]
        
        # Trim old messages if exceeding limit
        if len(conv["messages"]) >= self.max_messages:
            conv["messages"] = conv["messages"][-(self.max_messages - 1) :]
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        
        conv["messages"].append(message)

    def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """
        Get conversation message history.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            List of messages
        """
        if conversation_id not in self.conversations:
            return []
        
        # Return messages without timestamp for LLM
        return [
            {
                "role": msg["role"],
                "content": msg["content"],
            }
            for msg in self.conversations[conversation_id]["messages"]
        ]

    def get_context(self, conversation_id: str) -> Dict:
        """
        Get conversation context.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Context dictionary
        """
        if conversation_id not in self.conversations:
            return {}
        
        return self.conversations[conversation_id]["context"]

    def update_context(self, conversation_id: str, context: Dict) -> None:
        """
        Update conversation context.
        
        Args:
            conversation_id: Conversation ID
            context: Context updates
        """
        if conversation_id not in self.conversations:
            self.start_conversation(conversation_id)
        
        self.conversations[conversation_id]["context"].update(context)

    def extract_key_information(self, conversation_id: str) -> Dict:
        """
        Extract key information from conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Extracted information
        """
        if conversation_id not in self.conversations:
            return {}
        
        conv = self.conversations[conversation_id]
        messages = conv["messages"]
        
        return {
            "total_messages": len(messages),
            "first_message_time": messages[0]["timestamp"] if messages else None,
            "last_message_time": messages[-1]["timestamp"] if messages else None,
            "sentiment_trend": self._calculate_sentiment_trend(messages),
            "topics": self._extract_topics(messages),
            "context": conv["context"],
        }

    def end_conversation(self, conversation_id: str) -> Dict:
        """
        End conversation and return summary.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Conversation summary
        """
        if conversation_id not in self.conversations:
            return {}
        
        conv = self.conversations[conversation_id]
        summary = {
            "id": conversation_id,
            "created_at": conv["created_at"].isoformat(),
            "ended_at": datetime.now().isoformat(),
            "message_count": len(conv["messages"]),
            "duration_seconds": (
                datetime.now() - conv["created_at"]
            ).total_seconds(),
            "context": conv["context"],
        }
        
        # Keep summary but clear messages
        conv["messages"] = []
        
        return summary

    def cleanup_expired(self) -> int:
        """
        Remove expired conversations.
        
        Returns:
            Number of conversations removed
        """
        now = datetime.now()
        expired = []
        
        for conv_id, conv in self.conversations.items():
            if now - conv["created_at"] > self.ttl:
                expired.append(conv_id)
        
        for conv_id in expired:
            del self.conversations[conv_id]
        
        return len(expired)

    def _calculate_sentiment_trend(self, messages: List[Dict]) -> str:
        """
        Calculate overall sentiment trend.
        
        Args:
            messages: Message history
            
        Returns:
            Sentiment trend (positive/neutral/negative)
        """
        sentiments = [
            msg.get("metadata", {}).get("sentiment")
            for msg in messages
            if msg.get("metadata", {}).get("sentiment")
        ]
        
        if not sentiments:
            return "neutral"
        
        positive_count = sentiments.count("positive")
        negative_count = sentiments.count("negative")
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        
        return "neutral"

    def _extract_topics(self, messages: List[Dict]) -> List[str]:
        """
        Extract topics from conversation.
        
        Args:
            messages: Message history
            
        Returns:
            List of topics
        """
        topics = []
        
        for msg in messages:
            extracted = msg.get("metadata", {}).get("topics")
            if extracted:
                if isinstance(extracted, list):
                    topics.extend(extracted)
                else:
                    topics.append(extracted)
        
        # Return unique topics
        return list(set(topics))


class LeadMemory(ConversationMemory):
    """Extended memory for lead qualification conversations."""

    def track_lead_data(
        self,
        conversation_id: str,
        field: str,
        value: str,
    ) -> None:
        """
        Track extracted lead data.
        
        Args:
            conversation_id: Conversation ID
            field: Field name (e.g., "budget", "timeline")
            value: Field value
        """
        if conversation_id not in self.conversations:
            self.start_conversation(conversation_id)
        
        if "lead_data" not in self.conversations[conversation_id]["context"]:
            self.conversations[conversation_id]["context"]["lead_data"] = {}
        
        self.conversations[conversation_id]["context"]["lead_data"][field] = value

    def get_lead_profile(self, conversation_id: str) -> Dict:
        """
        Get complete lead profile from conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Lead profile data
        """
        context = self.get_context(conversation_id)
        
        return {
            "lead_data": context.get("lead_data", {}),
            "sentiment": self._calculate_sentiment_trend(
                self.conversations[conversation_id]["messages"]
            ),
            "engagement_score": self._calculate_engagement(conversation_id),
        }

    def _calculate_engagement(self, conversation_id: str) -> float:
        """
        Calculate lead engagement score (0-100).
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Engagement score
        """
        if conversation_id not in self.conversations:
            return 0.0
        
        messages = self.conversations[conversation_id]["messages"]
        message_count = len(messages)
        
        # Score based on message count (max 100)
        base_score = min(message_count * 5, 100)
        
        return base_score
