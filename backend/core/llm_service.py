"""
LLM Service - Manages OpenAI GPT integration for agent conversations.
"""

import os
from typing import Optional, List
from openai import AsyncOpenAI
from enum import Enum


class ConversationRole(str, Enum):
    """Conversation participant roles."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class LLMService:
    """
    Service for managing OpenAI GPT interactions.
    Handles conversation history, context, and response generation.
    """

    def __init__(self, model: str = "gpt-4"):
        """
        Initialize LLM service.
        
        Args:
            model: OpenAI model to use (default: gpt-4)
        """
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.max_tokens = 500
        self.temperature = 0.7

    async def get_agent_response(
        self,
        conversation_history: List[dict],
        system_prompt: str,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Get AI agent response based on conversation history.
        
        Args:
            conversation_history: List of messages in format {"role": "", "content": ""}
            system_prompt: System instruction for the agent
            temperature: Override default temperature
            
        Returns:
            Agent response text
        """
        messages = [
            {"role": ConversationRole.SYSTEM, "content": system_prompt},
            *conversation_history,
        ]
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=self.max_tokens,
        )
        
        return response.choices[0].message.content

    async def analyze_sentiment(self, text: str) -> dict:
        """
        Analyze sentiment of customer message.
        
        Args:
            text: Customer message text
            
        Returns:
            Sentiment analysis result with score and label
        """
        prompt = f"""Analyze the sentiment of this customer message and respond with JSON:
{{"sentiment": "positive|neutral|negative", "score": 0-1, "reason": "brief explanation"}}

Message: {text}"""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=100,
        )
        
        import json
        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return {"sentiment": "neutral", "score": 0.5, "reason": "analysis failed"}

    async def extract_intent(self, text: str, possible_intents: List[str]) -> str:
        """
        Extract user intent from message.
        
        Args:
            text: User message
            possible_intents: List of possible intents
            
        Returns:
            Detected intent
        """
        intents_str = "\n".join(f"- {intent}" for intent in possible_intents)
        
        prompt = f"""Classify this message into ONE of these intents:
{intents_str}

Respond with just the intent name.

Message: {text}"""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=50,
        )
        
        return response.choices[0].message.content.strip()

    async def generate_summary(self, conversation_history: List[dict]) -> str:
        """
        Generate summary of conversation.
        
        Args:
            conversation_history: Conversation messages
            
        Returns:
            Conversation summary
        """
        # Format conversation for summarization
        conversation_text = "\n".join(
            f"{msg['role']}: {msg['content']}"
            for msg in conversation_history
        )
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize this conversation in 2-3 sentences:\n\n{conversation_text}",
                }
            ],
            temperature=0.5,
            max_tokens=150,
        )
        
        return response.choices[0].message.content

    async def lead_score(self, conversation_data: dict) -> dict:
        """
        Score lead based on conversation data.
        
        Args:
            conversation_data: Data from lead conversation
                - responses: dict of question->answer
                - duration: call duration in seconds
                - sentiment: overall sentiment
                
        Returns:
            Lead score (0-100) and qualifications
        """
        prompt = f"""Score this sales lead from 0-100 and list key qualifications.
Respond with JSON format: {{"score": 0-100, "qualified": true/false, "reasons": [...]}}

Lead data:
- Responses: {conversation_data.get('responses', {})}
- Call duration: {conversation_data.get('duration', 0)} seconds
- Sentiment: {conversation_data.get('sentiment', 'neutral')}
- Budget mentioned: {conversation_data.get('budget', 'No')}
- Timeline: {conversation_data.get('timeline', 'Unknown')}"""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
        )
        
        import json
        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return {
                "score": 50,
                "qualified": False,
                "reasons": ["Analysis error"],
            }
